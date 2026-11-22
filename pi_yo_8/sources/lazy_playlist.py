import asyncio
import logging
from collections.abc import AsyncGenerator, Callable
from typing import Any

from pi_yo_8.core.playlist import Playlist
from pi_yo_8.core.track import Track
from pi_yo_8.sources.extractor import YTDLP_VIDEO_PARAMS
from pi_yo_8.sources.http import is_url_accessible
from pi_yo_8.sources.manager import YTDLPManager
from pi_yo_8.sources.mapper import is_playable_entry, map_info_to_track
from pi_yo_8.sources.status import StatusManager, YTDLPInfoType

_log = logging.getLogger(__name__)


class LazyPlaylist(Playlist):
    """
    動的にplaylistのentryを読み込むプレイリストクラス
    """
    def __init__(
        self,
        first_entry_info: dict[str, Any],
        generator: AsyncGenerator[dict[str, Any]],
        on_status: Callable[[StatusManager], None] | None = None,
    ) -> None:
        title = first_entry_info.get("playlist_title", "No Title")
        url = first_entry_info.get("playlist_webpage_url", "")
        super().__init__(title, url)

        first_track = map_info_to_track(first_entry_info)
        first_track.playlist_title = first_track.playlist_title or self.title
        self.entries.append(first_track)
        self.cooldowns.append(0)

        self.on_status = on_status
        self._generator: AsyncGenerator[dict[str, Any]] | None = generator
        self.decompress_task: asyncio.Task[None] | asyncio.Future[None] = asyncio.create_task(self._decompress_loop())

    @classmethod
    def from_tracks(
        cls,
        title: str,
        url: str,
        tracks: list[Track],
        on_status: Callable[[StatusManager], None] | None = None,
    ) -> "LazyPlaylist":
        instance = cls.__new__(cls)
        Playlist.__init__(instance, title, url)
        instance.entries = list(tracks)
        for track in instance.entries:
            track.playlist_title = track.playlist_title or instance.title
        instance.cooldowns = [0] * len(tracks)
        instance.random.set_range(len(tracks))
        instance.on_status = on_status
        instance._generator = None
        done_future: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        done_future.set_result(None)
        instance.decompress_task = done_future
        return instance

    async def _decompress_loop(self) -> None:
        if self._generator is None:
            return
        try:
            async for entry in self._generator:
                if not is_playable_entry(entry):
                    continue
                track = map_info_to_track(entry)
                track.playlist_title = track.playlist_title or self.title
                self.entries.append(track)
                max_cooldown = max(self.cooldowns) if self.cooldowns else 0
                self.cooldowns.append(max_cooldown)
                self.random.set_range(len(self.entries))
            _log.info(f"LazyPlaylist '{self.title}' decompression completed with {len(self.entries)} entries.")
        except Exception as e:
            _log.error(f"LazyPlaylist '{self.title}' decompression error: {e}", exc_info=True)
        finally:
            await self.update_next_indexes()

    async def wait_until_index_available(self, index: int) -> None:
        while len(self.entries) <= index and not self.decompress_task.done():
            await asyncio.sleep(0.05)

    async def update_next_indexes(self, length: int = 25) -> None:
        if self.decompress_task.done():
            return await super().update_next_indexes(length)

        if self.status.random_pl:
            return

        if not self.next_indexes and self.entries:
            self.next_indexes.append(0)

        while len(self.next_indexes) < length:
            i = (self.next_indexes[-1] + 1) if self.next_indexes else 0
            if i >= len(self.entries):
                if self.decompress_task.done():
                    if not self.status.loop_pl or not self.entries:
                        break
                    self.next_indexes.append(i % len(self.entries))
                else:
                    break
            else:
                self.next_indexes.append(i)

        self._preload_upcoming_entries()

    async def set_next_index_by_video_id(self, video_id: str) -> bool:
        entry_index = 0
        while True:
            await self.wait_until_index_available(entry_index)
            if len(self.entries) <= entry_index:
                return False
            entry = self.entries[entry_index]
            if entry.id == video_id or (entry.raw_info and entry.raw_info.get("id") == video_id):
                self.next_indexes.clear()
                self.next_indexes.append(entry_index)
                self._preload_upcoming_entries()
                return True
            entry_index += 1

    def _preload_upcoming_entries(self, count: int = 2) -> None:
        if not self.next_indexes:
            return
        for i in range(min(len(self.next_indexes), count)):
            idx = self.next_indexes[i]
            if idx < len(self.entries):
                entry = self.entries[idx]
                if not entry.is_stream_ready() and not entry.is_loading():
                    asyncio.create_task(ensure_track_playable(entry, on_status=self.on_status))

    async def get_current_track(self) -> Track | None:
        if not self.next_indexes:
            if not self.decompress_task.done() and self.status.random_pl:
                await self.wait_until_index_available(5)
                chosen = self.random.select_next_index()
                self.next_indexes.append(chosen)
            else:
                await self.update_next_indexes()

        if self.next_indexes:
            idx = self.next_indexes[0]
            await self.wait_until_index_available(idx)
            if idx < len(self.entries):
                current_track = self.entries[idx]
                _log.info(f"Loading current track at index {idx}: '{current_track.title}'")
                if await ensure_track_playable(current_track, on_status=self.on_status):
                    return current_track
                _log.warning(f"Track '{current_track.title}' could not be played. Skipping to next.")
                await self.next()
                return await self.get_current_track()
        return None


async def ensure_track_playable(track: Track, on_status: Callable[[StatusManager], None] | None = None) -> bool:
    """
    トラックのストリームURLが有効か検査し、無効なら再抽出を行う。
    既に抽出中の場合は同一タスクを待機し、二重抽出（重複リクエスト）を防止する。
    """
    if track.is_stream_ready() and track.stream_info:
        _log.debug(f"Track '{track.title}' stream ready, checking URL accessibility...")
        if await is_url_accessible(track.stream_info.url, track.stream_info.http_headers, track.stream_info.cookies):
            _log.debug(f"Track '{track.title}' stream URL is accessible.")
            return True
        _log.info(f"Track '{track.title}' stream URL inaccessible/expired. Re-extracting...")

    # 既に抽出タスクが実行中であれば、その完了を待つ（重複実行を防止）
    if track.is_loading() and track._load_task is not None:
        _log.debug(f"Track '{track.title}' stream extraction already in flight, awaiting existing task...")
        return await track._load_task

    task = asyncio.create_task(_do_extract_stream(track, on_status))
    track._load_task = task
    try:
        return await task
    finally:
        track._load_task = None


async def _resolve_youtube_url(
    search_query: str,
    title: str,
    on_status: Callable[[StatusManager], None] | None = None,
) -> str | None:
    """検索クエリからYouTube動画URLを1件取得する (extract_flatによる第1段階)"""
    target_query = f"ytsearch1:{search_query}"
    _log.info(f"Searching YouTube URL for external track '{title}': {target_query}")
    extractor = YTDLPManager.get_extractor(YTDLP_VIDEO_PARAMS)
    gen, sm = extractor.extract_raw_info(target_query)
    sm.info_type = YTDLPInfoType.VIDEO
    sm.name = title
    if on_status:
        on_status(sm)
    try:
        async for info in gen:
            if video_url := info.get("webpage_url") or info.get("original_url") or info.get("url"):
                await gen.aclose()
                return str(video_url)
    except Exception as e:
        _log.error(f"Failed to search YouTube URL for '{title}': {e}", exc_info=True)
    return None


async def _do_extract_stream(track: Track, on_status: Callable[[StatusManager], None] | None = None) -> bool:
    search_query = track.raw_info.get("search_query") if track.raw_info else None
    is_external = isinstance(search_query, str) and bool(search_query)

    if is_external:
        assert isinstance(search_query, str)
        target_url = track.raw_info.get("resolved_youtube_url")
        if not target_url:
            target_url = await _resolve_youtube_url(search_query, track.title, on_status)
            if not target_url:
                return False
            track.raw_info["resolved_youtube_url"] = target_url
    else:
        target_url = track.web_url

    _log.info(f"Extracting stream URL for: '{track.title}' ({target_url})")
    extractor = YTDLPManager.get_extractor(YTDLP_VIDEO_PARAMS)
    gen, sm = extractor.extract_raw_info(target_url)
    sm.info_type = YTDLPInfoType.VIDEO
    sm.name = track.title
    if on_status:
        on_status(sm)
    try:
        async for info in gen:
            if info.get("formats") and info.get("url"):
                fresh = map_info_to_track(info)
                track.stream_info = fresh.stream_info
                if is_external:
                    track.duration = track.duration or fresh.duration
                    track.thumbnail_url = track.thumbnail_url or fresh.thumbnail_url
                    track.upload_date = track.upload_date or fresh.upload_date
                    track.view_count = track.view_count if track.view_count is not None else fresh.view_count
                    track.uploader = track.uploader or fresh.uploader
                    track.uploader_url = track.uploader_url or fresh.uploader_url
                    track.uploader_id = track.uploader_id or fresh.uploader_id
                else:
                    track.duration = fresh.duration or track.duration
                    track.thumbnail_url = fresh.thumbnail_url or track.thumbnail_url
                    track.upload_date = fresh.upload_date or track.upload_date
                    track.view_count = fresh.view_count if fresh.view_count is not None else track.view_count
                    track.uploader = fresh.uploader or track.uploader
                    track.uploader_url = fresh.uploader_url or track.uploader_url
                    track.uploader_id = fresh.uploader_id or track.uploader_id
                if fresh.raw_info:
                    track.raw_info.update(fresh.raw_info)
                _log.info(f"Successfully extracted stream URL for '{track.title}'")
                await gen.aclose()
                return True
    except Exception as e:
        _log.error(f"Failed to extract stream for '{track.title}': {e}", exc_info=True)
    return False

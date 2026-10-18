import asyncio
from collections.abc import AsyncGenerator
from typing import Any

from pi_yo_8.core.playlist import Playlist
from pi_yo_8.core.track import Track
from pi_yo_8.sources.extractor import YTDLP_VIDEO_PARAMS
from pi_yo_8.sources.http import is_url_accessible
from pi_yo_8.sources.manager import YTDLPManager
from pi_yo_8.sources.mapper import map_info_to_track


class LazyPlaylist(Playlist):
    """
    動的にplaylistのentryを読み込むプレイリストクラス
    """
    def __init__(self, first_entry_info: dict[str, Any], generator: AsyncGenerator[dict[str, Any]]):
        title = first_entry_info.get("playlist_title", "No Title")
        url = first_entry_info.get("playlist_webpage_url", "")
        super().__init__(title, url)

        first_track = map_info_to_track(first_entry_info)
        self.entries.append(first_track)
        self.cooldowns.append(0)

        self._generator = generator
        self.decompress_task = asyncio.create_task(self._decompress_loop())

    async def _decompress_loop(self) -> None:
        try:
            async for entry in self._generator:
                if entry.get("duration") is None and entry.get("channel") is None and entry.get("view_count") is None:
                    continue
                track = map_info_to_track(entry)
                self.entries.append(track)
                max_cooldown = max(self.cooldowns) if self.cooldowns else 0
                self.cooldowns.append(max_cooldown)
                self.random.set_range(len(self.entries))
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

        while len(self.next_indexes) < length:
            i = (self.next_indexes[-1] + 1) if self.next_indexes else 0
            await self.wait_until_index_available(i)
            if not self.status.loop_pl and i >= len(self.entries):
                break
            self.next_indexes.append(i % len(self.entries))

        self._preload_upcoming_entries()

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
                if await ensure_track_playable(current_track):
                    return current_track
                await self.next()
                return await self.get_current_track()
        return None

async def ensure_track_playable(track: Track) -> bool:
    """
    トラックのストリームURLが有効か検査し、無効なら再抽出を行う
    """
    if track.is_stream_ready() and track.stream_info:
        if await is_url_accessible(track.stream_info.url, track.stream_info.http_headers, track.stream_info.cookies):
            return True

    # 再抽出
    extractor = YTDLPManager.YT_DLP.get(YTDLP_VIDEO_PARAMS)
    gen, _ = extractor.extract_raw_info(track.web_url)
    async for info in gen:
        if info.get("formats") and info.get("url"):
            fresh = map_info_to_track(info)
            track.stream_info = fresh.stream_info
            track.duration = fresh.duration
            track.thumbnail_url = fresh.thumbnail_url
            return True
    return False

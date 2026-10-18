import asyncio
import logging
import re
import time
from typing import Any

from pi_yo_8.core.play_mode import PlayMode
from pi_yo_8.core.queue import PlayQueue
from pi_yo_8.core.track import Track
from pi_yo_8.engine.track_stream import AudioTrack
from pi_yo_8.sources.lazy_playlist import LazyPlaylist, ensure_track_playable
from pi_yo_8.sources.resolver import TrackResolver

_log = logging.getLogger(__name__)

re_skip = re.compile(r'^((-|)\d+)([hms])$')
re_skip_set_h = re.compile(r'^(\d+)[:;,](\d+)[:;,](\d+)$')
re_skip_set_m = re.compile(r'^(\d+)[:;,](\d+)$')

class PlayerService:
    def __init__(self, guild_name: str, audio_track: AudioTrack, on_status_report: Any = None):
        self.guild_name = guild_name
        self.player_track = audio_track
        self.queue = PlayQueue()
        self.status = PlayMode()
        self.on_status_report = on_status_report
        self.last_played_url: str | None = None
        self.last_played_time: float = 0.0

    async def enqueue(self, query: str) -> None:
        if not query:
            self.player_track.resume()
            return

        result, status_manager = await TrackResolver.resolve(query)
        if self.on_status_report and status_manager:
            self.on_status_report(status_manager)

        if not result:
            return

        self.queue.play_queue.append(result)
        if not self.player_track.has_audio_data():
            await self.play_loop()
        self.player_track.resume()

    async def play(self, query: str) -> None:
        if not query:
            self.player_track.resume()
            return

        result, status_manager = await TrackResolver.resolve(query)
        if self.on_status_report and status_manager:
            self.on_status_report(status_manager)

        if not result:
            return

        if self.queue.play_queue:
            await self._advance_and_update_status(ignore_playlist=True)
        self.queue.play_queue.appendleft(result)

        if isinstance(result, LazyPlaylist):
            self.status = result.status

        await self.play_loop()
        self.player_track.resume()

    async def get_current_playable_track(self) -> Track | None:
        raw = self.queue.get_current_raw()
        if not raw:
            return None
        if isinstance(raw, LazyPlaylist):
            return await raw.get_current_track()
        if isinstance(raw, Track):
            if await ensure_track_playable(raw):
                return raw
            # 再生不能なら次へ
            await self.skip_tracks(1)
            return await self.get_current_playable_track()
        return None

    async def play_loop(self, played_url: str | None = None, played_at: float = 0.0) -> None:
        current_raw = self.queue.get_current_raw()
        if current_raw:
            url_match = (played_url is not None and self.last_played_url == played_url)
            quick_end = (time.time() - played_at) <= 0.2
            if not self.status.loop and (url_match or quick_end):
                await self._advance_and_update_status()

        track = await self.get_current_playable_track()
        if track and track.is_stream_ready():
            self.last_played_url = track.stream_info.url if track.stream_info else None
            self.last_played_time = time.time()
            _log.info(f"{self.guild_name} : Play {track.web_url} [Queue: {len(self.queue.play_queue)}]")

            loop = asyncio.get_running_loop()
            await self.player_track.play(
                track,
                after=lambda: asyncio.run_coroutine_threadsafe(
                    self.play_loop(self.last_played_url, self.last_played_time), loop
                )
            )

    async def _advance_and_update_status(self, count: int = 1, ignore_playlist: bool = False) -> bool:
        if count == 0:
            return bool(self.queue.play_queue)
        res = await self.queue.next(count, ignore_playlist)
        if res and self.queue.play_queue:
            head = self.queue.play_queue[0]
            if isinstance(head, LazyPlaylist):
                head.status.set(self.status.loop, self.status.loop_pl, self.status.random_pl)
                self.status = head.status
        return res

    async def skip_tracks(self, count: int = 1) -> None:
        if count == 0:
            return
        res = await self._advance_and_update_status(count)
        if not res:
            return
        await self.play_loop()
        if self.player_track.is_paused():
            self.player_track.resume()

    async def seek_or_skip(self, skip_input: str | None) -> None:
        if not skip_input:
            await self.skip_tracks(1)
            return

        try:
            sec = int(skip_input)
        except ValueError:
            s_lower = skip_input.lower()
            if res := re_skip.match(s_lower):
                sec = int(res.group(1))
                unit = res.group(3)
                if unit == 'h':
                    sec *= 3600
                elif unit == 'm':
                    sec *= 60
            elif res := re_skip_set_h.match(s_lower):
                sec = int(res.group(3)) + int(res.group(2)) * 60 + int(res.group(1)) * 3600 - int(self.player_track.timer)
            elif res := re_skip_set_m.match(s_lower):
                sec = int(res.group(2)) + int(res.group(1)) * 60 - int(self.player_track.timer)
            else:
                return

        await self.player_track.seek_by_seconds(sec)

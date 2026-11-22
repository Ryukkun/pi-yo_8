import asyncio
import logging
import re
import time
from collections.abc import Callable

from pi_yo_8.core.play_mode import PlayMode
from pi_yo_8.core.queue import PlayQueue
from pi_yo_8.core.track import Track
from pi_yo_8.engine.track_stream import AudioTrack
from pi_yo_8.sources.lazy_playlist import LazyPlaylist, ensure_track_playable
from pi_yo_8.sources.resolver import TrackResolver
from pi_yo_8.sources.status import StatusManager

_log = logging.getLogger(__name__)

re_skip = re.compile(r'^((-|)\d+)([hms])$')
re_skip_set_h = re.compile(r'^(\d+)[:;,](\d+)[:;,](\d+)$')
re_skip_set_m = re.compile(r'^(\d+)[:;,](\d+)$')


class PlayerService:
    def __init__(
        self,
        guild_name: str,
        audio_track: AudioTrack,
        on_status_report: Callable[[StatusManager], None] | None = None,
        on_track_change: Callable[[], None] | None = None,
    ) -> None:
        self.guild_name = guild_name
        self.player_track = audio_track
        self.queue = PlayQueue()
        self.status = PlayMode()
        self.on_status_report = on_status_report
        self.on_track_change = on_track_change
        self.last_played_url: str | None = None
        self.last_played_time: float = 0.0

    async def enqueue(self, query: str) -> None:
        if not query:
            self.player_track.resume()
            return

        result, _ = await TrackResolver.resolve(query, on_status=self.on_status_report)
        if not result:
            return

        self.queue.play_queue.append(result)
        if len(self.queue.play_queue) == 1 and isinstance(result, LazyPlaylist):
            self.status = result.status
        if not self.player_track.has_audio_data():
            await self.play_loop()
        self.player_track.resume()

    async def play(self, query: str) -> None:
        if not query:
            self.player_track.resume()
            return

        result, _ = await TrackResolver.resolve(query, on_status=self.on_status_report)
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
            track = await raw.get_current_track()
            if track is not None:
                return track
            await self._advance_and_update_status(1)
            return await self.get_current_playable_track()
        if isinstance(raw, Track):
            if await ensure_track_playable(raw, on_status=self.on_status_report):
                return raw
            # 再生不能なら次へスキップ
            await self.skip_tracks(1)
            return await self.get_current_playable_track()
        return None

    async def play_loop(self, played_url: str | None = None, played_at: float = 0.0) -> None:
        current_raw = self.queue.get_current_raw()
        if current_raw:
            url_match = (played_url is not None and self.last_played_url == played_url)
            elapsed = time.time() - played_at
            quick_end = (played_at > 0.0) and (elapsed <= 0.5)
            if not self.status.loop and (url_match or quick_end):
                if quick_end:
                    _log.warning(f"{self.guild_name} : Track ended abruptly ({elapsed:.3f}s). Advancing queue.")
                await self._advance_and_update_status()

        track = await self.get_current_playable_track()
        if track and track.is_stream_ready():
            self.last_played_url = track.stream_info.url if track.stream_info else None
            self.last_played_time = time.time()
            _log.info(f"{self.guild_name} : Now Playing '{track.title}' [{track.web_url}] [Queue items: {len(self.queue.play_queue)}]")
            if self.on_track_change:
                self.on_track_change()

            loop = asyncio.get_running_loop()
            await self.player_track.play(
                track,
                after=lambda: asyncio.run_coroutine_threadsafe(
                    self.play_loop(self.last_played_url, self.last_played_time), loop
                )
            )
        else:
            _log.info(f"{self.guild_name} : Play loop finished - no more tracks to play.")
            if self.on_track_change:
                self.on_track_change()

    def _sync_head_status(self) -> None:
        if self.queue.play_queue:
            head = self.queue.play_queue[0]
            if isinstance(head, LazyPlaylist):
                head.status.set(self.status.loop, self.status.loop_pl, self.status.random_pl)
                self.status = head.status

    async def _advance_and_update_status(self, count: int = 1, ignore_playlist: bool = False) -> bool:
        if count == 0:
            return bool(self.queue.play_queue)
        res = await self.queue.next(count, ignore_playlist)
        if res:
            self._sync_head_status()
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

    async def skip_to_queue_index(self, target_index: int) -> None:
        if not self.queue.skip_to_queue_index(target_index):
            return
        self._sync_head_status()
        await self.play_loop()
        if self.player_track.is_paused():
            self.player_track.resume()

    async def select_history(self, action_value: str) -> None:
        if action_value.startswith("pl_rewind:"):
            steps = int(action_value.split(":", 1)[1])
            await self.skip_tracks(-steps)
            return

        if action_value.startswith("hist:"):
            hist_idx = int(action_value.split(":", 1)[1])
            if not self.queue.recall_history_item(hist_idx):
                return
            head = self.queue.get_current_raw()
            if isinstance(head, LazyPlaylist):
                self.status = head.status
                if not head.next_indexes:
                    if head.entries:
                        head.next_indexes.append(0)
                    await head.update_next_indexes()
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
            s_lower = skip_input.lower().strip()
            if res := re_skip.match(s_lower):
                val = int(res.group(1))
                unit = res.group(3)
                multipliers = {'h': 3600, 'm': 60, 's': 1}
                sec = val * multipliers[unit]
            elif res := re_skip_set_h.match(s_lower):
                h, m, s = int(res.group(1)), int(res.group(2)), int(res.group(3))
                sec = (h * 3600 + m * 60 + s) - int(self.player_track.timer)
            elif res := re_skip_set_m.match(s_lower):
                m, s = int(res.group(1)), int(res.group(2))
                sec = (m * 60 + s) - int(self.player_track.timer)
            else:
                return

        await self.player_track.seek_by_seconds(sec)

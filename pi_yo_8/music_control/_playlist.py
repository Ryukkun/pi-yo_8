import asyncio
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from random import Random
from typing import Any, Generator

from pi_yo_8.audio_data import YTDLPAudioData
from pi_yo_8.music_control import Status
from pi_yo_8.music_control import PlaylistRandom


class Playlist:
    def __init__(self, info:dict[str, Any]):
        """
        entriesは常に1つ以上ある
        """
        self.entries: list[YTDLPAudioData] = info.pop('entries')
        self.now_index: int | None = None
        self.next_indexes: deque[int] = deque([0])
        self.cooldowns: list[int] = [0] * len(self.entries)
        # statusはMusicControllerと同期させる
        self._status = Status(loop=False, loop_pl=True, random_pl=False)
        self.random = PlaylistRandom(len(self.entries))


    @property
    def status(self) -> Status:
        return self._status

    @status.setter
    def status(self, value: Status):
        old = self._status
        self._status = value
        if self._status.loop_pl != old.loop_pl or self._status.random_pl != old.random_pl:
            self.next_indexes.clear()
            if self._status.random_pl:
                self.random.range = len(self.entries)
                self.random.cooldowns = self.cooldowns.copy()
            self.generate_next_indexies()

            


    def generate_next_indexies(self):
        if self.status.random_pl:
            while len(self.next_indexes) < 25:
                self.next_indexes.append(self.random.next())
        else:
            while len(self.next_indexes) < 25:
                i = (self.next_indexes[-1] + 1) if self.next_indexes else (0 if self.now_index is None else self.now_index + 1)
                if not self.status.loop_pl and i >= len(self.entries):
                    return
                self.next_indexes.append(i % len(self.entries))


    async def set_next_index_from_videoID(self, video_id: str):
        for i, entry in enumerate(self.entries):
            if entry.video_id() == video_id:
                self.next_indexes = i
                if not entry.is_available():
                    entry.update_streaming_data.create_task()
                break


    async def next(self, count:int = 1) -> bool:
        """
        indexを進める 動画のロードはしない
        """
        if self.status.random_pl:
            self.now_index = self.next_indexes.popleft()
        else:
            self.now_index = self.now_index + count
            if self.status.loop_pl:
                self.now_index %= len(self.entries)
            elif not (0 <= self.now_index < len(self.entries)):
                return False

            self.next_index = (self.now_index + 1) % len(self.entries)

        next_entry = self.entries[self.next_index]
        if not next_entry.is_available():
            next_entry.update_streaming_data.create_task()

        for _ in range(len(self.cooldowns)):
            if _ == self.now_index:
                self.cooldowns[_] = 0
            else:
                self.cooldowns[_] += 1
        now_entry = self.entries[self.now_index]
        if not now_entry.is_available():
            now_entry.update_streaming_data.create_task()
        return now_entry
    

    async def get_now_entry(self) -> YTDLPAudioData | None:
        if len(self.entries) <= self.now_index:
            return None
        now_entry: YTDLPAudioData = self.entries[self.now_index]
        if not now_entry.is_available():
            if now_entry.update_streaming_data.is_running():
                await now_entry.update_streaming_data.wait()
            else:
                await now_entry.update_streaming_data.run()
        return now_entry


class GeneratorPlaylist(Playlist):
    def __init__(self, info:dict[str, Any]):
        generator : Generator[dict[str, Any] | None] = info['entries']
        info['entries'] = []
        super().__init__(info)

        def task():
            try:
                self.entries.append(YTDLPAudioData(next(generator)))
            except:
                pass
        with ThreadPoolExecutor(max_workers=1) as exe:
            self.decompres_task = exe.submit(task)


    async def _wait_load_entry(self, i:int):
        while i >= len(self.entries) and self.decompres_task.running():
            await asyncio.sleep(0.1)


    async def set_next_index_from_videoID(self, video_id: str):
        i = 0
        while True:
            if i >= len(self.entries):
                if self.decompres_task.running():
                    await asyncio.sleep(0.1)
                    continue
                else:
                    return

            entry = self.entries[i]
            if entry.video_id() == video_id:
                self.next_index = i
                if not entry.is_available():
                    entry.update_streaming_data.create_task()
                return
            i += 1


    async def next(self, count:int = 1) -> bool:
        if not self.status.random_pl:
            i = self.now_index + count + 1
            await self._wait_load_entry(i)
        super().next(count)
    

    async def get_now_entry(self) -> YTDLPAudioData | None:
        await self._wait_load_entry(self.now_index)
        return await super().get_now_entry()
import asyncio
from concurrent.futures import ThreadPoolExecutor
from random import Random
from typing import Any, Generator

from pi_yo_8.audio_data import YTDLPAudioData


class Playlist:
    def __init__(self, info:dict[str, Any]):
        self.entries: list[YTDLPAudioData] = info.pop('entries')
        self.now_index: int | None = None
        self.next_index: int = 0


    async def set_next_index_from_videoID(self, video_id: str):
        for i, entry in enumerate(self.entries):
            if entry.video_id() == video_id:
                self.next_index = i
                if not entry.is_available():
                    entry.update_streaming_data.create_task()
                break


    async def get_next_entry(self, random:bool = False) -> YTDLPAudioData:
        self.now_index = self.next_index
        if random:
            self.next_index = Random.randint(0, len(self.entries) - 1)
        else:
            self.next_index = (self.next_index + 1) % len(self.entries)

        next_entry = self.entries[self.next_index]
        if not next_entry.is_available():
            next_entry.update_streaming_data.create_task()

        entry = self.entries[self.now_index]
        if not entry.is_available():
            if entry.update_streaming_data.is_running():
                await entry.update_streaming_data.wait()
            else:
                await entry.update_streaming_data.run()
        return entry



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


    async def get_next_entry(self, random:bool = False) -> YTDLPAudioData:
        await self._wait_load_entry(self.next_index + 1)
        return await super().get_next_entry(random)
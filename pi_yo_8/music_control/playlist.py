import asyncio
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Generator

from pi_yo_8.music_control.utils import Status, PlaylistRandom

if TYPE_CHECKING:
    from pi_yo_8.extractor.yt_dlp.audio_data import YTDLPAudioData

class Playlist:
    def __init__(self, info:dict[str, Any]):
        """
        entriesは常に1つ以上ある
        """
        from pi_yo_8.extractor.yt_dlp.audio_data import YTDLPAudioData
        self.entries: list["YTDLPAudioData"] = [YTDLPAudioData(_) for _ in info['entries']]
        # 0 再生中, 1~ 次に再生
        self.next_indexes: deque[int] = deque()
        self.cooldowns: list[int] = [0] * len(self.entries)
        # statusはMusicControllerと同期させる
        self._status = Status(loop=False, loop_pl=True, random_pl=False, callback=self.status_callback)
        self.random = PlaylistRandom(len(self.entries))


    @property
    def status(self) -> "Status":
        return self._status

    def status_callback(self, old: "Status", new: "Status"):
        if new.loop_pl != old.loop_pl or new.random_pl != old.random_pl:
            if self.next_indexes:
                playing_index = self.next_indexes[0]
                self.next_indexes.clear()
                self.next_indexes.append(playing_index)
            if self._status.random_pl:
                self.random.range = len(self.entries)
                self.random.cooldowns = self.cooldowns.copy()
            asyncio.get_event_loop().create_task(self.update_next_indexies())


    async def update_next_indexies(self) -> None:
        if self.status.random_pl:
            while len(self.next_indexes) < 25:
                self.next_indexes.append(self.random.next())
        else:
            while len(self.next_indexes) < 25:
                i = (self.next_indexes[-1] + 1) if self.next_indexes else 0
                if not self.status.loop_pl and len(self.entries) <= i:
                    return
                self.next_indexes.append(i % len(self.entries))



    async def set_next_index_from_videoID(self, video_id: str):
        for i, entry in enumerate(self.entries):
            if entry.video_id() == video_id:
                self.next_indexes.clear()
                self.next_indexes.append(i)
                if not await entry.is_available():
                    entry.check_streaming_data.create_task()
                break


    async def next(self, count:int = 1) -> bool:
        """
        indexを進める 動画のロードはしない
        """
        for _ in range(count):
            await self.update_next_indexies()
            if not self.next_indexes: return False
            self.next_indexes.popleft()
            if not self.next_indexes: return False

        for _ in range(len(self.cooldowns)):
            if _ == self.next_indexes[0]:
                self.cooldowns[_] = 0
            else:
                self.cooldowns[_] += 1

        for i in range(min(2, len(self.next_indexes))):
            self.entries[self.next_indexes[i]].check_streaming_data.create_task()
        return True
    

    async def get_now_entry(self) -> "YTDLPAudioData | None":
        if self.next_indexes:
            now_entry = self.entries[self.next_indexes[0]]
            await now_entry.check_streaming_data.run()
            if await now_entry.is_available():
                return now_entry
        return None


class GeneratorPlaylist(Playlist):
    def __init__(self, info:dict[str, Any]):
        from pi_yo_8.extractor.yt_dlp.audio_data import YTDLPAudioData
        generator : Generator[dict[str, Any] | None] = info['entries']
        info['entries'] = []
        super().__init__(info)

        def task():
            try:
                while True:
                    info:dict | None = next(generator)
                    if not info:
                        break
                    if info.get("channel", None):
                        self.entries.append(YTDLPAudioData(info))
            except:
                pass
        with ThreadPoolExecutor(max_workers=1) as exe:
            self.decompres_task = exe.submit(task)


    async def _wait_load_entry(self, i:int):
        while i >= len(self.entries) and self.decompres_task.running():
            await asyncio.sleep(0.05)


    async def update_next_indexies(self) -> None:
        if self.decompres_task.done():
            return await super().update_next_indexies()
        # ジェネレーターが解析し終わっていない状況でnext_indexies作成できない
        if self.status.random_pl:
            return
        while len(self.next_indexes) < 25:
            i = (self.next_indexes[-1] + 1) if self.next_indexes else 0
            await self._wait_load_entry(i)
            if not self.status.loop_pl and i >= len(self.entries):
                return
            self.next_indexes.append(i % len(self.entries))


    async def set_next_index_from_videoID(self, video_id: str):
        i = 0
        while True:
            await self._wait_load_entry(i)
            if len(self.entries) <= i:
                return

            entry = self.entries[i]
            if entry.video_id() == video_id:
                self.next_indexes.clear()
                self.next_indexes.append(i)
                if not await entry.is_available():
                    entry.check_streaming_data.create_task()
                return
            i += 1


    async def next(self, count:int = 1) -> bool:
        if self.decompres_task.done():
            return await super().next(count)
        if self.status.random_pl:
            self.random.range = len(self.entries)
            i = self.random.next()
            self.next_indexes.clear()
            self.next_indexes.append(i)
            self.entries[i].check_streaming_data.create_task()
            return True
        
        i = self.next_indexes[0] + count + 1
        await self._wait_load_entry(i)
        return await super().next(count)        
    

    async def get_now_entry(self) -> "YTDLPAudioData | None":
        await self._wait_load_entry(self.next_indexes[0])
        return await super().get_now_entry()
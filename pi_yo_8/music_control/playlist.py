import asyncio
from collections import deque
from typing import TYPE_CHECKING, Any, Callable

from pi_yo_8.music_control.utils import Status, PlaylistRandom
from pi_yo_8.utils import AsyncGenWrapper
from pi_yo_8.yt_dlp.audio_data import YTDLPAudioData

if TYPE_CHECKING:
    from pi_yo_8.main import DataInfo

class Playlist:
    def __init__(self, playlist_title:str, playlist_url:str, guild_info:"DataInfo|None", loop=False, loop_pl=True, random_pl=False):
        """
        entriesは常に1つ以上ある
        """
        self.title = playlist_title
        self.url = playlist_url
        self.guild_info = guild_info
        self.entries: list["YTDLPAudioData"] = []
        # 0 再生中, 1~ 次に再生
        self.next_indexes: deque[int] = deque()
        self.play_history: deque[int] = deque()
        self.cooldowns: list[int] = [0] * len(self.entries)
        # statusはMusicControllerと同期させる
        self._status = Status(loop, loop_pl, random_pl, callback=self.status_callback)
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
            if new.random_pl:
                self.random.set_range(len(self.entries))
                self.random.cooldowns = self.cooldowns.copy()
            asyncio.get_event_loop().create_task(self.update_next_indexies())


    async def update_next_indexies(self, length:int=25) -> None:
        '''
        next_indexesをlength個まで補充する
        再生可能なものがない場合はlength以下になる
        '''
        if self.status.random_pl:
            while len(self.next_indexes) < length:
                self.next_indexes.append(self.random.next())
                
        else:
            while len(self.next_indexes) < length:
                i = (self.next_indexes[-1] + 1) if self.next_indexes else 0
                if not self.status.loop_pl and len(self.entries) <= i:
                    break
                self.next_indexes.append(i % len(self.entries))
        self._load_streaming_data()
        

    def _load_streaming_data(self, count = 2):
        '''
        先にロードしておく
        '''
        for i in range(min(len(self.next_indexes), count)):
            self.entries[self.next_indexes[i]].check_streaming_data.create_task()



    async def set_next_index_from_videoID(self, video_id: str):
        for i, entry in enumerate(self.entries):
            if entry.video_id() == video_id:
                self.next_indexes.clear()
                self.next_indexes.append(i)
                if not await entry.is_available():
                    entry.check_streaming_data.create_task()
                break


    async def rewind(self, count:int = 1) -> int:
        """再生済みのindexを巻き戻す

        Parameters
        ----------
        count : int, optional
            正の数のみ対応, by default 1

        Returns
        -------
        int
            巻き戻しても余った個数
        """
        rewind_count = min(len(self.play_history), count)
        for _ in range(rewind_count):
            self.next_indexes.appendleft( self.play_history.pop())

        self._update_cooldowns()
        for i in range(min(2, len(self.next_indexes))):
            self.entries[self.next_indexes[i]].check_streaming_data.create_task()
        return count - rewind_count



    async def next(self, count:int = 1) -> int:
        """
        indexを進める 動画のロードはしない

        Parameters
        ----------
        count : int
            飛ばす数 正の値のみ対応

        Returns
        -------
        int
            スキップしても余った数
        """
        await self.update_next_indexies(count + 25)
        for _ in range(count):
            if not self.next_indexes: return count - _
            self.play_history.append(self.next_indexes.popleft())
            if not self.next_indexes: return count - _

        self._load_streaming_data()
        self._update_cooldowns()
        return 0
    
    
    def _update_cooldowns(self):
        if self.next_indexes:
            for _ in range(len(self.cooldowns)):
                if _ == self.next_indexes[0]:
                    self.cooldowns[_] = 0
                else:
                    self.cooldowns[_] += 1


    async def get_now_entry(self) -> "YTDLPAudioData | None":
        if not self.next_indexes:
            await self.update_next_indexies()
        if self.next_indexes:
            now_entry = self.entries[self.next_indexes[0]]
            await now_entry.check_streaming_data.run()
            if await now_entry.is_available():
                return now_entry
            else:
                await self.next()
                return await self.get_now_entry()
        return None


class LazyPlaylist(Playlist):
    """動的にplaylistのentryを読み込み

    ジェネレーター解答タスクが動いている間:
        random_pl = True:
            get_now_entryが呼び出されるときに次の曲を決める
            next_indexies[0]に格納しておく lenは1


    Parameters
    ----------
    Playlist : _type_
        _description_
    """
    def __init__(self, first_entry:dict[str, Any], generator:AsyncGenWrapper, guild_info:"DataInfo|None"):
        super().__init__(first_entry.get("playlist_title", "No Title"), first_entry.get("playlist_webpage_url", ""), guild_info)
        self.entries.append(YTDLPAudioData(first_entry, self.guild_info, self))

        async def decompres_task_func():
            async for entry in generator:
                if (entry.get("duration") == None and entry.get("channel") == None and entry.get("view_count") == None):
                    continue
                self.entries.append(YTDLPAudioData(entry, self.guild_info, self))
        self.decompres_task = asyncio.create_task(decompres_task_func())

        async def callback():
            self._adaptation()()
            await self.update_next_indexies()
        self.decompres_task.add_done_callback(lambda x : asyncio.create_task(callback()))


    def _adaptation(self: Callable|"LazyPlaylist") -> Callable:
        def wrapper(_self: "LazyPlaylist", *args, **kwargs):
            _self.random.set_range(len(_self.entries))
            max_value = max(_self.cooldowns) if _self.cooldowns else 0
            for _ in range(len(_self.entries) - len(_self.cooldowns)):
                _self.cooldowns.append(max_value)
            if isinstance(self, Callable):
                return self(_self, *args, **kwargs)
            
        if isinstance(self, Callable):
            return wrapper
        else:
            return lambda : wrapper(self)
        

    async def _wait_load_entry(self, i:int):
        while len(self.entries) <= i and not self.decompres_task.done():
            await asyncio.sleep(0.05)


    async def update_next_indexies(self, length:int=25) -> None:
        if self.decompres_task.done():
            return await super().update_next_indexies(length)
        
        # ジェネレーターが解析し終わっていない状況でnext_indexies作成できない
        if self.status.random_pl:
            return
        while len(self.next_indexes) < length:
            i = (self.next_indexes[-1] + 1) if self.next_indexes else 0
            await self._wait_load_entry(i)
            if not self.status.loop_pl and i >= len(self.entries):
                break
            self.next_indexes.append(i % len(self.entries))
        
        # 先にロードしておく
        self._load_streaming_data()


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


    @_adaptation
    async def rewind(self, count:int = 1) -> int:
        return await super().rewind(count)


    @_adaptation
    async def next(self, count:int = 1) -> int:
        if self.decompres_task.done():
            return await super().next(count)
        
        if self.status.random_pl:
            #空っぽにしといてget_now_entryが呼び出されたときにrandomでチョイスする
            if self.next_indexes:
                self.next_indexes.popleft()
            return 0
        else:
            i = self.next_indexes[0] + count + 1
            await self._wait_load_entry(i)
            return await super().next(count)        


    @_adaptation
    async def get_now_entry(self) -> "YTDLPAudioData | None":
        if (not self.decompres_task.done() and self.status.random_pl and not self.next_indexes):
            await self._wait_load_entry(10)
            i = self.random.next()
            self.next_indexes.append(i)
        if self.next_indexes:
            await self._wait_load_entry(self.next_indexes[0])
        return await super().get_now_entry()
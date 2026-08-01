import asyncio
from collections import deque
from typing import TYPE_CHECKING, Any, Callable

from pi_yo_8.music_control.utils import Status, PlaylistRandom
from pi_yo_8.utils import AsyncGenWrapper
from pi_yo_8.yt_dlp.audio_data import YTDLPAudioData

if TYPE_CHECKING:
    from pi_yo_8.main import GuildSession

class Playlist:
    def __init__(self, playlist_title: str, playlist_url: str, guild_session: "GuildSession | None", loop=False, loop_pl=True, random_pl=False):
        """
        entriesは常に1つ以上ある
        """
        self.title = playlist_title
        self.url = playlist_url
        self.guild_session = guild_session
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
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.update_next_indexes())
            except RuntimeError:
                pass


    async def update_next_indexes(self, length: int = 25) -> None:
        '''
        next_indexesをlength個まで補充する
        再生可能なものがない場合はlength以下になる
        '''
        if self.status.random_pl:
            while len(self.next_indexes) < length:
                self.next_indexes.append(self.random.select_next_index())
                
        else:
            while len(self.next_indexes) < length:
                i = (self.next_indexes[-1] + 1) if self.next_indexes else 0
                if not self.status.loop_pl and len(self.entries) <= i:
                    break
                self.next_indexes.append(i % len(self.entries))
        self._preload_upcoming_entries()

        
    def _preload_upcoming_entries(self, count = 2):
        '''先にロードしておく'''
        for i in range(min(len(self.next_indexes), count)):
            self.entries[self.next_indexes[i]].check_streaming_data.create_task()


    async def set_next_index_by_video_id(self, video_id: str):
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



    async def next(self, count: int = 1) -> int:
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
        await self.update_next_indexes(count + 25)
        for _ in range(count):
            if not self.next_indexes: return count - _
            self.play_history.append(self.next_indexes.popleft())
            if not self.next_indexes: return count - _

        self._preload_upcoming_entries()
        self._update_cooldowns()
        return 0
    
    
    def _update_cooldowns(self):
        if self.next_indexes:
            for _ in range(len(self.cooldowns)):
                if _ == self.next_indexes[0]:
                    self.cooldowns[_] = 0
                else:
                    self.cooldowns[_] += 1


    async def get_current_entry(self) -> "YTDLPAudioData | None":
        if not self.next_indexes:
            await self.update_next_indexes()

        if self.next_indexes:
            current_entry = self.entries[self.next_indexes[0]]
            await current_entry.check_streaming_data.run()
            if await current_entry.is_available():
                return current_entry
            else:
                await self.next()
                return await self.get_current_entry()
        return None


class LazyPlaylist(Playlist):
    """動的にplaylistのentryを読み込み

    ジェネレーター解答タスクが動いている間:
        random_pl = True:
            get_current_entryが呼び出されるときに次の曲を決める
            next_indexes[0]に格納しておく lenは1
    """
    def __init__(self, first_entry: dict[str, Any], generator: AsyncGenWrapper, guild_session: "GuildSession | None"):
        super().__init__(first_entry.get("playlist_title", "No Title"), first_entry.get("playlist_webpage_url", ""), guild_session)
        self.entries.append(YTDLPAudioData(first_entry, self.guild_session, self))

        async def decompress_task_func():
            async for entry in generator:
                if (entry.get("duration") is None and entry.get("channel") is None and entry.get("view_count") is None):
                    continue
                self.entries.append(YTDLPAudioData(entry, self.guild_session, self))
        self.decompress_task = asyncio.create_task(decompress_task_func())

        async def callback():
            self._adapt_cooldowns()()
            await self.update_next_indexes()
        self.decompress_task.add_done_callback(lambda x: asyncio.create_task(callback()))


    def _adapt_cooldowns(self: Callable | "LazyPlaylist") -> Callable:
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
            return lambda: wrapper(self)


    async def _wait_load_entry(self, entry_index: int):
        while len(self.entries) <= entry_index and not self.decompress_task.done():
            await asyncio.sleep(0.05)


    async def update_next_indexes(self, length: int = 25) -> None:
        if self.decompress_task.done():
            return await super().update_next_indexes(length)

        
        # ジェネレーターが解析し終わっていない状況でnext_indexes作成できない
        if self.status.random_pl:
            return
        while len(self.next_indexes) < length:
            i = (self.next_indexes[-1] + 1) if self.next_indexes else 0
            await self._wait_load_entry(i)
            if not self.status.loop_pl and i >= len(self.entries):
                break
            self.next_indexes.append(i % len(self.entries))
        
        # 先にロードしておく
        self._preload_upcoming_entries()


    async def set_next_index_by_video_id(self, video_id: str):
        entry_index = 0
        while True:
            await self._wait_load_entry(entry_index)
            if len(self.entries) <= entry_index:
                return

            entry = self.entries[entry_index]
            if entry.video_id() == video_id:
                self.next_indexes.clear()
                self.next_indexes.append(entry_index)
                if not await entry.is_available():
                    entry.check_streaming_data.create_task()
                return
            entry_index += 1


    @_adapt_cooldowns
    async def rewind(self, count: int = 1) -> int:
        return await super().rewind(count)


    @_adapt_cooldowns
    async def next(self, count: int = 1) -> int:
        if self.decompress_task.done():
            return await super().next(count)
        
        if self.status.random_pl:
            # 空っぽにしといてget_current_entryが呼び出されたときにrandomでチョイスする
            if self.next_indexes:
                self.next_indexes.popleft()
            return 0
        else:
            target_index = self.next_indexes[0] + count + 1
            await self._wait_load_entry(target_index)
            return await super().next(count)        


    @_adapt_cooldowns
    async def get_current_entry(self) -> "YTDLPAudioData | None":
        if (not self.decompress_task.done() and self.status.random_pl and not self.next_indexes):
            await self._wait_load_entry(10)
            chosen_index = self.random.select_next_index()
            self.next_indexes.append(chosen_index)
        if self.next_indexes:
            await self._wait_load_entry(self.next_indexes[0])
        return await super().get_current_entry()
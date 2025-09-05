import asyncio
import time
from types import TracebackType
from typing import TYPE_CHECKING

from pi_yo_8.yt_dlp.unit import YTDLPExtractor



class YTDLPWith:
    def __init__(self, option:dict={}) -> None:
        self.is_running = False
        self.ydl = YTDLPExtractor(option)

    def __enter__(self) -> "YTDLPExtractor":
        if self.is_running:
            raise RuntimeError("This yt_dlp extractor is already running")
        self.is_running = True
        self.latest_accessed = time.time()
        return self.ydl
    
    def __exit__(self, exc_type: type, exc_value: Exception, traceback: TracebackType) -> None:
        self.is_running = False


class YTDLPManager:
    def __init__(self):

        self.free_ftdlp: list[YTDLPWith] = [YTDLPWith() for _ in range(2)]
        self.special_ftdlp: dict[str, YTDLPWith] = {}


    def get(self, id:str ="") -> "YTDLPWith":
        if id:
            return self._get_special_ftdlp(id)
        return self._get_free_ftdlp()
    

    def _get_free_ftdlp(self):
        from pi_yo_8.utils import FREE_THREADS
    
        for ytdlp in self.free_ftdlp:
            if not ytdlp.is_running:
                if ytdlp == self.free_ftdlp[-1]:
                    asyncio.get_event_loop().run_in_executor(FREE_THREADS, self._add_ftdlp)
                return ytdlp
        return self._add_ftdlp()


    def _get_special_ftdlp(self, id:str) -> "YTDLPWith":
        if id in self.special_ftdlp:
            return self.special_ftdlp[id]
        return self._add_ftdlp(id, option={}) 


    def _add_ftdlp(self, id:str="", option:dict={}) -> "YTDLPWith":
        
        is_special = bool(option)
        ftdlp = YTDLPWith(option)
        if is_special:
            self.special_ftdlp[id] = ftdlp
        else:
            self.free_ftdlp.append(ftdlp)
        return ftdlp
    

YT_DLP = YTDLPManager()
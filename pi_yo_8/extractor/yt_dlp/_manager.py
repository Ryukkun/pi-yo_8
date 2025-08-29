import asyncio
from pi_yo_8.extractor.yt_dlp import YTDLPExtractor
from pi_yo_8.utils import FREE_THREADS


class YTDLPManager:
    def __init__(self):
        self.free_ftdlp: list[YTDLPExtractor] = [YTDLPExtractor() for _ in range(2)]
        self.special_ftdlp: dict[str, YTDLPExtractor] = {}


    def get(self, id:str ="") -> YTDLPExtractor:
        if id:
            return self._get_special_ftdlp(id)
        return self._get_free_ftdlp()
    

    def _get_free_ftdlp(self):
        for ytdlp in self.free_ftdlp:
            if not ytdlp.is_running:
                if ytdlp == self.free_ftdlp[-1]:
                    asyncio.get_event_loop().run_in_executor(FREE_THREADS, self._add_ftdlp)
                return ytdlp
        return self._add_ftdlp()


    def _get_special_ftdlp(self, id:str) -> YTDLPExtractor:
        if id in self.special_ftdlp:
            return self.special_ftdlp[id]
        return self._add_ftdlp(id, option={}) 


    def _add_ftdlp(self, id:str="", option:dict={}) -> YTDLPExtractor:
        is_special = bool(option)
        ftdlp = YTDLPExtractor(option)
        if is_special:
            self.special_ftdlp[id] = ftdlp
        else:
            self.free_ftdlp.append(ftdlp)
        return ftdlp
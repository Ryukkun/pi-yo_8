import time
from types import TracebackType

from pi_yo_8.yt_dlp.unit import YTDLP_GENERAL_PARAMS, YTDLP_VIDEO_PARAMS, YTDLPExtractor



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
    YT_DLP:"YTDLPManager" = None # type: ignore
    def __init__(self):
        self.ytdlp: dict[str, list[YTDLPWith]] = {
            str(YTDLP_GENERAL_PARAMS): [YTDLPWith(YTDLP_GENERAL_PARAMS) for _ in range(6)],
            str(YTDLP_VIDEO_PARAMS): [YTDLPWith(YTDLP_VIDEO_PARAMS) for _ in range(6)],
        }


    @classmethod
    def initiallize(cls):
        c = cls()
        YTDLPManager.YT_DLP = c


    def get(self, opts:dict) -> "YTDLPWith":
        _key = str(opts)
        if _key in self.ytdlp:
            for ytdlp in self.ytdlp[_key]:
                if not ytdlp.is_running:
                    return ytdlp
        else:
            self.ytdlp[_key] = []

        new_ytdlp = YTDLPWith(opts)
        self.ytdlp[_key].append(new_ytdlp)
        return new_ytdlp
    


import atexit
import threading

from pi_yo_8.sources.extractor import YTDLP_GENERAL_PARAMS, YTDLP_VIDEO_PARAMS, YTDLPExtractor


class YTDLPManager:
    YT_DLP: "YTDLPManager" = None  # type: ignore

    def __init__(self, general_pool_size: int = 4, video_pool_size: int = 4):
        self._lock = threading.Lock()
        self.ytdlp: dict[str, list[YTDLPExtractor]] = {
            str(YTDLP_GENERAL_PARAMS): [YTDLPExtractor(YTDLP_GENERAL_PARAMS) for _ in range(general_pool_size)],
            str(YTDLP_VIDEO_PARAMS): [YTDLPExtractor(YTDLP_VIDEO_PARAMS) for _ in range(video_pool_size)],
        }

    @classmethod
    def initialize(cls, general_pool_size: int = 4, video_pool_size: int = 4) -> None:
        cls.YT_DLP = cls(general_pool_size, video_pool_size)

    @classmethod
    def get_extractor(cls, options: dict) -> YTDLPExtractor:
        if cls.YT_DLP is None:
            cls.initialize()
        return cls.YT_DLP.get(options)

    @classmethod
    def shutdown_all(cls) -> None:
        if cls.YT_DLP is not None:
            cls.YT_DLP.shutdown()

    def shutdown(self) -> None:
        with self._lock:
            all_extractors = [e for pool in self.ytdlp.values() for e in pool]
            for extractor in all_extractors:
                try:
                    extractor.connection.close()
                except Exception:
                    pass
                if extractor.process.is_alive():
                    try:
                        extractor.process.terminate()
                    except Exception:
                        pass
            for extractor in all_extractors:
                if extractor.process.is_alive():
                    try:
                        extractor.process.join(timeout=0.2)
                    except Exception:
                        pass
            self.ytdlp.clear()

    def get(self, options: dict) -> YTDLPExtractor:
        _key = str(options)
        with self._lock:
            if _key in self.ytdlp:
                for ytdlp in self.ytdlp[_key]:
                    if not ytdlp.is_running and ytdlp.process.is_alive():
                        ytdlp.is_running = True
                        return ytdlp
            else:
                self.ytdlp[_key] = []

            new_ytdlp = YTDLPExtractor(options)
            new_ytdlp.is_running = True
            self.ytdlp[_key].append(new_ytdlp)
            return new_ytdlp


atexit.register(YTDLPManager.shutdown_all)


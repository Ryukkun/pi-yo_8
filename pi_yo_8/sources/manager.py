from pi_yo_8.sources.extractor import YTDLP_GENERAL_PARAMS, YTDLP_VIDEO_PARAMS, YTDLPExtractor


class YTDLPManager:
    YT_DLP: "YTDLPManager" = None  # type: ignore

    def __init__(self, general_pool_size: int = 4, video_pool_size: int = 4):
        self.ytdlp: dict[str, list[YTDLPExtractor]] = {
            str(YTDLP_GENERAL_PARAMS): [YTDLPExtractor(YTDLP_GENERAL_PARAMS) for _ in range(general_pool_size)],
            str(YTDLP_VIDEO_PARAMS): [YTDLPExtractor(YTDLP_VIDEO_PARAMS) for _ in range(video_pool_size)],
        }

    @classmethod
    def initialize(cls, general_pool_size: int = 4, video_pool_size: int = 4) -> None:
        cls.YT_DLP = cls(general_pool_size, video_pool_size)

    def get(self, options: dict) -> YTDLPExtractor:
        _key = str(options)
        if _key in self.ytdlp:
            for ytdlp in self.ytdlp[_key]:
                if not ytdlp.is_running:
                    return ytdlp
        else:
            self.ytdlp[_key] = []

        new_ytdlp = YTDLPExtractor(options)
        self.ytdlp[_key].append(new_ytdlp)
        return new_ytdlp

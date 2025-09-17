from pi_yo_8.yt_dlp.unit import YTDLP_GENERAL_PARAMS, YTDLP_VIDEO_PARAMS, YTDLPExtractor



class YTDLPManager:
    YT_DLP:"YTDLPManager" = None # type: ignore
    def __init__(self):
        self.ytdlp: dict[str, list[YTDLPExtractor]] = {
            str(YTDLP_GENERAL_PARAMS): [YTDLPExtractor(YTDLP_GENERAL_PARAMS) for _ in range(6)],
            str(YTDLP_VIDEO_PARAMS): [YTDLPExtractor(YTDLP_VIDEO_PARAMS) for _ in range(6)],
        }


    @classmethod
    def initiallize(cls):
        c = cls()
        YTDLPManager.YT_DLP = c


    def get(self, opts:dict) -> "YTDLPExtractor":
        _key = str(opts)
        if _key in self.ytdlp:
            for ytdlp in self.ytdlp[_key]:
                if not ytdlp.is_running:
                    return ytdlp
        else:
            self.ytdlp[_key] = []

        new_ytdlp = YTDLPExtractor(opts)
        self.ytdlp[_key].append(new_ytdlp)
        return new_ytdlp
    


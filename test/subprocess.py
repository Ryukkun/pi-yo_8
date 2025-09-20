import asyncio
import time
from typing import Any


class YTDLPExtractor:
    YTDLP_GENERAL_PARAMS = ['yt-dlp', '--skip-download', '-f', '"bestaudio/worst"', '--default-search', '"ytsearch30"', '--flat-playlist', '--lazy-playlist', '-j']
    YTDLP_VIDEO_PARAMS = ['yt-dlp', '--skip-download', '--format', '"bestaudio/worst"', '--default-search', '"ytsearch30"', '--flat-playlist', '--no-playlist', '-J']
    YTDLP_CHANNEL_PARAMS = ['yt-dlp', '--skip-download', '--flat-playlist', '--no-playlist', '-J']
    def __init__(self):
        """
        Parameters
        ----------
        opts : dict
            yt-dlp に渡すオプション ログイン情報の想定
        """

    

    async def _extract_info(self) -> dict[str, Any] | None:
        """
        yt-dlp対応サイトの解析情報を出力
        youtubeのplaylistを解析するときはprocess=False かつ URLが...youtube.com/playlist?list...であるとジェネレーターになる。
        """
        arg = "https://www.youtube.com/watch?v=cQKGUgOfD8U&list=PLB02wINShjkBKnLfufaEPnCupGO-SK6e4&index=4"
        #arg = "https://www.youtube.com/playlist?&list=PLB02wINShjkBKnLfufaEPnCupGO-SK6e4&index=4"
        #arg = "https://www.nicovideo.jp/mylist/21130988"
        arg = "https://youtu.be/x06wB8UDxMI?si=yEw3s0RAISEH4Iu4"
        #arg = "https://www.nicovideo.jp/watch/sm36999938"
        #arg = "https://www.youtube.com/watch?v=Y1Nip-y0BcQ&list=PLYITQsyLyAGkqp1e18fF22RbsisWzXazN" #再生不可能なものが入っている
        #arg = "ytsearch50:ディぺっしゅモード"
        #arg = "ytsearch50:ジブリBGM playlist"
        #arg = "じぶりBGM playlist"
        #arg = "https://www.youtube.com/channel/UCGmO0S4S-AunjRdmxA6TQYg" # Channel
        cmd = self.YTDLP_GENERAL_PARAMS.copy()
        cmd.append(arg)
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE)
        if not proc.stdout:
            return
        while not proc.stdout.at_eof():
            stdout = await proc.stdout.readline()
            print(stdout.decode())
        

if __name__ == "__main__":
    t = YTDLPExtractor()
    asyncio.run(t._extract_info())
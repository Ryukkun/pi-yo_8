import asyncio
from yt_dlp import YoutubeDL
from typing import TYPE_CHECKING

from _ie import YoutubeIE
from pi_yo_8.music_control._playlist import GeneratorPlaylist, Playlist
from pi_yo_8.utils import FREE_THREADS


if TYPE_CHECKING:
     from pi_yo_8.audio_data import YTDLPAudioData

class YTDLPExtractor:
    YTDLP_PARAMS = {
        'format':'bestaudio/worst',
        "default_search":"ytsearch30",
        'extract_flat':"in_playlist",
        'quiet':True,
        'skip_download': True
    }
    def __init__(self, opts:dict={}) -> None:
        """
        Parameters
        ----------
        opts : dict
            yt-dlp に渡すオプション ログイン情報の想定
        """
        self.opts: dict = opts
        self.opts.update(self.YTDLP_PARAMS)


    def _get_ytdlp(self) -> YoutubeDL:
        ydl = YoutubeDL(self.opts)
        ydl.add_info_extractor(YoutubeIE())
        return ydl


    async def extract_info(self, url: str) -> YTDLPAudioData| Playlist | None:
        """
        yt-dlpで動画を解析。Youtube以外も想定
        """
        info = await self._extract_info(url)

        if info:
            if 'entries' in info and info['entries']:
                return Playlist([YTDLPAudioData(entry) for entry in info['entries']])
            elif "formats" in info and 'url' in info:
                if (thmb := info.get('thumbnails')) and isinstance(thmb, list):
                    thmb.sort(key=lambda t:(
                        t.get("preference", -100),
                        t.get("width", 0) * t.get("height", 0)  #解像度
                    ), reverse=True)
                return YTDLPAudioData(info)
            
        return None


    async def extract_yt_playlist_info(self, _id:str) -> GeneratorPlaylist | None:
        """
        yt-dlp を使用してYoutubeのプレイリストを取得する

        Returns
        -------
        Playlist
            取得したプレイリストの動画情報 失敗した場合は None
        """
        url = f'https://www.youtube.com/playlist?list={_id}'
        # yt-dlp load playlist
        info = await self._extract_info(url, process=False)

        if info and 'entries' in info:
            return GeneratorPlaylist(info)
        return None
        # to cls
        # res = []
        # for _ in entries:
        #     if _['title'] == '[Private video]' and not _['duration']:
        #         continue
        #     res.append(YTDLPAudioData(_['id'], video_id=_['id'], title=_['title']))
        # return res
    

    async def _extract_info(self, url: str, process: bool = True) -> dict | None:
        """
        yt-dlp対応サイトの解析情報を出力
        youtubeのplaylistを解析するときはprocess=False かつ URLが...youtube.com/playlist?list...であるとジェネレーターになる。
        """
        def main():
            try:
                return self._get_ytdlp().extract_info(url, download=False, process=process)
            except:
                return None
        return await asyncio.get_event_loop().run_in_executor(FREE_THREADS, main)
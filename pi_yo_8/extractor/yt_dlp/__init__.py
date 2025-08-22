import asyncio
from yt_dlp import YoutubeDL
from typing import TYPE_CHECKING, Any, Generator

from _ie import YoutubeIE
from pi_yo_8.audio_data import GenericAudioData
from pi_yo_8.music_control._playlist import Playlist


if TYPE_CHECKING:
     from pi_yo_8.audio_data import YoutubeAudioData

class YTDLPExtractor:
    @staticmethod
    async def load_video(url: str) -> YoutubeAudioData | GenericAudioData | None:
        """
        yt-dlpで動画を解析。Youtube以外も想定
        """
        def io() -> dict | None:
            try:
                with YoutubeDL({'format':'bestaudio/worst', 'quiet':True, 'noplaylist':True, 'skip_download': True}) as ydl:
                    ydl.add_info_extractor(YoutubeIE())
                    return ydl.extract_info(url, download=False)
            except:
                return None

        video_info = await asyncio.get_event_loop().run_in_executor(None, io)
        if video_info is None:
            return None
        elif "youtu" in video_info["extractor_key"].lower():
            return YTDLPExtractor._yt_format(video_info)
        else:
            return YTDLPExtractor._generic_format(video_info)

    @classmethod
    def _yt_format(video_info) -> YoutubeAudioData:
            from pi_yo_8.audio_data import YoutubeAudioData
            if (upload_date := video_info.get('upload_date', None)) is not None:
                upload_date=f'{upload_date[:4]}/{upload_date[4:6]}/{upload_date[6:]}'
            if (volume := video_info.get('volume_data', {}).get('perceptualLoudnessDb', None)) is not None:
                volume = -14 - volume
            return YoutubeAudioData(video_id=video_info["id"],
                             title=video_info["title"],
                             st_url=video_info['url'],
                             st_sec=int(video_info["duration"]),
                             volume=volume,
                             view_count=video_info.get('view_count', None),
                             like_count=video_info.get('like_count', None),
                             upload_date=upload_date,
                             ch_id=video_info.get("channel_id", None),
                             ch_name=video_info.get("channel", None))


    @classmethod
    def _generic_format(video_info:dict) -> GenericAudioData:
        web_url = video_info.get('webpage_url', None)
        if web_url is None:
            web_url = video_info.get('original_url', "None")
        return GenericAudioData(st_url=video_info['url'],
                                web_url=web_url,
                                title=video_info['title'])



    @staticmethod
    async def ytdlp_playlist(_id:str) -> Playlist:
        """
        yt-dlp を使用してYoutubeのプレイリストを取得する

        Parameters
        ----------
        _id : str
            YoutubeのプレイリストID

        Returns
        -------
        Playlist
            取得したプレイリストの動画情報 失敗した場合は None
        """
        url = f'https://www.youtube.com/playlist?list={_id}'
        def main() -> Generator[dict[str, Any] | Any, Any, None] | None:
            # yt-dlp load playlist
            try:
                with YoutubeDL({'quiet':True, 'skip_download': True}) as ydl:
                    info = ydl.extract_info(url, download=True, process=False, ie_key="YoutubeTab")
                    return info["entries"]
            except:
                return None

        loop = asyncio.get_event_loop()
        entries = await loop.run_in_executor(None, main)

        if entries is None:
            return None
        
        # to cls
        res = []
        for _ in entries:
            if _['title'] == '[Private video]' and not _['duration']:
                continue
            res.append(YoutubeAudioData(_['id'], video_id=_['id'], title=_['title']))
        return res
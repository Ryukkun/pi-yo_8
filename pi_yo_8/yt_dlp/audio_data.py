import asyncio
from typing import Any

from discord import FFmpegOpusAudio, FFmpegPCMAudio
from pi_yo_8.type import Thumbnail
from pi_yo_8.utils import is_url_accessible, task_running_wrapper
from pi_yo_8.voice_client import StreamAudioData
from pi_yo_8.yt_dlp.manager import YTDLPManager
from pi_yo_8.yt_dlp.unit import YTDLP_VIDEO_PARAMS



class YTDLPAudioData(StreamAudioData):
    def __init__(self, info:dict[str, Any]):
        self.info = info
        self.ch_icon: str | None = None
        self.thumbnail:str | None = None

        self.load_thumbnail.create_task()
        if "url" in info:
            super().__init__(info['url'], self.get_volume(), self.get_duration())

    def web_url(self) -> str:
        ret = self.info.get("webpage_url", None)
        if not ret:
            ret = self.info.get("original_url", self.info["url"])
        return ret

    def title(self) -> str:
        ret = self.info.get("title", "No Title")
        if not ret:
            ret = self.web_url()
        return ret

    def get_volume(self) -> float | None:
        if (volume := self.info.get('volume_data', {}).get('perceptualLoudnessDb', None)) is not None:
            return -14.0 - float(volume)

    def get_duration(self) -> int | None:
        return self.info.get("duration", None)
    
    def video_id(self) -> str | None:
        return self.info.get("id", None)
    
    def view_count(self) -> int | None:
        return self.info.get("view_count", None)

    def like_count(self) -> int | None:
        return self.info.get("like_count", None)

    def upload_date(self) -> str | None:
        if (upload_date := self.info.get('upload_date', None)) is not None:
            upload_date=f'{upload_date[:4]}/{upload_date[4:6]}/{upload_date[6:]}'
        return upload_date
    
    def ch_id(self) -> str | None:
        return self.info.get("uploader_id", None)

    def ch_url(self) -> str | None:
        return self.info.get("uploader_url", None)

    def ch_name(self) -> str | None:
        return self.info.get("uploader", None)
    
    def formats(self) -> list[dict[str, Any]]:
        return self.info.get("formats", [])

    @task_running_wrapper()
    async def load_ch_icon(self) -> str | None:
        if not self.ch_icon:
            if (ch_url := self.ch_url()):
                print("load ch icon:", ch_url)
                info_generator = YTDLPManager.YT_DLP.get(YTDLP_VIDEO_PARAMS).extract_raw_info(ch_url)
                if info := await anext(info_generator, None):
                    _ = YTDLPAudioData(info)
                    self.ch_icon = await _.load_thumbnail.run()
                print("load ch icon fin:", ch_url)
        return self.ch_icon
    
    @task_running_wrapper()
    async def load_thumbnail(self) -> str | None:
        if not self.thumbnail:
            thumbnails:list[Thumbnail] = self.info.get("thumbnails", [{"url":None}])
            for thumb in reversed(thumbnails):
                if (url := thumb.get("url", None)) and await is_url_accessible(url):
                    self.thumbnail = url
                    break
        return self.thumbnail


    async def is_available(self) -> bool:
        """
        利用可能か利用可能かどうかをチェックする
        最悪5秒程度かかる
        """
        if self.formats():
            return await is_url_accessible(self.stream_url, self.info.get("http_headers"), self.info.get("cookies"))
        return False


    @task_running_wrapper()
    async def check_streaming_data(self):
        """
        音声ファイル直のURLを取得する
        投げっぱなし可能
        """
        if await self.is_available():
            return
        
        self.load_ch_icon.create_task()
        
        print("check stream data:", self.web_url())
        info_generator = YTDLPManager.YT_DLP.get(YTDLP_VIDEO_PARAMS).extract_raw_info(self.web_url())
        info = await anext(info_generator, None)
        if info and info.get("formats"):
            self.info = info
            self.stream_url = self.info['url']
            self.duration = self.get_duration()
            self.volume = self.get_volume()
        print("check stream data fin:", self.web_url())

            
    def _get_ffmpegaudio(self, opus: bool, before_options: list[str], options: list[str]) -> FFmpegOpusAudio | FFmpegPCMAudio:
        if isinstance(self, YTDLPAudioData):
            #headers
            if headers := self.info.get("http_headers"):
                for k, v in headers.items():
                    before_options.append('-headers')
                    before_options.append(f'"{k}: {v}"')
            #cookies
            if cookies := self.info.get("cookies"):
                before_options.append('-headers')
                before_options.append(f'"Cookie: {cookies}"')
        return super()._get_ffmpegaudio(opus, before_options, options)
from typing import Any
from pi_yo_8.utils import is_url_accessible, task_running_wrapper
from pi_yo_8.voice_client import StreamAudioData
from pi_yo_8.yt_dlp.manager import YTDLPManager
from pi_yo_8.yt_dlp.unit import YTDLP_VIDEO_PARAMS



class YTDLPAudioData(StreamAudioData):
    def __init__(self, info:dict[str, Any]):
        self.info = info
        self._ch_icon: str | None = None
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
    async def ch_icon(self) -> str | None:
        if self._ch_icon:
            return self._ch_icon
        
        if (ch_url := self.ch_url()) is not None:
            result = await YTDLPManager.YT_DLP.get(YTDLP_VIDEO_PARAMS).extract_info(ch_url)
            self._ch_icon = result.get_thumbnail() if (result and isinstance(result, YTDLPAudioData)) else None
        return self._ch_icon
    

    def get_thumbnail(self) -> str | None:
        return self.info.get("thumbnails", [{"url":None}])[0]["url"]


    async def is_available(self) -> bool:
        """
        利用可能か利用可能かどうかをチェックする
        最悪5秒程度かかる
        """
        if self.formats():
            return await is_url_accessible(self.stream_url)
        return False
    

    @task_running_wrapper()
    async def check_streaming_data(self):
        """
        音声ファイル直のURLを取得する
        投げっぱなし可能
        """
        if self._ch_icon == None and not self.ch_icon.is_running():
            self.ch_icon.create_task()

        if await self.is_available():
            return
        
        result = await YTDLPManager.YT_DLP.get(YTDLP_VIDEO_PARAMS).extract_info(self.web_url())
        if result and isinstance(result, YTDLPAudioData):
            self.info = result.info
            self.stream_url = self.info['url']
            self.duration = self.get_duration()
            self.volume = self.get_volume()
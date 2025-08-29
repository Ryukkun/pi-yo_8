from typing import Any
from pi_yo_8.utils import YT_DLP, is_url_accessible, task_running_wrapper
from pi_yo_8.voice_client import StreamAudioData



class YTDLPAudioData(StreamAudioData):
    def __init__(self, info:dict[str, Any]):
        self.info = info
        self._ch_icon: str | None = None
        if (volume := info.get('volume_data', {}).get('perceptualLoudnessDb', None)) is not None:
            volume = -14 - volume
        super().__init__(info['url'], volume)

    def web_url(self) -> str:
        ret = self.info.get("webpage_url", None)
        if not ret:
            ret = self.info.get("original_url", "")
        return ret

    def title(self) -> str:
        ret = self.info.get("title", "No Title")
        if not ret:
            ret = self.web_url()
        return ret

    def duration(self) -> int | None:
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

    async def ch_icon(self) -> str | None:
        if self._ch_icon is None and (ch_url := self.ch_url()) is not None:
            with YT_DLP.get() as ydl:
                result = await ydl._extract_info(ch_url, process=False)
            if result:
                self._ch_icon = result.get("thumbnails", [""])[0]
            else:
                self._ch_icon = ""
        return self._ch_icon
    
    def get_thumbnail(self) -> str | None:
        return self.info.get("thumbnails", [None])[0]

    async def is_available(self) -> bool:
        """
        利用可能か利用可能かどうかをチェックする
        最悪5秒程度かかる
        """
        if self.stream_url:
            return await is_url_accessible(self.stream_url)
        return False
    

    @task_running_wrapper()
    async def update_streaming_data(self):
        """
        音声ファイル直のURLを取得する
        投げっぱなし可能
        """
        with YT_DLP.get() as ydl:
            info = await ydl._extract_info(self.web_url())
        if info:
            self.info = info
            self.stream_url = info['url']
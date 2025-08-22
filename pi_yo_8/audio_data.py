from typing import Optional

from pi_yo_8.utils import YoutubeUtil, is_url_accessible, task_running_wrapper
from pi_yo_8.voice_client import StreamAudioData



class GenericAudioData(StreamAudioData):
    def __init__(self,
                 st_url:str,
                 web_url:str,
                 volume:Optional[int] = None,
                 title:Optional[str] = None):
        super().__init__(st_url, volume)
   
        self.web_url = web_url
        self.title = title if title else self.web_url



class YoutubeAudioData(StreamAudioData):
    def __init__(self,
                 video_id:str,
                 title:str,
                 st_url:Optional[str] = None,
                 st_sec:Optional[int] = None,
                 volume:Optional[int] = None,
                 view_count:Optional[int] = None,
                 like_count:Optional[int] = None,
                 upload_date:Optional[str] = None,
                 ch_id:Optional[str] = None,
                 ch_name:Optional[str] = None,
                 ch_icon:Optional[str] = None):
        super().__init__(st_url, YoutubeUtil.get_web_url(video_id), volume, title)

        # video detail
        self.st_sec = st_sec
        self.video_id = video_id
        self.view_count = view_count
        self.like_count = like_count
        self.upload_date = upload_date

        # channel detail
        self.ch_id = ch_id
        self.ch_url = YoutubeUtil.get_ch_url(ch_id)
        self.ch_name = ch_name
        self.ch_icon = ch_icon


    async def is_available(self) -> bool:
        """
        利用可能か利用可能かどうかをチェックする
        最悪5秒程度かかる
        """
        if self.st_url:
            return await is_url_accessible(self.st_url)
        return False
    

    @task_running_wrapper()
    async def update_streaming_data(self):
        """
        音声ファイル直のURLを取得する
        投げっぱなし可能
        """
        from pi_yo_8.extractor.yt_dlp import YTDLPExtractor
        new:YoutubeAudioData = await YTDLPExtractor.load_video(self.video_id)
        for key, value in new.__dict__.items():
            if value:
                self.__dict__[key] = value
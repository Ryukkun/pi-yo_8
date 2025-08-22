import re
import urllib.parse

from discord import Optional
from pi_yo_8.audio_data import GenericAudioData, StreamAudioData, YoutubeAudioData
from pi_yo_8.extractor.youtube_api import YoutubeAPIExtractor
from pi_yo_8.extractor.yt_dlp import YTDLPExtractor
from pi_yo_8.music_control._playlist import Playlist


youtube_api = 'https://www.googleapis.com/youtube/v3'

class YoutubeExtractor:
    def __init__(self, _input:str) -> None:
        self.input = _input
        self.url_parse = urllib.parse.urlparse(_input)
        self.url_query:dict = {}
        self.is_url = False
        self.is_yt = False
        self.list_id:Optional[str] = None
        self.video_id:Optional[str] = None

        if self.url_parse.query:
            self.url_query = urllib.parse.parse_qs(self.url_parse.query)
        
        self.is_url = bool(self.url_parse.hostname)
        if self.is_url:
            self.is_yt = re.match(r'^(.*?(youtube\.com|youtube-nocookie\.com)|youtu\.be)$',self.url_parse.hostname)
            if self.is_yt:
                self.list_id = self.url_query.get('list', [None])[0]
                self.video_id = self.url_query.get('v', [None])[0]
                if not self.video_id and self.url_parse.hostname == 'youtu.be':
                    self.video_id = self.url_parse.path[1:]


    async def extract_playlist(self):
        """
        .p で指定された引数を、再生可能か判別する

        再生可能だった場合
        return self

        不可
        return None
        """
        if not self.is_yt:
            raise Exception("YoutubeのURLではありません")

        if not self.list_id:
            raise Exception("このURLにはプレイリストは含まれていません")
        
        
        ### PlayList と 動画が一緒についてきた場合 --------------------------------------------------------------#
        if self.video_id:
            # Load Video in the Playlist 
            if pl := await self.load_playlist(url=self.input, _id=self.list_id):
                # Playlist Index 特定
                index = 0
                for index, temp in enumerate(pl):
                    if self.video_id in temp.video_id:
                        break

                # self.playlist = True
                # self.index = index - 1
                # self.random_pl = False
                # self.sad = pl


        ### PlayList 本体のURL ------------------------------------------------------------------------#
        else: 
            pl = await self.load_playlist(url=self.input, _id=self.list_id)
                # self.playlist = True
                # self.index = -1
                # self.random_pl = True
                # self.sad = pl 
    

    @staticmethod
    async def load_playlist(_id:str) -> Playlist:
        """
        YoutubeAPI、または yt-dlp を使用してプレイリストの情報を取得する
        """
        try:
            return await YoutubeAPIExtractor.api_playlist(_id)
        except Exception: pass
        return await YTDLPExtractor.load_playlist(_id)


    async def extract_search(self):
        """
        指定された引数を、再生可能か判別する
        
        Playlist形式
        return 'pl'
        
        単曲
        return 'video'

        不可
        return None
        """
        
        ### URLじゃなかった場合 -----------------------------------------------------------------------#
        return await YoutubeAPIExtractor.api_search_playlist(self.input)
            # self.index = -1
            # self.random_pl = False
            # self.playlist = True
    

    async def extract_video(self) -> Optional[GenericAudioData]:
        """
        指定された引数を、再生可能か判別する
        urlであればOK
        
        Playlist形式
        return 'pl'
        
        単曲
        return 'video'

        不可
        return None
        """
        if not self.is_url:
            raise Exception("URLを入力してください")
        sad = None
        ### youtube 動画オンリー -----------------------------------------------------------------------#
        sad = await YTDLPExtractor.load_video(self.input)
        
        if sad is None:
            raise Exception("音声の出力に失敗しました")

        return sad
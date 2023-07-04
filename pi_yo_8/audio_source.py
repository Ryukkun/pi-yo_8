import asyncio
import aiohttp
import urllib.parse

from typing import Optional
from yt_dlp import YoutubeDL
from yt_dlp.utils import PlaylistEntries
from yt_dlp.extractor.youtube import orderedSet
from .pytube.innertube import InnerTube
from .voice_client import _StreamAudioData

import config

youtube_api = 'https://www.googleapis.com/youtube/v3'



class AnalysisUrl:
    def __init__(self, arg:str) -> None:
        self.arg = arg
        self.playlist:Optional[bool] = False
        self.index:Optional[int] = None
        self.random_pl:Optional[bool] = None
        self.sad:Optional[StreamAudioData] = None
        self.url_parse = urllib.parse.urlparse(arg)
        self.url_query:dict = {}

        if self.url_parse.query:
            self.url_query = urllib.parse.parse_qs(self.url_parse.query)


    def is_url(self):
        return bool(self.url_parse.hostname)

    def is_yt(self):
        return ( self.url_parse.hostname in ('www.youtube.com', 'youtube.com', 'youtu.be'))

    def get_list_id(self):
        return self.url_query.get('list', [None])[0]
    
    def get_video_id(self):
        if res := self.url_query.get('v', [None])[0]:
            pass
        elif self.url_parse.hostname == 'youtu.be':
            res = self.url_parse.path[1:]
        
        return res
        


    async def video_check(self) -> 'AnalysisUrl':
        """
        .p で指定された引数を、再生可能か判別する

        再生可能だった場合
        return self

        不可
        return None
        """
        arg = self.arg
        watch_id = self.get_video_id()
        yt = self.is_yt()

        ### 文字指定
        if not self.is_url():
            self.sad = await StreamAudioData(arg).api_v_search()

        ### youtube 動画
        elif watch_id and yt:
            try: 
                self.sad = await StreamAudioData(watch_id).Pyt_V()
            except Exception as e:
                print(f"Error : Audio only 失敗 {e}")

        ### それ以外のサイト yt-dlp を使用
        else:
            try:
                self.sad = await StreamAudioData(arg).Ytdlp_V()
            except Exception as e:
                print(f"Error : Audio + Video 失敗 {e}")

        if not self.sad:return
        return self



    async def url_check(self) -> 'AnalysisUrl':
        """
        指定された引数を、再生可能か判別する
        
        Playlist形式
        return 'pl'
        
        単曲
        return 'video'

        不可
        return None
        """
        arg = self.arg
        watch_id = self.get_video_id()
        pl_id = self.get_list_id()
        yt = self.is_yt()
        
        ### URLじゃなかった場合 -----------------------------------------------------------------------#
        if not self.is_url():
            self.sad = await StreamAudioData.api_p_search(arg)
            self.index = -1
            self.random_pl = False
            self.playlist = True
    
        
        ### PlayList と 動画が一緒についてきた場合 --------------------------------------------------------------#
        elif pl_id and watch_id and yt:
            # Load Video in the Playlist 
            if pl := await StreamAudioData.load_p(url=arg, _id=pl_id):
                # Playlist Index 特定
                index = 0
                for index, temp in enumerate(pl):
                    if watch_id in temp.video_id:
                        break

                self.playlist = True
                self.index = index - 1
                self.random_pl = False
                self.sad = pl


        ### PlayList 本体のURL ------------------------------------------------------------------------#
        elif pl_id and yt: 
            if pl := await StreamAudioData.load_p(url=arg, _id=pl_id):
                self.playlist = True
                self.index = -1
                self.random_pl = True
                self.sad = pl 


        ### youtube 動画オンリー -----------------------------------------------------------------------#
        elif watch_id and yt:
            try: 
                self.sad = await StreamAudioData(watch_id).Pyt_V()
            except Exception as e:
                print(f"Error : Audio only 失敗 {e}")


        ### それ以外のサイト yt-dlp を使用 -----------------------------------------------------------------------#
        else:
            try: 
                self.sad = await StreamAudioData(arg).Ytdlp_V()
            except Exception as e:
                print(f"Error : Audio + Video 失敗 {e}")


        if not self.sad:return
        return self



class _CheckStUrl:
    def __init__(self, sad:'StreamAudioData') -> None:
        self.sad = sad
        self.task = None


    def create_task(self):
        if self.task != None:
            return

        self.task = self.sad.loop.create_task(self.sad.Pyt_V())


    async def get_url(self) -> Optional[str]:
        try:
            if not self.sad.st_url:
                if self.task == None:
                    self.create_task()

                await self.task
        except:
            pass

        return self.sad.st_url





class StreamAudioData(_StreamAudioData):
    def __init__(self,
                _input,
                **kwargs
                ):
        super().__init__(_input)
        kget = kwargs.get
        self.loop = asyncio.get_event_loop()
        
        # video id, url
        self.video_id = kget('video_id')
        self.web_url = kget('web_url')

        # video detail
        self.title = kget('title')
        self.view_count = kget('view_count')
        self.like_count = kget('like_count')
        self.upload_date = kget('upload_date')
        
        # video stream date
        self.st_vol = kget('st_vol')
        self.st_sec = kget('st_sec')
        self.st_url = kget('st_url')

        # 振り分け
        self.music = kget('music')
        self.YT = kget('None')
        
        # その他
        self.index:Optional[int] = None
        self.check_st_url = _CheckStUrl(self)
    

    async def api_get_viewcounts(self):
        if self.view_count and self.upload_date:
            return
        
        params = {'key':config.youtube_key, 'part':'statistics,snippet', 'id':self.video_id}
        url = youtube_api + '/videos'
        async with aiohttp.ClientSession() as session:
            async with session.get(url=url, params=params) as resp:
                text = await resp.json()
        text = text.get('items',[{}])[0]
        sta = text.get('statistics',{})
        self.upload_date = text.get('snippet',{}).get('publishedAt')
        if self.upload_date:
            self.upload_date = self.upload_date[:10].replace('-','/')
        self.view_count = sta.get('viewCount')
        self.like_count = sta.get('likeCount')


    async def api_v_search(self):
        params = {'key':config.youtube_key, 'part':'id', 'q':self.input, 'maxResults':'1'}
        url = youtube_api + '/search'
        async with aiohttp.ClientSession() as session:
            async with session.get(url=url, params=params) as resp:
                text = await resp.json()

        self.video_id = text['items'][0]['id']['videoId']
        self.music = True
        self.YT = True
        return await self.Pyt_V()

    @classmethod
    async def api_p_search(self, arg):
        #arg = urllib.parse.quote(arg)
        params = {'key':config.youtube_key, 'part':'id,snippet', 'q':arg, 'maxResults':'50', 'type':'video'}
        url = youtube_api + '/search'
        async with aiohttp.ClientSession() as session:
            async with session.get(url=url, params=params) as resp:
                text = await resp.json()

        return [
            self(_['id']['videoId'],
                 video_id=_['id']['videoId'],
                 title=_['snippet']['title']
                 )
            for _ in text['items']
                ]


    @classmethod
    async def load_p(cls, url, _id):
        try:
            return await cls.api_p(_id)
        except Exception: pass
        return await cls.yt_dlp_p(url)



    @classmethod
    async def api_p(cls, arg):
        params = {'key':config.youtube_key, 'part':'contentDetails,status,snippet', 'playlistId':arg, 'maxResults':'50'}
        url = youtube_api + '/playlistItems'
        res_urls = []
        i = 0
        loop = True
        async with aiohttp.ClientSession() as session:
            while loop:
                async with session.get(url=url, params=params) as resp:
                    text = await resp.json()
                    if not text['items']:
                        raise Exception('解析不可能なplaylist')
                    total = text['pageInfo']['totalResults']
                    for _ in text['items']:
                        i += 1
                        if total < i:
                            loop = False
                            break
                        if _['status']['privacyStatus'].lower() == 'private':
                            continue
                        upload_date = _['contentDetails']['videoPublishedAt'][:10].replace('-','/')
                        video_id = _['contentDetails']['videoId']
                        title = _['snippet']['title']
                        res_urls.append(cls(video_id, upload_date=upload_date, video_id=video_id, title=title))

                    if text.get('nextPageToken'):
                        params['pageToken'] = text['nextPageToken']
                    else:
                        break
        return res_urls


    @classmethod
    async def yt_dlp_p(cls, arg):
        def main():
            # yt-dlp load playlist
            key = 'YoutubeTab'
            ytd = YoutubeDL({'quiet':True})
            ie = ytd._ies[key]
            if not ie.suitable(arg):
                return
            ie = ytd.get_info_extractor(key)
            ie_result = ie.extract(arg)
            _ = PlaylistEntries(ytd, ie_result)
            entries = orderedSet(_.get_requested_items(), lazy=True)
            _, entries = tuple(zip(*list(entries))) or ([], [])
            return entries

        loop = asyncio.get_event_loop()
        entries = await loop.run_in_executor(None, main)

        # to cls
        res = []
        for _ in entries:
            if _['title'] == '[Private video]' and not _['duration']:
                continue
            res.append(cls(_['id'], video_id=_['id'], title=_['title']))
        return res



        
    # YT Video Load
    async def Pyt_V(self):
        if not self.video_id:
            self.video_id = self.input
        
        used = 'pytube'
        vdic = await InnerTube().player(self.video_id)

        if not vdic.get('streamingData'):
            used = 'pytube embed'
            vdic = await InnerTube(client='ANDROID_EMBED').player(self.video_id)

            if not vdic.get('streamingData'):
                used = 'yt-dlp'
                url = f'https://www.youtube.com/watch?v={self.video_id}'
                with YoutubeDL({'format': 'bestaudio','quiet':True}) as ydl:
                    vdic = await self.loop.run_in_executor(None, ydl.extract_info, url, False)

        #print(f'used {used}')

        await self._format(vdic)
        self.volume = -17.0 - self.st_vol
        self.local = False
        self.music = True
        self.YT = True
        return self
    


    # 汎用人型決戦兵器 (Youtube 以外)
    async def Ytdlp_V(self):
        with YoutubeDL({'format': 'best','quiet':True,'noplaylist':True}) as ydl:
            info = await self.loop.run_in_executor(None,ydl.extract_info, self.input, False)
            self.st_url = info['url']
            self.web_url = self.input
            self.title = self.input
            self.st_sec = int(info.get('duration',None))
            self.formats = info.get('formats')
            self.local = False
            self.music = True
            self.YT = False
        return self


    def Url_Only(self):
        self.st_url = self.input
        self.music = False
        self.YT = False
        return self


    async def _format(self, vdic):

        # pytube
        if vdic.get('streamingData'):
            self.formats = vdic['streamingData'].get('formats',[])
            self.formats.extend(vdic['streamingData'].get('adaptiveFormats',[]))
            res = []
            for fm in self.formats:
                if 249 <= fm['itag'] <= 251 or 139 <= fm['itag'] <= 141:
                    res.append(fm)
            self.st_url = res[-1]['url']
            self.title = vdic["videoDetails"]["title"]
            self.ch_name = vdic["videoDetails"]["author"]
            self.ch_url = f'https://www.youtube.com/channel/{vdic["videoDetails"]["channelId"]}'
            self.ch_id = vdic["videoDetails"]["channelId"]
            self.video_id = vdic["videoDetails"]["videoId"]
            self.st_vol = vdic['playerConfig']['audioConfig'].get('loudnessDb')
            self.st_sec = int(vdic['videoDetails']['lengthSeconds'])
            self.view_count = vdic['videoDetails']['viewCount']
            await self.api_get_viewcounts()

        else:
            self.formats = vdic['formats']
            self.st_url = vdic['url']
            self.title = vdic["title"]
            self.ch_name = vdic["channel"]
            self.ch_url = vdic["channel_url"]
            self.ch_id = vdic["channel_id"]
            self.video_id = vdic["id"]
            self.st_vol = 5.0
            self.st_sec = int(vdic["duration"])
            self.view_count = vdic.get('view_count')
            self.like_count = vdic.get('like_count')
            ud = vdic['upload_date']
            self.upload_date = f'{ud[:4]}/{ud[4:6]}/{ud[6:]}'


        self.web_url = f"https://youtu.be/{self.video_id}"
        params = {'key':config.youtube_key, 'part':'snippet', 'id':self.ch_id}
        url = youtube_api + '/channels'
        async with aiohttp.ClientSession() as session:
            async with session.get(url=url, params=params) as resp:
                text = await resp.json()
        self.ch_icon = text['items'][0]['snippet']['thumbnails']['medium']['url']
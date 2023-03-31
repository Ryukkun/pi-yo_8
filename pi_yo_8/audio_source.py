import asyncio
import aiohttp
import re
import urllib.parse

from typing import Optional
from yt_dlp import YoutubeDL
from .discord.player import FFmpegPCMAudio, FFmpegOpusAudio
from .pytube.innertube import InnerTube

import config

re_URL_YT = re.compile(r'https://((www.|)youtube.com|youtu.be)/')
re_URL_Video = re.compile(r'https://((www.|)youtube.com/watch\?v=|(youtu.be/))(.+)')
re_URL_PL_Video = re.compile(r'https://(www.|)youtube.com/watch\?v=(.+)&list=(.+)')
re_URL_PL = re.compile(r'https://(www.|)youtube.com/playlist\?list=(.+)')
re_URL = re.compile(r'http')
youtube_api = 'https://www.googleapis.com/youtube/v3'



class AnalysisUrl:
    def __init__(self) -> None:
        self.arg:Optional[str] = None
        self.playlist:Optional[bool] = False
        self.index:Optional[int] = None
        self.random_pl:Optional[bool] = None
        self.sad:Optional[StreamAudioData] = None


    async def video_check(self, arg:str) -> 'AnalysisUrl':
        """
        .p で指定された引数を、再生可能か判別する

        再生可能だった場合
        return self

        不可
        return None
        """
        self.arg = arg
        ### 動画+playlist
        if re_result := re_URL_PL_Video.match(arg):
            arg = f'https://www.youtube.com/watch?v={re_result.group(2)}'
        
        ### 文字指定
        if not re_URL.match(arg):
            self.sad = await StreamAudioData().api_v_search(arg)

        ### youtube 動画オンリー
        elif re_URL_YT.match(arg):
            try: 
                self.sad = await StreamAudioData().Pyt_V(arg)
            except Exception as e:
                print(f"Error : Audio only 失敗 {e}")

        ### それ以外のサイト yt-dlp を使用
        else:
            try:
                self.sad = await StreamAudioData().Ytdlp_V(arg)
            except Exception as e:
                print(f"Error : Audio + Video 失敗 {e}")

        if not self.sad:return
        return self



    async def url_check(self, arg:str) -> 'AnalysisUrl':
        """
        指定された引数を、再生可能か判別する
        
        Playlist形式
        return 'pl'
        
        単曲
        return 'video'

        不可
        return None
        """
        self.arg = arg
        ### PlayList 本体のURL ------------------------------------------------------------------------#
        if result_re := re_URL_PL.match(arg): 
            if pl := await StreamAudioData().api_p(result_re.group(2)):
                self.playlist = True
                self.index = -1
                self.random_pl = True
                self.sad = pl 

        ### PlayList と 動画が一緒についてきた場合 --------------------------------------------------------------#
        elif result_re := re_URL_PL_Video.match(arg):
            watch_id = result_re.group(2)
            #arg = f'https://www.youtube.com/playlist?list={result_re.group(3)}'
            arg = re.sub(r'&index.+','',result_re.group(3))

            # Load Video in the Playlist 
            if pl := await StreamAudioData().api_p(arg):

                # Playlist Index 特定
                index = 0
                for index, temp in enumerate(pl):
                    if watch_id in temp:
                        break

                self.playlist = True
                self.index = index - 1
                self.random_pl = False
                self.sad = pl


        ### youtube 動画オンリー -----------------------------------------------------------------------#
        elif re_URL_YT.match(arg):
            try: 
                self.sad = await StreamAudioData().Pyt_V(arg)
            except Exception as e:
                print(f"Error : Audio only 失敗 {e}")


        ### それ以外のサイト yt-dlp を使用 -----------------------------------------------------------------------#
        elif re_URL.match(arg):
            try: 
                self.sad = await StreamAudioData().Ytdlp_V(arg)
            except Exception as e:
                print(f"Error : Audio + Video 失敗 {e}")


        ### URLじゃなかった場合 -----------------------------------------------------------------------#
        else:
            self.sad = await StreamAudioData().api_p_search(arg)
            self.index = -1
            self.random_pl = False
            self.playlist = True
        
        if not self.sad:return
        return self


class StreamAudioData:
    def __init__(self, _input):
        self.input = _input
        self.loop = asyncio.get_event_loop()
        
        # video id, url
        self.video_id = None
        self.web_url = None

        # video detail
        self.view_count = None
        self.like_count = None
        self.upload_date:Optional[str] = None
        
        # video stream date
        self.st_vol = None
        self.st_sec = None
        self.st_url = None

        # 振り分け
        self.music = None
        self.YT = None
        self.index = None
        
        # playlist index
        self.index:Optional[int] = None
    

    async def api_get_viewcounts(self):
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


    async def api_p_search(self, arg):
        #arg = urllib.parse.quote(arg)
        params = {'key':config.youtube_key, 'part':'id', 'q':arg, 'maxResults':'20', 'type':'video'}
        url = youtube_api + '/search'
        async with aiohttp.ClientSession() as session:
            async with session.get(url=url, params=params) as resp:
                text = await resp.json()

        return [_['id']['videoId'] for _ in text['items']]


    @classmethod
    async def api_p(self, arg):
        arg = urllib.parse.quote(arg)
        params = {'key':config.youtube_key, 'part':'contentDetails,status', 'playlistId':arg, 'maxResults':'50'}
        url = youtube_api + '/playlistItems'
        res_urls = []
        async with aiohttp.ClientSession() as session:
            while True:
                async with session.get(url=url, params=params) as resp:
                    text = await resp.json()
                    checked_urls = []
                    for _ in text['items']:
                        if _['status']['privacyStatus'].lower() == 'private':
                            continue
                        checked_urls.append(_['contentDetails']['videoId'])
                    res_urls.extend(checked_urls)
                    if text.get('nextPageToken'):
                        params['pageToken'] = text['nextPageToken']
                    else:
                        break
        return res_urls


        
    # YT Video Load
    async def Pyt_V(self):
        self.video_id = self.input

        self.Vdic = await InnerTube().player(self.video_id)
        if not self.Vdic.get('streamingData'):
            url = f'https://www.youtube.com/watch?v={self.video_id}'
            with YoutubeDL({'format': 'bestaudio','quiet':True}) as ydl:
                self.Vdic = await self.loop.run_in_executor(None, ydl.extract_info, url, False)

        await self._format()
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
            self.music = True
            self.YT = False
        return self


    def Url_Only(self):
        self.st_url = self.input
        self.music = False
        self.YT = False
        return self


    async def _format(self):

        # pytube
        if self.Vdic.get('streamingData'):
            self.formats = self.Vdic['streamingData'].get('formats',[])
            self.formats.extend(self.Vdic['streamingData'].get('adaptiveFormats',[]))
            res = []
            for fm in self.formats:
                if 249 <= fm['itag'] <= 251 or 139 <= fm['itag'] <= 141:
                    res.append(fm)
            self.st_url = res[-1]['url']
            self.title = self.Vdic["videoDetails"]["title"]
            self.ch_name = self.Vdic["videoDetails"]["author"]
            self.ch_url = f'https://www.youtube.com/channel/{self.Vdic["videoDetails"]["channelId"]}'
            self.ch_id = self.Vdic["videoDetails"]["channelId"]
            self.video_id = self.Vdic["videoDetails"]["videoId"]
            self.st_vol = self.Vdic['playerConfig']['audioConfig'].get('loudnessDb')
            self.st_sec = int(self.Vdic['videoDetails']['lengthSeconds'])
            await self.api_get_viewcounts()

        else:
            self.formats = self.Vdic['formats']
            self.st_url = self.Vdic['url']
            self.title = self.Vdic["title"]
            self.ch_name = self.Vdic["channel"]
            self.ch_url = self.Vdic["channel_url"]
            self.ch_id = self.Vdic["channel_id"]
            self.video_id = self.Vdic["id"]
            self.st_vol = 5.0
            self.st_sec = int(self.Vdic["duration"])
            self.view_count = self.Vdic.get('view_count')
            self.like_count = self.Vdic.get('like_count')
            ud = self.Vdic['upload_date']
            self.upload_date = f'{ud[:4]}/{ud[4:6]}/{ud[6:]}'


        self.web_url = f"https://youtu.be/{self.video_id}"
        params = {'key':config.youtube_key, 'part':'snippet', 'id':self.ch_id}
        url = youtube_api + '/channels'
        async with aiohttp.ClientSession() as session:
            async with session.get(url=url, params=params) as resp:
                text = await resp.json()
        self.ch_icon = text['items'][0]['snippet']['thumbnails']['medium']['url']



    async def AudioSource(self, opus:bool, sec:int=0, speed:float=1.0, pitch:int=0):
        before_options = []
        options = ['-vn', '-application', 'lowdelay', '-loglevel', 'quiet']
        af = []

        # Sec
        if int(sec):
            before_options.extend(('-ss' ,str(sec)))
        
        # Pitch
        if pitch != 0:
            pitch = 2 ** (pitch / 12)
            af.append(f'rubberband=pitch={pitch}')
        
        if float(speed) != 1.0:
            af.append(f'rubberband=tempo={speed}')

        if self.music:
            volume = -15.0
            if Vol := self.st_vol:
                volume -= Vol
            before_options.extend(('-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5', '-analyzeduration', '2147483647', '-probesize', '2147483647'))
            af.append(f'volume={volume}dB')
        
        # af -> str
        if af:
            options.extend(('-af', ','.join(af) ))

        if opus:
            options.extend(('-c:a', 'libopus', '-ar', '48000'))
            return FFmpegOpusAudio(self.st_url, before_options=before_options, options=options)

        else:
            options.extend(('-c:a', 'pcm_s16le', '-ar', '48000'))
            return FFmpegPCMAudio(self.st_url, before_options=before_options, options=options)
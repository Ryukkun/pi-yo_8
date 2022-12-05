import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re
from yt_dlp import YoutubeDL
import pytube
from pytube.innertube import InnerTube
from pytube.helpers import DeferredGeneratorList
from discord import FFmpegOpusAudio, FFmpegPCMAudio

re_URL_YT = re.compile(r'https://((www.|)youtube.com|youtu.be)/')
re_URL_Video = re.compile(r'https://((www.|)youtube.com/watch\?v=|(youtu.be/))(.+)')
re_URL_PL_Video = re.compile(r'https://(www.|)youtube.com/watch\?v=(.+)&list=(.+)')
re_URL_PL = re.compile(r'https://(www.|)youtube.com/playlist\?list=')
re_URL = re.compile(r'http')



class StreamAudioData:

    def __init__(self,url):
        self.Url = url
        self.loop = asyncio.get_event_loop()
        self.Web_Url = None
        self.St_Vol = None
        self.St_Sec = None
        self.St_Url = None
        self.music = None
        self.YT = None
        self.CH_Icon = None
        self.index = None
        
    # YT Video Load
    async def Pyt_V(self):
        self.Vid = re_URL_Video.match(self.Url).group(4)
        self.Vdic = await self.loop.run_in_executor(None,InnerTube().player,self.Vid)
        if not self.Vdic.get('streamingData'):
            with YoutubeDL({'format': 'bestaudio','quiet':True}) as ydl:
                self.Vdic = await self.loop.run_in_executor(None,ydl.extract_info,self.Url,False)

        await self._format()
        self.music = True
        self.YT = True
        return self


    # 汎用人型決戦兵器
    async def Ytdlp_V(self):
        with YoutubeDL({'format': 'best','quiet':True,'noplaylist':True}) as ydl:
            info = await self.loop.run_in_executor(None,ydl.extract_info,self.Url,False)
            self.St_Url = info['url']
            self.Web_Url = self.Url
            self.St_Sec = int(info.get('duration',None))
            self.formats = info.get('formats')
            self.music = True
            self.YT = False
        return self

    def Url_Only(self):
        self.St_Url = self.Url
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
            self.St_Url = res[-1]['url']
            self.Title = self.Vdic["videoDetails"]["title"]
            self.CH = self.Vdic["videoDetails"]["author"]
            self.CH_Url = f'https://www.youtube.com/channel/{self.Vdic["videoDetails"]["channelId"]}'
            self.VideoID = self.Vdic["videoDetails"]["videoId"]
            self.St_Vol = self.Vdic['playerConfig']['audioConfig'].get('loudnessDb')
            self.St_Sec = int(self.Vdic['videoDetails']['lengthSeconds'])

        else:
            self.formats = self.Vdic['formats']
            self.St_Url = self.Vdic['url']
            self.Title = self.Vdic["title"]
            self.CH = self.Vdic["channel"]
            self.CH_Url = self.Vdic["channel_url"]
            self.VideoID = self.Vdic["id"]
            self.St_Vol = 5.0
            self.St_Sec = int(self.Vdic["duration"])

        self.Web_Url = f"https://youtu.be/{self.VideoID}"
        async with aiohttp.ClientSession() as session:
            async with session.get(self.CH_Url) as resp:
                text = await resp.read()
        CH_Icon = BeautifulSoup(text.decode('utf-8'), 'html.parser')
        self.CH_Icon = CH_Icon.find('link',rel="image_src").get('href')


    async def AudioSource(self, opus:bool, sec=0):
        FFMPEG_OPTIONS = {
            'before_options': '',
            'options': f'-vn -application lowdelay -loglevel quiet'
            }

        if int(sec):
            FFMPEG_OPTIONS['before_options'] += f'-ss {sec}'
        
        if self.music:
            volume = -20.0
            if Vol := self.St_Vol:
                volume -= Vol
            FFMPEG_OPTIONS['before_options'] += " -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -analyzeduration 2147483647 -probesize 2147483647"
            FFMPEG_OPTIONS['options'] += f' -af "volume={volume}dB"'

        if opus:
            FFMPEG_OPTIONS['options'] += ' -c:a libopus'
            return await FFmpegOpusAudio.from_probe(self.St_Url,**FFMPEG_OPTIONS)

        else:
            FFMPEG_OPTIONS['options'] += ' -c:a pcm_s16le -b:a 128k'
            return FFmpegPCMAudio(self.St_Url,**FFMPEG_OPTIONS)


    async def Check(self):
        """
        指定された引数を、再生可能か判別する
        
        Playlist形式
        return (Index, Random:bool, [urls])
        
        単曲
        return self
        
        不可
        return None
        """
        ### PlayList 本体のURL ------------------------------------------------------------------------#
        if re_URL_PL.match(self.Url): 
            if Pl := await self.Pyt_P(self.Url):
                return (0, 1, Pl)

        ### PlayList と 動画が一緒についてきた場合 --------------------------------------------------------------#
        elif result_re := re_URL_PL_Video.match(self.Url):
            watch_id = result_re.group(2)
            self.Url = f'https://www.youtube.com/playlist?list={result_re.group(3)}'

            # Load Video in the Playlist 
            if Pl := await self.Pyt_P(self.Url):

                # Playlist Index 特定
                index = 0
                for index, temp in enumerate(Pl):
                    if watch_id in temp:
                        break
            
                return (index, 0, Pl)
            

        ### youtube 動画オンリー -----------------------------------------------------------------------#
        elif re_URL_YT.match(self.Url):
            try: return await self.Pyt_V()
            except Exception as e:
                print(f"Error : Audio only 失敗 {e}")
                return

        ### それ以外のサイト yt-dlp を使用 -----------------------------------------------------------------------#
        elif re_URL.match(self.Url):
            try: return await self.Ytdlp_V()
            except Exception as e:
                print(f"Error : Audio + Video 失敗 {e}")
                return

        ### URLじゃなかった場合 -----------------------------------------------------------------------#
        else:
            Pl = await self.Pyt_P_Search(self.Url)
            return (0, 0, Pl)




    async def Check_V(self):
        """
        .p で指定された引数を、再生可能か判別する

        再生可能だった場合
        return self

        不可
        return None
        """
        ### 動画+playlist
        if re_result := re_URL_PL_Video.match(self.Url):
            self.Url = f'https://www.youtube.com/watch?v={re_result.group(2)}'
        
        ### 文字指定
        if not re_URL.match(self.Url):
            return await self.Pyt_V_Search()

        ### youtube 動画オンリー
        elif re_URL_YT.match(self.Url):
            try: return await self.Pyt_V()
            except Exception as e:
                print(f"Error : Audio only 失敗 {e}")
                return

        ### それ以外のサイト yt-dlp を使用
        else:
            try: return await self.Ytdlp_V()
            except Exception as e:
                print(f"Error : Audio + Video 失敗 {e}")
                return





    # Video Search
    async def Pyt_V_Search(self):
        pyt = pytube.Search(self.Url)
        Vdic = await self.loop.run_in_executor(None,pyt.fetch_and_parse)

        self.Url = Vdic[0][0].watch_url
        res = await self.Pyt_V()

        self.music = True
        self.YT = True
        return res

    # Playlist Search
    async def Pyt_P_Search(self,Url):
        loop = asyncio.get_event_loop()
        pyt = pytube.Search(Url)
        Vdic = await loop.run_in_executor(None,pyt.fetch_and_parse)
        return [temp.watch_url for temp in Vdic[0]]

    # Playlist 全体 Load
    async def Pyt_P(self,Url):
        loop = asyncio.get_event_loop()
        yt_pl = pytube.Playlist(Url)
        try: return await loop.run_in_executor(None,DeferredGeneratorList,yt_pl.url_generator())
        except Exception as e:
            print(f'Error : Playlist All-List {e}')
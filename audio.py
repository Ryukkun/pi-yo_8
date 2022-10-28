import asyncio
import re
from yt_dlp import YoutubeDL
import pytube
from pytube.innertube import InnerTube
from pytube.helpers import DeferredGeneratorList
from discord import FFmpegPCMAudio, FFmpegOpusAudio


re_URL_Video = re.compile(r'https://((www.|)youtube.com/watch\?v=|(youtu.be/))(.+)')



class StreamAudioData:

    def __init__(self,url):
        self.Url = url
        self.loop = asyncio.get_event_loop()
        
    # YT Video Load
    async def Pyt_V(self):
        self.Vid = re_URL_Video.match(self.Url).group(4)
        self.Vdic = await self.loop.run_in_executor(None,InnerTube().player,self.Vid)

        self.Web_Url = self.Url
        self.St_Vol = self.Vdic.get('playerConfig',{}).get('audioConfig',{}).get('loudnessDb',None)
        self.St_Url = await self._format()
        return self


    # Video Search
    async def Pyt_V_Search(self):
        pyt = pytube.Search(self.Url)
        Vdic = await self.loop.run_in_executor(None,pyt.fetch_and_parse)
        self.Vdic = await self.loop.run_in_executor(None,InnerTube().player,Vdic[0][0].video_id)
        self.Web_Url = f"https://youtu.be/{self.Vdic['videoDetails']['videoId']}"
        self.St_Vol = self.Vdic.get('playerConfig',{}).get('audioConfig',{}).get('loudnessDb',None)
        self.St_Url = await self._format()
        return self

    # 汎用人型決戦兵器
    async def Ytdlp_V(self):
        with YoutubeDL({'format': 'best','quiet':True,'noplaylist':True}) as ydl:
            info = await self.loop.run_in_executor(None,ydl.extract_info,self.Url,False)
            self.St_Url = info['url']
            self.Web_Url = self.Url
            self.St_Vol = None


    async def _format(self):
        formats = self.Vdic['streamingData'].get('formats',[])
        formats.extend(self.Vdic['streamingData'].get('adaptiveFormats',[]))
        res = []
        for fm in formats:
            if 249 <= fm['itag'] <= 251 or 139 <= fm['itag'] <= 141:
                res.append(fm)
        return res[-1]['url']


    async def AudioSource(self):
        volume = -20
        if Vol := self.St_Vol:
            if Vol <= 0:
                Vol /= 2
            volume -= int(Vol)

        FFMPEG_OPTIONS = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -analyzeduration 2147483647 -probesize 2147483647",
            'options': f'-vn -c:a pcm_s16le -af "volume={volume}dB" -b:a 128k -application lowdelay'
            }
        return FFmpegPCMAudio(self.St_Url,**FFMPEG_OPTIONS)

# Playlist Search
async def Pyt_P_Search(Url):
    loop = asyncio.get_event_loop()
    pyt = pytube.Search(Url)
    Vdic = await loop.run_in_executor(None,pyt.fetch_and_parse)
    return [temp.watch_url for temp in Vdic[0]]

# Playlist 全体 Load
async def Pyt_P(Url):
    loop = asyncio.get_event_loop()
    yt_pl = pytube.Playlist(Url)
    try: return await loop.run_in_executor(None,DeferredGeneratorList,yt_pl.url_generator())
    except Exception as e:
        print(f'Error : Playlist All-List {e}')
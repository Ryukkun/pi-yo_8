import asyncio
import re
from yt_dlp import YoutubeDL
import pytube
from pytube.innertube import InnerTube
from pytube.helpers import DeferredGeneratorList

re_false = re.compile(r'(f|0|ふぁlせ)')
re_true = re.compile(r'(t|1|ｔるえ)')
re_random = re.compile(r'(r|2|らんどm)')
re_URL_YT = re.compile(r'https://((www.|)youtube.com|youtu.be)/')
re_URL_Video = re.compile(r'https://((www.|)youtube.com/watch\?v=|(youtu.be/))(.+)')
re_URL_PL_Video = re.compile(r'https://(www.|)youtube.com/watch\?v=(.+)&list=(.+)')
re_str_PL = re.compile(r'p')
re_URL_PL = re.compile(r'https://(www.|)youtube.com/playlist\?list=')
re_URL = re.compile(r'http')


class StreamAudioData:

    def __init__(sefl):
        pass

    async def pytube_vid(self,url):
        Vid = re_URL_Video.match(url).group(4)
        loop = asyncio.get_event_loop()
        INN = InnerTube()
        Vdic = await loop.run_in_executor(None,INN.player,Vid)

        St_Url = await self._format(Vdic)
        St_Vol = Vdic.get('playerConfig',{}).get('audioConfig',{}).get('loudnessDb',None)
        return St_Url,St_Vol

    @classmethod
    async def _format(cls,Vdic):
        formats = Vdic['streamingData'].get('formats',[])
        formats.extend(Vdic['streamingData'].get('adaptiveFormats',[]))
        res = []
        for fm in formats:
            if 249 <= fm['itag'] <= 251 or 139 <= fm['itag'] <= 141:
                res.append(fm)
        return res[-1]['url']


    async def pytube_search(self,arg,mode):
        loop = asyncio.get_event_loop()
        pyt = pytube.Search(arg)
        Vdic = await loop.run_in_executor(None,pyt.fetch_and_parse)
        if pyt:
            if mode == 'video':
                INN = InnerTube()
                Vdic = await loop.run_in_executor(None,INN.player,Vdic[0][0].video_id)
                Web_Url = f"https://youtu.be/{Vdic['videoDetails']['videoId']}"
                St_Vol = Vdic.get('playerConfig',{}).get('audioConfig',{}).get('loudnessDb',None)
                St_Url = await _format(Vdic)
                return St_Url,Web_Url,St_Vol

            if mode == 'playlist':
                Web_Url = [temp.watch_url for temp in Vdic[0]]
                return Web_Url
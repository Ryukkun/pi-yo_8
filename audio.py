import asyncio
import re
from yt_dlp import YoutubeDL
import pytube
from pytube.innertube import InnerTube
from pytube.helpers import DeferredGeneratorList


re_URL_Video = re.compile(r'https://((www.|)youtube.com/watch\?v=|(youtu.be/))(.+)')



class StreamAudioData:
    @classmethod
    async def pytube_vid(self,url):
        self.Vid = re_URL_Video.match(url).group(4)
        loop = asyncio.get_event_loop()
        INN = InnerTube()
        self.Vdic = await loop.run_in_executor(None,INN.player,self.Vid)

        self.Web_Url = url
        self.St_Url = await self._format(self.Vdic)
        self.St_Vol = self.Vdic.get('playerConfig',{}).get('audioConfig',{}).get('loudnessDb',None)


    async def _format(self,Vdic):
        formats = Vdic['streamingData'].get('formats',[])
        formats.extend(Vdic['streamingData'].get('adaptiveFormats',[]))
        res = []
        for fm in formats:
            if 249 <= fm['itag'] <= 251 or 139 <= fm['itag'] <= 141:
                res.append(fm)
        return res[-1]['url']

    @classmethod
    async def pytube_search(col,arg,mode):
        loop = asyncio.get_event_loop()
        pyt = pytube.Search(arg)
        Vdic = await loop.run_in_executor(None,pyt.fetch_and_parse)
        if pyt:
            if mode == 'video':
                INN = InnerTube()
                col.Vdic = await loop.run_in_executor(None,INN.player,Vdic[0][0].video_id)
                col.Web_Url = f"https://youtu.be/{col.Vdic['videoDetails']['videoId']}"
                col.St_Vol = col.Vdic.get('playerConfig',{}).get('audioConfig',{}).get('loudnessDb',None)
                col.St_Url = await col._format(col.Vdic)

            if mode == 'playlist':
                col.Web_Url = [temp.watch_url for temp in Vdic[0]]

    
    async def yt_dlp_vid(self,url):
        loop = asyncio.get_event_loop()
        with YoutubeDL({'format': 'best','quiet':True,'noplaylist':True}) as ydl:
            info = await loop.run_in_executor(None,ydl.extract_info,url,False)
            self.St_Url = info['url']
            self.Web_Url = url
            self.St_Vol = None
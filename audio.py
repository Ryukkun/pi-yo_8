import asyncio
import re
from yt_dlp import YoutubeDL
import pytube
from pytube.innertube import InnerTube
from pytube.helpers import DeferredGeneratorList


re_URL_Video = re.compile(r'https://((www.|)youtube.com/watch\?v=|(youtu.be/))(.+)')



class StreamAudioData:

    async def pytube_vid(self,url):
        self.Vid = re_URL_Video.match(url).group(4)
        loop = asyncio.get_event_loop()
        INN = InnerTube()
        self.Vdic = await loop.run_in_executor(None,INN.player,self.Vid)

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


    async def pytube_search(self,arg,mode):
        loop = asyncio.get_event_loop()
        pyt = pytube.Search(arg)
        self.Vdic = await loop.run_in_executor(None,pyt.fetch_and_parse)
        if pyt:
            if mode == 'video':
                INN = InnerTube()
                self.Vdic = await loop.run_in_executor(None,INN.player,self.Vdic[0][0].video_id)
                self.Web_Url = f"https://youtu.be/{self.Vdic['videoDetails']['videoId']}"
                self.St_Vol = self.Vdic.get('playerConfig',{}).get('audioConfig',{}).get('loudnessDb',None)
                self.St_Url = await self._format(self.Vdic)

            if mode == 'playlist':
                Web_Url = [temp.watch_url for temp in self.Vdic[0]]
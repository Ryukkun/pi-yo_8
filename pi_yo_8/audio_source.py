import asyncio
import aiohttp
import re
import pytube
import io
import subprocess

from typing import Union, Optional, IO, Literal
from yt_dlp import YoutubeDL
from bs4 import BeautifulSoup
from pytube.innertube import InnerTube
from pytube.helpers import DeferredGeneratorList
from discord import FFmpegAudio
from discord.oggparse import OggStream
from discord.opus import Encoder as OpusEncoder

re_URL_YT = re.compile(r'https://((www.|)youtube.com|youtu.be)/')
re_URL_Video = re.compile(r'https://((www.|)youtube.com/watch\?v=|(youtu.be/))(.+)')
re_URL_PL_Video = re.compile(r'https://(www.|)youtube.com/watch\?v=(.+)&list=(.+)')
re_URL_PL = re.compile(r'https://(www.|)youtube.com/playlist\?list=')
re_URL = re.compile(r'http')

"""
The MIT License (MIT)
Copyright (c) 2015-present Rapptz
Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""
class FFmpegPCMAudio(FFmpegAudio):
    """An audio source from FFmpeg (or AVConv).
    This launches a sub-process to a specific input file given.
    .. warning::
        You must have the ffmpeg or avconv executable in your path environment
        variable in order for this to work.
    Parameters
    ------------
    source: Union[:class:`str`, :class:`io.BufferedIOBase`]
        The input that ffmpeg will take and convert to PCM bytes.
        If ``pipe`` is ``True`` then this is a file-like object that is
        passed to the stdin of ffmpeg.
    executable: :class:`str`
        The executable name (and path) to use. Defaults to ``ffmpeg``.
    pipe: :class:`bool`
        If ``True``, denotes that ``source`` parameter will be passed
        to the stdin of ffmpeg. Defaults to ``False``.
    stderr: Optional[:term:`py:file object`]
        A file-like object to pass to the Popen constructor.
        Could also be an instance of ``subprocess.PIPE``.
    before_options: Optional[:class:`str`]
        Extra command line arguments to pass to ffmpeg before the ``-i`` flag.
    options: Optional[:class:`str`]
        Extra command line arguments to pass to ffmpeg after the ``-i`` flag.
    Raises
    --------
    ClientException
        The subprocess failed to be created.
    """

    def __init__(
        self,
        source: Union[str, io.BufferedIOBase],
        *,
        executable: str = 'ffmpeg',
        pipe: bool = False,
        stderr: Optional[IO[str]] = None,
        before_options: Optional[list] = None,
        options: Optional[list] = None,
    ) -> None:
        args = []
        subprocess_kwargs = {'stdin': subprocess.PIPE if pipe else subprocess.DEVNULL, 'stderr': stderr}

        if before_options:
            args.extend(before_options)

        args.append('-i')
        args.append('-' if pipe else source)
        args.extend(('-ac', '2', '-loglevel', 'warning', '-b:a', '128k'))

        if options:
            args.extend(options)

        args.append('pipe:1')

        super().__init__(source, executable=executable, args=args, **subprocess_kwargs)

    def read(self) -> bytes:
        ret = self._stdout.read(OpusEncoder.FRAME_SIZE)
        if len(ret) != OpusEncoder.FRAME_SIZE:
            return b''
        return ret

    def is_opus(self) -> bool:
        return False




class FFmpegOpusAudio(FFmpegAudio):
    """An audio source from FFmpeg (or AVConv).
    This launches a sub-process to a specific input file given.  However, rather than
    producing PCM packets like :class:`FFmpegPCMAudio` does that need to be encoded to
    Opus, this class produces Opus packets, skipping the encoding step done by the library.
    Alternatively, instead of instantiating this class directly, you can use
    :meth:`FFmpegOpusAudio.from_probe` to probe for bitrate and codec information.  This
    can be used to opportunistically skip pointless re-encoding of existing Opus audio data
    for a boost in performance at the cost of a short initial delay to gather the information.
    The same can be achieved by passing ``copy`` to the ``codec`` parameter, but only if you
    know that the input source is Opus encoded beforehand.
    .. versionadded:: 1.3
    .. warning::
        You must have the ffmpeg or avconv executable in your path environment
        variable in order for this to work.
    Parameters
    ------------
    source: Union[:class:`str`, :class:`io.BufferedIOBase`]
        The input that ffmpeg will take and convert to Opus bytes.
        If ``pipe`` is ``True`` then this is a file-like object that is
        passed to the stdin of ffmpeg.
    bitrate: :class:`int`
        The bitrate in kbps to encode the output to.  Defaults to ``128``.
    codec: Optional[:class:`str`]
        The codec to use to encode the audio data.  Normally this would be
        just ``libopus``, but is used by :meth:`FFmpegOpusAudio.from_probe` to
        opportunistically skip pointlessly re-encoding Opus audio data by passing
        ``copy`` as the codec value.  Any values other than ``copy``, ``opus``, or
        ``libopus`` will be considered ``libopus``.  Defaults to ``libopus``.
        .. warning::
            Do not provide this parameter unless you are certain that the audio input is
            already Opus encoded.  For typical use :meth:`FFmpegOpusAudio.from_probe`
            should be used to determine the proper value for this parameter.
    executable: :class:`str`
        The executable name (and path) to use. Defaults to ``ffmpeg``.
    pipe: :class:`bool`
        If ``True``, denotes that ``source`` parameter will be passed
        to the stdin of ffmpeg. Defaults to ``False``.
    stderr: Optional[:term:`py:file object`]
        A file-like object to pass to the Popen constructor.
        Could also be an instance of ``subprocess.PIPE``.
    before_options: Optional[:class:`str`]
        Extra command line arguments to pass to ffmpeg before the ``-i`` flag.
    options: Optional[:class:`str`]
        Extra command line arguments to pass to ffmpeg after the ``-i`` flag.
    Raises
    --------
    ClientException
        The subprocess failed to be created.
    """

    def __init__(
        self,
        source: Union[str, io.BufferedIOBase],
        *,
        executable: str = 'ffmpeg',
        pipe: bool = False,
        stderr: Optional[IO[bytes]] = None,
        before_options: Optional[list] = None,
        options: Optional[list] = None,
    ) -> None:
        args = []
        subprocess_kwargs = {'stdin': subprocess.PIPE if pipe else subprocess.DEVNULL, 'stderr': stderr}

        if before_options:
            args.extend(before_options)

        args.append('-i')
        args.append('-' if pipe else source)

        # fmt: off
        args.extend(('-map_metadata', '-1',
                     '-f', 'opus',
                     '-ac', '2',
                     '-b:a', '128k',
                     '-loglevel', 'warning'))
        # fmt: on

        if options:
            args.extend(options)

        args.append('pipe:1')

        super().__init__(source, executable=executable, args=args, **subprocess_kwargs)
        self._packet_iter = OggStream(self._stdout).iter_packets()

    def read(self) -> bytes:
        return next(self._packet_iter, b'')

    def is_opus(self) -> bool:
        return True



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
            self.sad = await StreamAudioData().Pyt_V_Search(arg)

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
        if re_URL_PL.match(arg): 
            if pl := await StreamAudioData().Pyt_P(arg):
                self.playlist = True
                self.index = -1
                self.random_pl = True
                self.sad = pl 

        ### PlayList と 動画が一緒についてきた場合 --------------------------------------------------------------#
        elif result_re := re_URL_PL_Video.match(arg):
            watch_id = result_re.group(2)
            arg = f'https://www.youtube.com/playlist?list={result_re.group(3)}'

            # Load Video in the Playlist 
            if pl := await StreamAudioData().Pyt_P(arg):

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
            pl = await StreamAudioData().Pyt_P_Search(arg)
            self.index = -1
            self.random_pl = False
            self.sad = pl
        
        if not self.sad:return
        return self


class StreamAudioData:
    def __init__(self):
        self.url:Optional[str] = None
        self.loop = asyncio.get_event_loop()
        self.web_url = None
        self.st_vol = None
        self.st_sec = None
        self.st_url = None
        self.music = None
        self.YT = None
        self.ch_icon = None
        self.index = None
        
        
    # YT Video Load
    async def Pyt_V(self, arg):
        self.url = arg
        self.Vid = re_URL_Video.match(arg).group(4)
        self.Vdic = await self.loop.run_in_executor(None,InnerTube().player,self.Vid)
        if not self.Vdic.get('streamingData'):
            with YoutubeDL({'format': 'bestaudio','quiet':True}) as ydl:
                self.Vdic = await self.loop.run_in_executor(None,ydl.extract_info,arg,False)

        await self._format()
        self.music = True
        self.YT = True
        return self
    

    # Video Search
    async def Pyt_V_Search(self, arg):
        pyt = pytube.Search(arg)
        Vdic = await self.loop.run_in_executor(None,pyt.fetch_and_parse)

        self.url = Vdic[0][0].watch_url
        res = await self.Pyt_V()

        self.music = True
        self.YT = True
        return res
    

    # Playlist Search
    async def Pyt_P_Search(self, arg):
        self.url = arg
        pyt = pytube.Search(arg)
        Vdic = await self.loop.run_in_executor(None,pyt.fetch_and_parse)
        return [temp.watch_url for temp in Vdic[0]]
    

    # Playlist 全体 Load
    async def Pyt_P(self, arg):
        self.url = arg
        yt_pl = pytube.Playlist(arg)
        try: return await self.loop.run_in_executor(None,DeferredGeneratorList,yt_pl.url_generator())
        except Exception as e:
            print(f'Error : Playlist All-List {e}')


    # 汎用人型決戦兵器
    async def Ytdlp_V(self, arg):
        with YoutubeDL({'format': 'best','quiet':True,'noplaylist':True}) as ydl:
            info = await self.loop.run_in_executor(None,ydl.extract_info, arg, False)
            self.st_url = info['url']
            self.web_url = arg
            self.url = arg
            self.st_sec = int(info.get('duration',None))
            self.formats = info.get('formats')
            self.music = True
            self.YT = False
        return self


    def Url_Only(self, arg):
        self.st_url = arg
        self.url = arg
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
            self.Title = self.Vdic["videoDetails"]["title"]
            self.CH = self.Vdic["videoDetails"]["author"]
            self.CH_Url = f'https://www.youtube.com/channel/{self.Vdic["videoDetails"]["channelId"]}'
            self.VideoID = self.Vdic["videoDetails"]["videoId"]
            self.st_vol = self.Vdic['playerConfig']['audioConfig'].get('loudnessDb')
            self.st_sec = int(self.Vdic['videoDetails']['lengthSeconds'])

        else:
            self.formats = self.Vdic['formats']
            self.st_url = self.Vdic['url']
            self.Title = self.Vdic["title"]
            self.CH = self.Vdic["channel"]
            self.CH_Url = self.Vdic["channel_url"]
            self.VideoID = self.Vdic["id"]
            self.st_vol = 5.0
            self.st_sec = int(self.Vdic["duration"])

        self.web_url = f"https://youtu.be/{self.VideoID}"
        async with aiohttp.ClientSession() as session:
            async with session.get(self.CH_Url) as resp:
                text = await resp.read()
        ch_icon = BeautifulSoup(text.decode('utf-8'), 'html.parser')
        self.ch_icon = ch_icon.find('link',rel="image_src").get('href')



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
            #speed = speed / pitch
            #af.append('aresample=48000')
            #af.append(f'asetrate={48000*pitch}')
            af.append(f'rubberband=pitch={pitch}')
        
        if float(speed) != 1.0:
            #af.append(f'atempo={speed}')
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
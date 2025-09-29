import asyncio
import json
import time
import traceback
from yt_dlp import YoutubeDL
from typing import TYPE_CHECKING, Any, AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Pipe, Process, connection

from pi_yo_8.utils import AsyncGenWrapper, ModdedBuffer, UrlAnalyzer
from pi_yo_8.yt_dlp.status_manager import ErrorMessage, YTDLPStatusManager, ErrorType, LambdaLogger

from ._ie import YoutubeIE

if TYPE_CHECKING:
    from pi_yo_8.main import DataInfo


YTDLP_GENERAL_PARAMS = {
    "http_headers": {
        "Accept-Language": "ja-JP,ja;q=0.9",
    },
    'format':'bestaudio/worst',
    "default_search":"ytsearch30",
    'extract_flat':"in_playlist",
    'quiet':True,
    'skip_download': True,
    "lazy_playlist": True,
    "forcejson":True
}
YTDLP_VIDEO_PARAMS = {
    "http_headers": {
        "Accept-Language": "ja-JP,ja;q=0.9",
    },
    'format':'bestaudio/worst',
    "default_search":"ytsearch30",
    'extract_flat':"in_playlist",
    'quiet':True,
    'skip_download': True,
    "noplaylist": True,
}



class YTDLPExtractor:
    def __init__(self, parms:dict) -> None:
        """
        Parameters
        ----------
        opts : dict
            yt-dlp に渡すオプション ログイン情報の想定
        """
        self.is_running:bool = False
        self.connection, child = Pipe()
        self.process = Process(target=YTDLPExtractor._extract_info, args=(child, parms))
        self.process.start()

    @staticmethod
    def get_ytdlp(parms:dict) -> YoutubeDL:
        ydl = YoutubeDL(parms) # type: ignore
        ydl.add_info_extractor(YoutubeIE()) # type: ignore
        return ydl


    def extract_raw_info(self, url:str, data_info:"DataInfo|None" = None) -> tuple[AsyncGenWrapper, YTDLPStatusManager]:
        self.is_running = True
        self.connection.send(url)
        loop = asyncio.get_event_loop()
        status_manager = YTDLPStatusManager(url if UrlAnalyzer(url).is_url else '')
        if data_info:
            data_info.ytdlp_status_managers.append(status_manager)
        async def generator():
            with ThreadPoolExecutor(max_workers=1) as exe:
                while True:
                    _result:str | dict[str, Any] | ErrorMessage = await loop.run_in_executor(exe, self.connection.recv)
                    if _result == '':
                        self.is_running = False
                        status_manager.is_running = False
                        if data_info:
                            loop.call_later(30, data_info.ytdlp_status_managers.remove, status_manager)
                        break
                    if isinstance(_result, ErrorMessage):
                        status_manager.append_error(_result)
                        continue
                    info:dict[str, Any] = json.loads(_result) if isinstance(_result, str) else _result
                    yield info

        async def finallize(generator: AsyncGenerator):
            async for _ in generator:
                pass

        return AsyncGenWrapper(generator(), lambda x: loop.create_task(finallize(x))), status_manager

    

    @staticmethod
    def _extract_info(connection: connection._ConnectionBase, opts:dict):
        '''
        別スレッドで実行しっぱなしを想定
        '''
        opts = opts.copy()
        #opts["logger"] = LambdaLogger(warning=lambda msg: connection.send(ErrorMessage(ErrorType.WARNING, msg)))
        ydl = YTDLPExtractor.get_ytdlp(opts)
        
        buffer = ModdedBuffer()
        ydl._out_files.__dict__["out"] = buffer # type: ignore
        with ThreadPoolExecutor(max_workers=1) as exe:
            while url := connection.recv():
                try:
                    future = exe.submit(ydl.extract_info, url, download=False, process=True)
                    send_count = 0
                    while True:
                        line = buffer.readline()
                        if line == '':
                            if future.done():
                                break
                            else:
                                time.sleep(0.01)
                                continue
                        connection.send(line)
                        send_count += 1

                    # プレイリストの場合戻り値要らない
                    if (result := future.result()) and (not "entries" in result or send_count == 0):
                        connection.send(result)
                except Exception as e:
                    connection.send(ErrorMessage(ErrorType.ERROR, str(e), type(e).__name__, traceback.format_exc()))
                finally:
                    buffer.clean()
                    connection.send('')
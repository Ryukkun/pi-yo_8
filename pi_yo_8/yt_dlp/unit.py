import asyncio
import json
import time
import io
from threading import Lock
from yt_dlp import YoutubeDL
from typing import Any, AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Pipe, Process, connection

from pi_yo_8.utils import AsyncGenWrapper

from ._ie import YoutubeIE


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


class ModdedBuffer(io.StringIO):
    '''
    readlineをするときは最初から読み込まれていく
    readlineとwrite以外は使わない想定
    '''
    def __init__(self, initial_value: str | None = "", newline: str | None = "\n") -> None:
        super().__init__(initial_value, newline)
        self.read_pos = 0
        self._lock = Lock()

    def readline(self, size: int = -1) -> str:
        with self._lock:
            self.seek(self.read_pos)
            result = super().readline(size)
            self.read_pos = self.tell()
        return result
        
    def write(self, s: str) -> int:
        with self._lock:
            self.seek(0, 2)
            result = super().write(s)
        return result
    
    def clean(self) -> None:
        self.seek(0)
        self.truncate(0)
        self.read_pos = 0


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


    def extract_raw_info(self, url:str) -> AsyncGenWrapper:
        self.is_running = True
        self.connection.send(url)
        loop = asyncio.get_event_loop()
        async def generator():
            with ThreadPoolExecutor(max_workers=1) as exe:
                while True:
                    _result:str|dict[str, Any] = await loop.run_in_executor(exe, self.connection.recv)
                    if _result == '':
                        self.is_running = False
                        break
                    info:dict[str, Any] = json.loads(_result) if isinstance(_result, str) else _result
                    if info.get("error"):
                        print(info["error"])
                        continue
                    yield info

        async def load_all_generator(generator: AsyncGenerator):
            print("raw finallize : ", url)
            async for _ in generator:
                pass
        gen = generator()
        return AsyncGenWrapper(gen, lambda x: loop.create_task(load_all_generator(x)))

    

    @staticmethod
    def _extract_info(connection: connection._ConnectionBase, opts:dict):
        '''
        別スレッドで実行しっぱなしを想定
        '''
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
                    connection.send(json.dumps({
                        "error": str(e)
                    }))
                finally:
                    buffer.clean()
                    connection.send('')
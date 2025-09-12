import asyncio
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, thread
import io
import sys
from threading import Lock
import time
from typing import Any, Generator

from yt_dlp import YoutubeDL
from multiprocessing import Pipe, Process, connection

class YTDLPExtractor:
    YTDLP_PARAMS = {
        'format':'bestaudio/worst',
        "default_search":"ytsearch30",
        'extract_flat':"in_playlist",
        'quiet':True,
        'skip_download': True,
        "lazy_playlist": True,
        "forcejson":True
    }
    def __init__(self, connection:connection.PipeConnection, process) -> None:
        """
        Parameters
        ----------
        opts : dict
            yt-dlp に渡すオプション ログイン情報の想定
        """
        self.connection = connection
        self.process = process
        #self.exe = ProcessPoolExecutor()


    async def extract_info(self, url:str, process=True):
        t = time.time()
        self.connection.send(url)
        print(time.time() - t)
        def io():
            while True:
                info:str|bool = self.connection.recv()
                print(info)
                if info == False:
                    return
        await asyncio.get_event_loop().run_in_executor(None, io)


class ModdedBuffer(io.StringIO):
    def __init__(self, initial_value: str | None = "", newline: str | None = "\n") -> None:
        super().__init__(initial_value, newline)
        self.read_pos = 0
        self.write_pos = 0
        self._lock = Lock()

    def readline(self, size: int = -1) -> str:
        with self._lock:
            self.seek(self.read_pos)
            result = super().readline(size)
            self.read_pos = self.tell()
            return result
        
    def write(self, s: str) -> int:
        with self._lock:
            self.seek(self.write_pos)
            result = super().write(s)
            self.write_pos = self.tell()
            return result


def __extract_info(connection: connection.PipeConnection, opts:dict):
    print("com")
    buffer = ModdedBuffer()
    #ydl._out_files.__dict__["out"] = buffer
    sys.stdout = buffer
    ydl = _get_ytdlp(opts)
    exe = ThreadPoolExecutor(max_workers=1)
    while url := connection.recv():
        t = time.time()
        future = exe.submit(ydl.extract_info, url, download=False, process=True)
        print(time.time() - t)
        t = time.time()
        line_c = 0
        while True:
            if (line := buffer.readline()) == '':
                if future.done():
                    break
                else:
                    time.sleep(0.05)
                    continue
            connection.send(line)
        # if info:
        #     if 'entries' in info and info['entries']:
        #         entries:dict|Generator = info.pop("entries")
        #         connection.send(info)
        #         if isinstance(entries, Generator):
        #             try:
        #                 while True:
        #                     connection.send(next(entries))
        #             except:
        #                 pass

        #         else:
        #             connection.send(entries)

        #     elif "formats" in info:
        #         connection.send(info)
        #connection.send(buffer.getvalue())
        connection.send(buffer.tell())
        connection.send(False)
    print("Fin")
    exe.shutdown()


def _get_ytdlp(opts) -> YoutubeDL:
    ydl = YoutubeDL(opts)
    return ydl




if __name__ == "__main__":
    parent, child = Pipe()
    process = Process(target=__extract_info, args=(child, YTDLPExtractor.YTDLP_PARAMS))
    process.start()
    y = YTDLPExtractor(parent, process)
    while True:
        url = input("in >> ")
        asyncio.run(y.extract_info(url))
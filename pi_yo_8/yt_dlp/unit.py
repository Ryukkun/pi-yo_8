import asyncio
import itertools
import json
import time
import io
from threading import Lock
import traceback
from yt_dlp import YoutubeDL
from typing import TYPE_CHECKING, Any
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Pipe, Process, connection

from ._ie import YoutubeIE
from pi_yo_8.music_control.playlist import LazyPlaylist, Playlist

if TYPE_CHECKING:
    from pi_yo_8.yt_dlp.audio_data import YTDLPAudioData


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
        ydl = YoutubeDL(parms)
        ydl.add_info_extractor(YoutubeIE())
        return ydl


    async def extract_info(self, url:str) -> "YTDLPAudioData | Playlist | None":
        self.is_running = True
        print("extract_info", url)
        from pi_yo_8.yt_dlp.audio_data import YTDLPAudioData
        self.connection.send(url)
        info_entries:list["YTDLPAudioData"] = []

        def read_from_pipe(limit = -1):
            for _ in itertools.count():
                if _ == limit:
                    return True
                _result:str|dict[str, Any] = self.connection.recv()
                if _result == '':
                    self.is_running = False
                    return False
                info:dict = json.loads(_result) if isinstance(_result, str) else _result
                info_entries.append(YTDLPAudioData(info))

        load_success = await asyncio.to_thread(read_from_pipe, 1)
        if load_success and not info_entries:
            print("extract_info None", url)
            return None
        
        future = ThreadPoolExecutor(max_workers=1).submit(read_from_pipe)
        info = info_entries[0].info
        if info.get("error"):
            print(info.get("error"))
            return None

        #Playlist
        if info.get("playlist"):
            print("extract_info playlist", url)
            return LazyPlaylist(info, info_entries, future)

        #その他 Video・Channel等
        if (thmb := info.get('thumbnails')) and isinstance(thmb, list):
            thmb.sort(key=lambda t:(
                t.get("preference", -100),
                t.get("width", 0) * t.get("height", 0)  #解像度
            ), reverse=True)
        print("extract_info video", url)
        return info_entries[0]


    

    @staticmethod
    def _extract_info(connection: connection.PipeConnection, opts:dict):
        '''
        別スレッドで実行しっぱなしを想定
        '''
        ydl = YTDLPExtractor.get_ytdlp(opts)
        buffer = ModdedBuffer()
        ydl._out_files.__dict__["out"] = buffer
        exe = ThreadPoolExecutor(max_workers=1)
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
        exe.shutdown()
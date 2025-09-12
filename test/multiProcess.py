import asyncio
from concurrent.futures import ThreadPoolExecutor
import io
from threading import Lock
import time

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


    async def extract_info(self, url:str, process=True):
        self.connection.send(url)
        def io():
            while True:
                info_str:str|dict = self.connection.recv()
                if info_str == '':
                    return
                print(info_str)
                #info = json.loads(info_str)
                #print(info['title'])
        await asyncio.get_event_loop().run_in_executor(None, io)


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



def __extract_info(connection: connection.PipeConnection, opts:dict):
    '''
    ★ 動画+Playlist >> https://www.youtube.com/watch?v=mJ-4Iz506t0&list=PLbF1amD14adXEDu-U3fxYXEuytBfXvfjQ
    - stdoutにentry+playlistの情報
    {"_type": "url", "ie_key": "Youtube", "id": "mJ-4Iz506t0", "url": "https://www.youtube.com/watch?v=mJ-4Iz506t0", "title": "Test your bond with Paint by solving puzzles cooperatively, where gimmicks are activated when you...", "description": null, "duration": 1112, "channel_id": "UClNdVSK1uy2xFHTaXZYXopw", "channel": "\u3089\u3063\u3060\u3041", "channel_url": "https://www.youtube.com/channel/UClNdVSK1uy2xFHTaXZYXopw", "uploader": "\u3089\u3063\u3060\u3041", "uploader_id": "@radaooo", "uploader_url": "https://www.youtube.com/@radaooo", "thumbnails": [{"url": "https://i.ytimg.com/vi/mJ-4Iz506t0/hqdefault.jpg?sqp=-oaymwEbCKgBEF5IVfKriqkDDggBFQAAiEIYAXABwAEG&rs=AOn4CLAN-rlY9bMtmdcqJNdffAfRCN6Gzw", "height": 94, "width": 168}, {"url": "https://i.ytimg.com/vi/mJ-4Iz506t0/hqdefault.jpg?sqp=-oaymwEbCMQBEG5IVfKriqkDDggBFQAAiEIYAXABwAEG&rs=AOn4CLD0UbnOQebZUIAFN2fFr-bJ9LghQQ", "height": 110, "width": 196}, {"url": "https://i.ytimg.com/vi/mJ-4Iz506t0/hqdefault.jpg?sqp=-oaymwEcCPYBEIoBSFXyq4qpAw4IARUAAIhCGAFwAcABBg==&rs=AOn4CLArxtlEfuXrQEk9BcXThVIk4WqnnQ", "height": 138, "width": 246}, {"url": "https://i.ytimg.com/vi/mJ-4Iz506t0/hqdefault.jpg?sqp=-oaymwEcCNACELwBSFXyq4qpAw4IARUAAIhCGAFwAcABBg==&rs=AOn4CLA3cIfspsD51lmfiYBJ_jmbuJMTpQ", "height": 188, "width": 336}], "timestamp": null, "release_timestamp": null, "availability": null, "view_count": 468000, "live_status": null, "channel_is_verified": null, "__x_forwarded_for_ip": null, "webpage_url": "https://www.youtube.com/watch?v=mJ-4Iz506t0", "original_url": "https://www.youtube.com/watch?v=mJ-4Iz506t0", "webpage_url_basename": "watch", "webpage_url_domain": "youtube.com", "extractor": "youtube", "extractor_key": "Youtube", "playlist_count": 1, "playlist": "\u9b54\u773c\u306e\u5927\u8ff7\u5bae/\u8131\u51fa\u30de\u30c3\u30d7", "playlist_id": "PLbF1amD14adXEDu-U3fxYXEuytBfXvfjQ", "playlist_title": "\u9b54\u773c\u306e\u5927\u8ff7\u5bae/\u8131\u51fa\u30de\u30c3\u30d7", "playlist_uploader": "\u3089\u3063\u3060\u3041", "playlist_uploader_id": "@radaooo", "playlist_channel": "\u3089\u3063\u3060\u3041", "playlist_channel_id": "UClNdVSK1uy2xFHTaXZYXopw", "playlist_webpage_url": "https://www.youtube.com/playlist?list=PLbF1amD14adXEDu-U3fxYXEuytBfXvfjQ", "n_entries": null, "playlist_index": 1, "__last_playlist_index": 0, "playlist_autonumber": 1, "epoch": 1757671377, "duration_string": "18:32", "release_year": null, "_version": {"version": "2025.08.27", "current_git_head": null, "release_git_head": "8cd37b85d492edb56a4f7506ea05527b85a6b02b", "repository": "yt-dlp/yt-dlp"}}

    - 戻り値にplaylistの情報 (entryの情報もついてくるから削除)
    多分なくてもいい

    ★ plyaylist >> https://www.youtube.com/playlist?list=PLbF1amD14adXEDu-U3fxYXEuytBfXvfjQ
    上記と同じ
    '''
    print("com")
    ydl = _get_ytdlp(opts)
    buffer = ModdedBuffer()
    ydl._out_files.__dict__["out"] = buffer
    exe = ThreadPoolExecutor(max_workers=1)
    while url := connection.recv():
        future = exe.submit(ydl.extract_info, url, download=False, process=True)
        while True:
            line = buffer.readline()
            if line == '':
                if future.done():
                    break
                else:
                    time.sleep(0.01)
                    continue
            connection.send(line)

        # プレイリストの場合戻り値要らない
        if (result := future.result()) and not "entries" in result:
            connection.send(result)
        buffer.clean()
        connection.send('')
    print("Fin")
    exe.shutdown()


def _get_ytdlp(opts) -> YoutubeDL:
    ydl = YoutubeDL(opts)
    return ydl




if __name__ == "__main__":
    parent, child = Pipe()
    # クラスのコンストラクタ内で新しいプロセス作ったらばぐった クラス外の関数を対象にしてもダメだった
    process = Process(target=__extract_info, args=(child, YTDLPExtractor.YTDLP_PARAMS))
    process.start()
    y = YTDLPExtractor(parent, process)
    while True:
        url = input("in >> ")
        asyncio.run(y.extract_info(url))
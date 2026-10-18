import asyncio
import json
import time
import traceback
from collections.abc import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Pipe, Process, connection
from typing import Any

from yt_dlp import YoutubeDL

from pi_yo_8.core.url import UrlAnalyzer
from pi_yo_8.sources.buffer import ModdedBuffer
from pi_yo_8.sources.loudness_ie import YoutubeIE
from pi_yo_8.sources.status import ErrorMessage, ErrorType, StatusManager

YTDLP_GENERAL_PARAMS = {
    "http_headers": {
        "Accept-Language": "ja-JP,ja;q=0.9",
    },
    'format': 'bestaudio/worst',
    "default_search": "ytsearch30",
    'extract_flat': "in_playlist",
    'quiet': True,
    'skip_download': True,
    "lazy_playlist": True,
    "forcejson": True,
}

YTDLP_VIDEO_PARAMS = {
    "http_headers": {
        "Accept-Language": "ja-JP,ja;q=0.9",
    },
    'format': 'bestaudio/worst',
    "default_search": "ytsearch30",
    'extract_flat': "in_playlist",
    'quiet': True,
    'skip_download': True,
    "noplaylist": True,
}

class YTDLPExtractor:
    def __init__(self, params: dict) -> None:
        self.is_running: bool = False
        self.connection, child = Pipe()
        self.process = Process(target=YTDLPExtractor._extract_info, args=(child, params))
        self.process.start()

    @staticmethod
    def get_ytdlp(params: dict) -> YoutubeDL:
        ydl = YoutubeDL(params)  # type: ignore
        ydl.add_info_extractor(YoutubeIE())  # type: ignore
        return ydl

    def extract_raw_info(self, url: str) -> tuple[AsyncGenerator[dict[str, Any]], StatusManager]:
        self.is_running = True
        self.connection.send(url)
        loop = asyncio.get_event_loop()
        status_manager = StatusManager(url if UrlAnalyzer(url).is_url else '')

        async def generator():
            with ThreadPoolExecutor(max_workers=1) as exe:
                while True:
                    received_item: str | dict[str, Any] | ErrorMessage = await loop.run_in_executor(
                        exe, self.connection.recv
                    )
                    if received_item == '':
                        self.is_running = False
                        status_manager.is_running = False
                        break
                    if isinstance(received_item, ErrorMessage):
                        status_manager.append_error(received_item)
                        continue
                    info: dict[str, Any] = json.loads(received_item) if isinstance(received_item, str) else received_item
                    yield info

        return generator(), status_manager

    @staticmethod
    def _extract_info(conn: connection._ConnectionBase, options: dict) -> None:
        ydl = YTDLPExtractor.get_ytdlp(options.copy())
        buffer = ModdedBuffer()
        ydl._out_files.__dict__["out"] = buffer  # type: ignore
        with ThreadPoolExecutor(max_workers=1) as exe:
            while url := conn.recv():
                try:
                    future = exe.submit(ydl.extract_info, url, download=False, process=True)
                    send_count = 0
                    while True:
                        line = buffer.readline()
                        if line == '':
                            if future.done():
                                break
                            time.sleep(0.01)
                            continue
                        conn.send(line)
                        send_count += 1

                    if (result := future.result()) and ("entries" not in result or send_count == 0):
                        conn.send(result)
                except Exception as e:
                    conn.send(ErrorMessage(ErrorType.ERROR, str(e), type(e).__name__, traceback.format_exc()))
                finally:
                    buffer.clean()
                    conn.send('')

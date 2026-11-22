import asyncio
import json
import logging
import signal
import threading
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
from pi_yo_8.sources.status import ErrorMessage, ErrorType, LambdaLogger, StatusManager

_log = logging.getLogger("pi_yo_8.ytdlp")

YTDLP_GENERAL_PARAMS = {
    "http_headers": {
        "Accept-Language": "ja-JP,ja;q=0.9",
    },
    'format': 'bestaudio[acodec=opus]/bestaudio/best',
    "default_search": "ytsearch30",
    'extract_flat': "in_playlist",
    'quiet': True,
    'skip_download': True,
    "lazy_playlist": True,
    "forcejson": True,
    "extractor_args": {"youtube": {"player_client": ["android", "default", "-tv", "-mweb"]}},
}

YTDLP_VIDEO_PARAMS = {
    "http_headers": {
        "Accept-Language": "ja-JP,ja;q=0.9",
    },
    'format': 'bestaudio[acodec=opus]/bestaudio/best',
    "default_search": "ytsearch30",
    'extract_flat': "in_playlist",
    'quiet': True,
    'skip_download': True,
    "noplaylist": True,
    "extractor_args": {"youtube": {"player_client": ["android", "default", "-tv", "-mweb"]}},
}


class YTDLPExtractor:
    def __init__(self, params: dict[str, Any]) -> None:
        self.params = params
        self.is_running: bool = False
        self._start_process()

    def _start_process(self) -> None:
        self.connection, child = Pipe()
        self.process = Process(target=YTDLPExtractor._extract_info, args=(child, self.params), daemon=True)
        self.process.start()

    def stop(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass
        if self.process.is_alive():
            try:
                self.process.terminate()
                self.process.join(timeout=0.5)
                if self.process.is_alive():
                    self.process.kill()
                    self.process.join(timeout=0.2)
            except Exception:
                pass

    def restart(self) -> None:
        self.stop()
        self.is_running = False
        self._start_process()

    @staticmethod
    def get_ytdlp(params: dict[str, Any]) -> YoutubeDL:
        ydl = YoutubeDL(params)  # type: ignore[arg-type]
        ydl.add_info_extractor(YoutubeIE())  # type: ignore[arg-type]
        return ydl

    def extract_raw_info(self, url: str) -> tuple[AsyncGenerator[dict[str, Any]], StatusManager]:
        self.is_running = True
        # 残存している未読データをパージしてパイプの同期ズレを防止
        try:
            while self.connection.poll():
                self.connection.recv()
        except Exception:
            pass

        self.connection.send(url)
        loop = asyncio.get_running_loop()
        status_manager = StatusManager(url if UrlAnalyzer(url).is_url else '')

        async def generator() -> AsyncGenerator[dict[str, Any]]:
            reached_eof = False
            try:
                while True:
                    received_item: str | dict[str, Any] | ErrorMessage = await loop.run_in_executor(
                        None, self.connection.recv
                    )
                    if received_item == '':
                        reached_eof = True
                        break
                    if isinstance(received_item, ErrorMessage):
                        status_manager.append_error(received_item)
                        if received_item.type == ErrorType.ERROR:
                            _log.error(f"{received_item.description}")
                        elif received_item.type == ErrorType.WARNING:
                            _log.warning(f"{received_item.description}")
                        elif received_item.type == ErrorType.INFO:
                            _log.info(f"{received_item.description}")
                        elif received_item.type == ErrorType.DEBUG:
                            _log.debug(f"{received_item.description}")
                        continue
                    info: dict[str, Any] = json.loads(received_item) if isinstance(received_item, str) else received_item
                    yield info
            finally:
                status_manager.is_running = False
                if not reached_eof:
                    # EOF前に終了した場合、パイプに残っている同一タスクの出力をドレイン試行
                    drained = False
                    start_drain = time.time()
                    try:
                        while time.time() - start_drain < 1.0:
                            if self.connection.poll(0.05):
                                item = self.connection.recv()
                                if item == '':
                                    drained = True
                                    break
                            else:
                                if not self.process.is_alive():
                                    break
                    except Exception:
                        pass

                    if drained:
                        self.is_running = False
                    else:
                        _log.warning("YTDLPExtractor: stream drain timed out. Recycling worker process.")
                        self.restart()
                else:
                    self.is_running = False

        return generator(), status_manager

    @staticmethod
    def _extract_info(conn: connection._ConnectionBase, options: dict[str, Any]) -> None:
        try:
            signal.signal(signal.SIGINT, signal.SIG_IGN)
        except Exception:
            pass

        send_lock = threading.Lock()

        def safe_send(item: Any) -> None:
            with send_lock:
                try:
                    conn.send(item)
                except Exception:
                    pass

        try:
            opts = options.copy()
            opts["logger"] = LambdaLogger(
                debug=lambda msg: safe_send(ErrorMessage(ErrorType.DEBUG, msg)),
                warning=lambda msg: safe_send(ErrorMessage(ErrorType.WARNING, msg)),
                error=lambda msg: safe_send(ErrorMessage(ErrorType.ERROR, msg)),
            )

            ydl = YTDLPExtractor.get_ytdlp(opts)
            buffer = ModdedBuffer()
            ydl._out_files.out = buffer
            with ThreadPoolExecutor(max_workers=1) as exe:
                while True:
                    try:
                        url = conn.recv()
                    except (EOFError, BrokenPipeError, KeyboardInterrupt):
                        break
                    if not url:
                        break
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
                            safe_send(line)
                            send_count += 1

                        if (result := future.result()) and ("entries" not in result or send_count == 0):
                            safe_send(result)
                    except (KeyboardInterrupt, SystemExit):
                        break
                    except Exception as e:
                        safe_send(ErrorMessage(ErrorType.ERROR, str(e), type(e).__name__, traceback.format_exc()))
                    finally:
                        buffer.clean()
                        safe_send('')
        except (KeyboardInterrupt, SystemExit, EOFError, BrokenPipeError):
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

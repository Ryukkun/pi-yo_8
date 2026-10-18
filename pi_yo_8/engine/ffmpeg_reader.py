import logging
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor

from discord import FFmpegAudio

_log = logging.getLogger(__name__)


class FFmpegAudioReader:
    """ffmpegのreadによるブロックを別スレッドで先読みして回避するクラス"""
    def __init__(self, ffmpeg: FFmpegAudio) -> None:
        self.ffmpeg = ffmpeg
        self.pending_audio_queue: deque[bytes] = deque()
        self.history_audio_queue: deque[bytes] = deque()
        self.stop_flag = threading.Event()
        self.exe = ThreadPoolExecutor(max_workers=1)

        def read_all():
            try:
                _log.debug("FFmpeg reader thread started.")
                total_frames = 0
                while not self.stop_flag.is_set():
                    data = ffmpeg.read()
                    if not data:
                        _log.debug(f"FFmpeg reader reached EOF after {total_frames} frames.")
                        break
                    total_frames += 1
                    self.pending_audio_queue.append(data)
            except Exception as e:
                _log.error(f"FFmpeg reader error: {e}", exc_info=True)
            finally:
                self.exe.shutdown(wait=False)

        self.read_all_task = self.exe.submit(read_all)


    def read(self) -> bytes | None:
        """
        Returns:
            bytes | None:
                b'' は読み込み終了を意味する。
                None はまだ読み込みは終わっていないがreadが間に合っていない。
        """
        if self.pending_audio_queue:
            data = self.pending_audio_queue.popleft()
            self.history_audio_queue.append(data)
            return data
        if self.read_all_task.done():
            return b''
        return None

    def cleanup(self) -> None:
        self.stop_flag.set()
        try:
            self.ffmpeg.cleanup()
        except Exception:
            pass
        self.pending_audio_queue.clear()
        self.history_audio_queue.clear()

    def rewind(self, count: int) -> None:
        while self.history_audio_queue and count > 0:
            self.pending_audio_queue.appendleft(self.history_audio_queue.pop())
            count -= 1

    def skip(self, count: int) -> None:
        while self.pending_audio_queue and count > 0:
            self.history_audio_queue.append(self.pending_audio_queue.popleft())
            count -= 1

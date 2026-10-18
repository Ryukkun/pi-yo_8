import asyncio
import io
import logging
import re
import threading
from collections.abc import Callable
from typing import Any

from discord import FFmpegOpusAudio, FFmpegPCMAudio, opus

from pi_yo_8.core.track import Track
from pi_yo_8.engine.attributes import TrackAttribute
from pi_yo_8.engine.ffmpeg_reader import FFmpegAudioReader

_log = logging.getLogger(__name__)



class AudioTrack:
    FRAME_LENGTH = opus.Encoder.FRAME_LENGTH / 1000  # 秒
    FRAME_PER_SEC = 1000 / opus.Encoder.FRAME_LENGTH
    DURATION_REGEX = re.compile(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)")

    def __init__(self, opus_mode: bool, on_state_change: Callable[[], Any] | None = None) -> None:
        self.opus: bool = opus_mode
        self.ffmpeg_audio: FFmpegAudioReader | None = None
        self.track: Track | None = None
        self.pausing: bool = True
        self.timer: float = 0.0
        self.on_state_change = on_state_change

        self.pitch = TrackAttribute[int](init=0, min_val=-60, max_val=60, on_update_callback=self.seek_to_position)
        self.speed = TrackAttribute[float](init=1.0, min_val=0.1, max_val=3.0, on_update_callback=self.seek_to_position)
        self.after: Callable[[], Any] | None = None
        self._lock = threading.RLock()

    def has_audio_data(self) -> bool:
        return self.track is not None

    def is_paused(self) -> bool:
        return self.pausing

    def pause(self) -> None:
        if not self.pausing:
            self.pausing = True
            if self.on_state_change:
                self.on_state_change()

    def resume(self) -> None:
        if self.pausing:
            self.pausing = False
            if self.on_state_change:
                self.on_state_change()

    async def play(self, track: Track, after: Callable[[], Any]) -> None:
        self.track = track
        self.timer = 0.0
        self.after = after
        self.pausing = False
        _log.info(f"AudioTrack.play: '{track.title}' (duration={track.duration}s)")
        self._create_reader(seek_seconds=0.0)
        if self.on_state_change:
            self.on_state_change()

    def _create_reader(self, seek_seconds: float = 0.0) -> None:
        if not self.track or not self.track.stream_info:
            _log.warning(f"AudioTrack._create_reader: track or stream_info is missing! track={self.track}")
            return

        stream = self.track.stream_info
        before_options = []
        options = ['-vn', '-loglevel', 'warning']
        if self.opus:
            options.extend(('-application', 'audio'))
        audio_filters = []



        if int(seek_seconds):
            before_options.extend(('-ss', str(seek_seconds)))
        before_options.extend(('-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5', '-analyzeduration', '2147483647', '-probesize', '2147483647'))

        # headers: Combine multiple headers into a single argument separated by CRLF (\r\n)
        header_lines = []
        if stream.http_headers:
            for k, v in stream.http_headers.items():
                header_lines.append(f"{k}: {v}")
        if stream.cookies:
            header_lines.append(f"Cookie: {stream.cookies}")
        if header_lines:
            headers_str = "".join(f"{line}\r\n" for line in header_lines)
            before_options.extend(('-headers', f'"{headers_str}"'))

        if stream.http_headers and 'User-Agent' in stream.http_headers:
            before_options.extend(('-user_agent', f'"{stream.http_headers["User-Agent"]}"'))

        # pitch & speed
        if self.pitch.value != 0:
            pitch_float = 2 ** (self.pitch.value / 12)
            audio_filters.append(f'rubberband=pitch={pitch_float}')
        if float(self.speed.value) != 1.0:
            audio_filters.append(f'rubberband=tempo={self.speed.value}')
        if stream.volume_gain_db:
            audio_filters.append(f'volume={stream.volume_gain_db}dB')

        if audio_filters:
            options.extend(('-af', ','.join(audio_filters)))

        ffmpeg_options: dict[str, Any] = {
            "before_options": ' '.join(before_options),
        }

        if self.opus:
            is_opus_source = bool((stream.acodec and "opus" in stream.acodec.lower()) or (".webm" in stream.url))
            if is_opus_source and not audio_filters:
                ffmpeg_options["codec"] = "copy"
            else:
                ffmpeg_options["bitrate"] = 256
                options.extend(("-vbr", "on", "-compression_level", "10"))

        ffmpeg_options["options"] = ' '.join(options)

        # duration probe if missing
        if self.track.duration is None:
            duration_buffer = io.BytesIO()
            ffmpeg_options["stderr"] = duration_buffer
            options.extend(("-nostats", "-loglevel", "info"))
            ffmpeg_options["options"] = ' '.join(options)
            asyncio.create_task(self._probe_duration_from_stderr(duration_buffer))

        _log.debug(f"Creating FFmpeg audio reader for '{self.track.title}' (opus={self.opus})")
        source = (
            FFmpegOpusAudio(stream.url, **ffmpeg_options)
            if self.opus
            else FFmpegPCMAudio(stream.url, **ffmpeg_options)
        )
        self.ffmpeg_audio = FFmpegAudioReader(source)



    async def _probe_duration_from_stderr(self, duration_buffer: io.BytesIO) -> None:
        last_pos = 0
        while True:
            duration_buffer.seek(last_pos)
            chunk = duration_buffer.read()
            last_pos = duration_buffer.tell()
            if chunk:
                text = chunk.decode('utf-8', errors='ignore')
                if "Duration:" in text and (match := self.DURATION_REGEX.search(text)):
                    h, m, s = match.groups()
                    if self.track:
                        self.track.duration = float(h) * 3600 + float(m) * 60 + float(s)
                    return
            await asyncio.sleep(0.1)

    async def seek_to_position(self, sec: float | None = None) -> None:
        if not self.track:
            return
        if sec is None:
            sec = self.timer

        with self._lock:
            if self.ffmpeg_audio:
                self.ffmpeg_audio.cleanup()
            self._create_reader(seek_seconds=sec)
            self.timer = sec

    async def seek_by_seconds(self, seconds: float) -> None:
        if not self.track or not self.ffmpeg_audio:
            return

        with self._lock:
            if seconds > 0:
                skip_len = int(seconds * self.FRAME_PER_SEC / self.speed.get())
                target_sec = self.timer + seconds
                if self.track.duration is not None and self.track.duration < target_sec:
                    self._finish()
                    return

                if len(self.ffmpeg_audio.pending_audio_queue) + (self.FRAME_PER_SEC * 10) < skip_len:
                    await self.seek_to_position(sec=target_sec)
                    return

                while len(self.ffmpeg_audio.pending_audio_queue) < skip_len and not self.ffmpeg_audio.read_all_task.done():
                    await asyncio.sleep(0.01)
                self.ffmpeg_audio.skip(skip_len)
                self.timer += skip_len * self.FRAME_LENGTH * self.speed.get()

            elif seconds < 0:
                target_sec = self.timer + seconds
                if target_sec < 0:
                    seconds = -self.timer
                rwd_len = int(-seconds * self.FRAME_PER_SEC / self.speed.get())
                self.ffmpeg_audio.rewind(rwd_len)
                self.timer += -rwd_len * self.FRAME_LENGTH * self.speed.get()

    def read_bytes(self) -> bytes:
        audio_chunk = b''
        if self.ffmpeg_audio and not self.pausing and self._lock.acquire(blocking=False):
            try:
                audio_chunk = self.ffmpeg_audio.read()
                if audio_chunk:
                    self.timer += (self.FRAME_LENGTH * self.speed.get())
                    return audio_chunk
                if audio_chunk is None:
                    audio_chunk = b''
                else:
                    self._finish()
            finally:
                self._lock.release()
        return audio_chunk

    def _finish(self) -> None:
        title = self.track.title if self.track else 'Unknown'
        _log.info(f"AudioTrack._finish: track '{title}' finished at {self.timer:.1f}s")
        if self.ffmpeg_audio:
            self.ffmpeg_audio.cleanup()
        self.ffmpeg_audio = None
        self.track = None
        if self.after:
            self.after()
        if self.on_state_change:
            self.on_state_change()


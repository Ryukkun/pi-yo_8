from concurrent.futures import ThreadPoolExecutor
import io
import logging
import re
import threading
import asyncio
import time
import numpy as np
from collections import deque
from math import sqrt
from discord import FFmpegAudio, SpeakingState, opus, Guild, FFmpegPCMAudio, FFmpegOpusAudio
from typing import TYPE_CHECKING, Any, Callable, Generic, TypeVar, Union

from pi_yo_8.utils import run_check_storage


if TYPE_CHECKING:
    from pi_yo_8.main import GuildSession


_log = logging.getLogger(__name__)



class StreamAudioData:
    duration_regex = re.compile(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)")
    def __init__(self, 
                 stream_url: str,
                 volume: float | None = None,
                 duration: int | None = None):
        self.stream_url = stream_url
        self.volume = volume
        self.duration: int | float | None = duration


    async def set_duration_from_ffmpeg(self, duration_buffer: io.BytesIO) -> None:
        """
        ffmpegのstderrからdurationを取得する
        """
        last_pos = 0  # 前回の読み込み終了位置

        while True:
            duration_buffer.seek(last_pos)       # 前回終わった位置へ移動
            chunk = duration_buffer.read()       # 新しく追記された差分だけ読む
            last_pos = duration_buffer.tell()    # 現在の末尾位置を記憶

            if chunk:
                text = chunk.decode('utf-8', errors='ignore')
                if "Duration:" in text:
                    match = StreamAudioData.duration_regex.search(text)
                    if match:
                        h, m, s = match.groups()
                        self.duration = float(h) * 3600 + float(m) * 60 + float(s)
                        return  # durationが取得できたら終了

            await asyncio.sleep(0.1)


    def _create_ffmpeg_audio_source(self, opus: bool, before_options: list[str], options: list[str]) -> Union[FFmpegOpusAudio, FFmpegPCMAudio]:
        ffmpeg_options: dict[str, Any] = {}

        if (type(self.duration) != float):
            duration_buffer = io.BytesIO()
            ffmpeg_options["stderr"] = duration_buffer
            options.append("-nostats")
            options.append("-loglevel info")
            asyncio.create_task(self.set_duration_from_ffmpeg(duration_buffer))
            
        ffmpeg_options["options"] = ' '.join(options)
        ffmpeg_options["before_options"] = ' '.join(before_options)
        return FFmpegOpusAudio(self.stream_url, **ffmpeg_options) if opus else FFmpegPCMAudio(self.stream_url, **ffmpeg_options)


    def create_ffmpeg_reader(self, opus: bool, seek_seconds: float = 0.0, speed: float = 1.0, pitch: int = 0) -> 'FFmpegAudioReader':
        before_options = []
        options = ['-vn', '-application', 'audio', '-loglevel', 'quiet']
        audio_filters = []

        # Seek
        if int(seek_seconds):
            before_options.extend(('-ss', str(seek_seconds)))
        before_options.extend(('-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5', '-analyzeduration', '2147483647', '-probesize', '2147483647'))
        
        # Pitch
        if pitch != 0:
            pitch_float = 2 ** (pitch / 12)
            audio_filters.append(f'rubberband=pitch={pitch_float}')
        
        if float(speed) != 1.0:
            audio_filters.append(f'rubberband=tempo={speed}')

        if self.volume:
            audio_filters.append(f'volume={self.volume}dB')
        
        if audio_filters:
            options.extend(('-af', ','.join(audio_filters)))

        return FFmpegAudioReader(self._create_ffmpeg_audio_source(opus, before_options, options))


class FFmpegAudioReader():
    """ffmpegのreadのブロックをなくすことを目的としている"""
    def __init__(self, ffmpeg: FFmpegAudio) -> None:
        self.ffmpeg = ffmpeg
        self.pending_audio_queue: deque[bytes] = deque() 
        self.history_audio_queue: deque[bytes] = deque()

        def read_all():
            while not self.stop_flag.is_set() and (data := ffmpeg.read()):
                self.pending_audio_queue.append(data)
            self.exe.shutdown()

        self.stop_flag = threading.Event()
        self.exe = ThreadPoolExecutor(max_workers=1)
        self.read_all_task = self.exe.submit(read_all)


    def read(self) -> bytes | None:
        """
        Returns
        -------
        bytes|None
            b''は読み込み終了を意味する。
            Noneはまだ読み込みは終わっていないがreadが間に合っていない
        """
        if self.pending_audio_queue:
            data = self.pending_audio_queue.popleft()
            self.history_audio_queue.append(data)
            return data
        if self.read_all_task.done():
            return b''
        return None
    
    def cleanup(self):
        self.stop_flag.set()
        try:
            self.ffmpeg.cleanup()
        except Exception:
            pass
        self.pending_audio_queue.clear()
        self.history_audio_queue.clear()


    def rewind(self, count: int):
        while self.history_audio_queue and count > 0:
            self.pending_audio_queue.appendleft(self.history_audio_queue.pop())
            count -= 1

    def skip(self, count: int):
        while self.pending_audio_queue and count > 0:
            self.history_audio_queue.append(self.pending_audio_queue.popleft())
            count -= 1


T_Attr = TypeVar("T_Attr", int, float)
class TrackAttribute(Generic[T_Attr]):
    def __init__(self, init: T_Attr, min: T_Attr, max: T_Attr, on_update_callback: Callable[..., Any]) -> None:
        self.value = init
        self.on_update_callback = on_update_callback
        self.min = min
        self.max = max
    
    def get(self) -> T_Attr:
        return self.value

    async def set(self, target_value) -> bool:
        return await self._check(target_value)

    async def add(self, delta_value) -> bool:
        return await self._check(self.value + delta_value)

    async def _check(self, target_value) -> bool:
        if self.min <= target_value <= self.max:
            self.value = target_value
            await self.on_update_callback()
            return True
        return False


class MultiTrackVoiceClient:
    """
    Discord に存在する AudioPlayer は 同時に1つまでの音源の再生にしか対応していないため
    独自で Playerを作成 
    self.run は制御方法知らんから、常にループしてる 0.02秒(20ms) 間隔で 
    """
    def __init__(self, guild: Guild, guild_session: "GuildSession") -> None:
        self.enable_loop = True
        self.guild = guild
        self.loop = guild_session.bot.loop
        self.guild_session = guild_session
        self.tracks: list['AudioTrack'] = []
        self.should_encode = False
        self.guild_session.vc.encoder = opus.Encoder()


    def kill(self):
        self.enable_loop = False

    def add_track(self, opus: bool = False) -> 'AudioTrack':
        player = AudioTrack(opus=opus, vc=self)
        self.tracks.append(player)
        self.should_encode = (len(self.tracks) != 1 or (len(self.tracks) == 1 and not opus))
        return player

    def ensure_audio_loop_running(self):
        playing = 0
        for track in self.tracks:
            playing += not track.is_paused()

        if playing > 0 and not self._run_loop.is_running:
            self._run_loop.run_in_thread()


    def _set_speaking_state(self, speaking: SpeakingState) -> None:
        """
        音声ステータスを変えるやつ
        これがないと botがjoinしたときに居たメンツにしか 音が聞こえない
        """
        try:
            asyncio.run_coroutine_threadsafe(self.guild_session.vc.ws.speak(speaking), self.loop)
        except Exception:
            _log.exception(f"func:_set_speaking_state guild:{self.guild_session.guild.name}")

    @run_check_storage()
    def _run_loop(self):
        """
        音声データを送る 別スレッドで動作する 
        音声データ (Bytes) を取得し、必要があれば Numpy で読み込んで 合成しています
        最後に音声データ送信
        """
        send_audio = self.guild_session.vc.send_audio_packet
        self._set_speaking_state(SpeakingState.voice)
        start_time = time.perf_counter()
        try:
            while self.enable_loop:
                audio_bytes: bytes = b''
                byte_list: list[bytes] = []
                for track in self.tracks:
                    if audio_chunk := track.read_bytes():
                        byte_list.append(audio_chunk)
                    
                active_track = len(byte_list)
                if 1 <= active_track:
                    if self.should_encode:
                        adjust_vol = 1 / sqrt(active_track)
                        audio_numpy: np.ndarray = np.sum([np.frombuffer(byte_list[i], dtype=np.int16) * adjust_vol for i in range(active_track)], axis=0)
                        audio_bytes = audio_numpy.astype(np.int16).tobytes()
                    else:
                        audio_bytes = byte_list[0]

                # Loop Delay
                start_time += 0.02
                delay = max(0, start_time - time.perf_counter())
                time.sleep(delay)
    
                # Send Bytes
                if audio_bytes:
                    send_audio(audio_bytes, encode=self.should_encode)

                # thread fin
                else:
                    send_audio(opus.OPUS_SILENCE, encode=False)

                    playing = 0
                    for track in self.tracks:
                        playing += not track.is_paused()
                    if playing == 0:
                        self._set_speaking_state(SpeakingState.none)
                        break
        except Exception:
            _log.exception(f"func:_run_loop guild:{self.guild_session.guild.name}")


class AudioTrack:
    FRAME_LENGTH = opus.Encoder.FRAME_LENGTH / 1000 #Second
    FRAME_PER_SEC = 1000 / opus.Encoder.FRAME_LENGTH

    def __init__(self, opus: bool, vc: 'MultiTrackVoiceClient'):
        self.ffmpeg_audio: FFmpegAudioReader | None = None
        self.audio_data: StreamAudioData | None = None
        self.pausing: bool = True
        self.vc = vc
        self.timer: float = 0.0
        self.pitch = TrackAttribute(init=0, min=-60, max=60, on_update_callback=self.seek_to_position)
        self.speed = TrackAttribute(init=1.0, min=0.1, max=3.0, on_update_callback=self.seek_to_position)
        self.after: Callable[[], Any] | None = None
        self.opus: bool = opus
        self._lock = threading.RLock()

    async def play(self, stream_audio_data: StreamAudioData, after: Callable[[], Any]):
        self.audio_data = stream_audio_data
        self.ffmpeg_audio = stream_audio_data.create_ffmpeg_reader(self.opus, speed=self.speed.value, pitch=self.pitch.value)
        # 最初のロードは少し時間かかるから先にロード
        self.timer = 0.0
        self.after = after
        self.pausing = False
        self.vc.ensure_audio_loop_running()

    def resume(self):
        if self.pausing:
            self.pausing = False
            self.vc.ensure_audio_loop_running()

    def pause(self):
        if not self.pausing:
            self.pausing = True

    def has_audio_data(self):
        return self.audio_data is not None

    def is_paused(self):
        return self.pausing

    async def seek_by_seconds(self, seconds: float):
        if self.audio_data is None or self.ffmpeg_audio is None:
            return
        
        with self._lock:
            # n秒 進む
            if 0 < seconds:
                skip_data_len = int(seconds * self.FRAME_PER_SEC / self.speed.get())
                target_sec = self.timer + seconds
                if self.audio_data.duration is not None and self.audio_data.duration < target_sec:
                    self._finish()
                    return
                
                if len(self.ffmpeg_audio.pending_audio_queue) + (AudioTrack.FRAME_PER_SEC * 10) < skip_data_len:
                    await self.seek_to_position(sec=target_sec)
                    return
                while len(self.ffmpeg_audio.pending_audio_queue) < skip_data_len and not self.ffmpeg_audio.read_all_task.done():
                    await asyncio.sleep(0.01)
                self.ffmpeg_audio.skip(skip_data_len)
                self.timer += skip_data_len * self.FRAME_LENGTH * self.speed.get()

            # n秒 前に戻る
            elif seconds < 0:
                target_sec = self.timer + seconds
                if target_sec < 0:
                    target_sec = 0
                    seconds = -self.timer
                rwd_data_len = int(-seconds * self.FRAME_PER_SEC / self.speed.get())
                self.ffmpeg_audio.rewind(rwd_data_len)
                self.timer += -rwd_data_len * self.FRAME_LENGTH * self.speed.get()


    def read_bytes(self) -> bytes:
        """別スレッドからの呼び出しを想定

        Returns
        -------
        bytes
            音声データ ない場合はb''
        """
        audio_chunk = b''
        if self.ffmpeg_audio and not self.pausing:            
            # Read Bytes
            if self._lock.acquire(blocking=False):
                audio_chunk = self.ffmpeg_audio.read()
                # 終了
                if audio_chunk:
                    self.timer += (self.FRAME_LENGTH * self.speed.get())
                    self._lock.release()
                    return audio_chunk
                
                self._lock.release()
                if audio_chunk is None:
                    audio_chunk = b''
                else:
                    self._finish()
        return audio_chunk
            

    async def seek_to_position(self, sec: float | None = None):
        if not self.audio_data:
            return
        if sec is None:
            sec = self.timer

        with self._lock:
            if self.ffmpeg_audio:
                self.ffmpeg_audio.cleanup()
            self.ffmpeg_audio = self.audio_data.create_ffmpeg_reader(self.opus, sec, speed=self.speed.value, pitch=self.pitch.value)
            self.timer = sec


    def _finish(self):
        if self.ffmpeg_audio:
            self.ffmpeg_audio.cleanup()
        self.ffmpeg_audio = None
        self.audio_data = None
        if self.after:
            self.after()

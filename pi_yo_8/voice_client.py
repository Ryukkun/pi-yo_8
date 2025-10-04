from concurrent.futures import ThreadPoolExecutor
import threading
import asyncio
import time
import traceback
import numpy as np
from collections import deque
from math import sqrt
from discord import FFmpegAudio, SpeakingState, opus, Guild, FFmpegPCMAudio, FFmpegOpusAudio
from typing import TYPE_CHECKING, Any, Callable, Generic, TypeVar, Union

from main import IS_MAIN_PROCESS
from pi_yo_8.utils import run_check_storage


if TYPE_CHECKING:
    from pi_yo_8.main import DataInfo






class StreamAudioData:
    exe:ThreadPoolExecutor = ThreadPoolExecutor(max_workers=2) if IS_MAIN_PROCESS else None # type: ignore
    def __init__(self, 
                 st_url:str,
                 volume:float | None = None,
                 duration:int | None = None):
        self.stream_url = st_url
        self.volume = volume
        self.duration = duration


    def _get_ffmpegaudio(self, opus:bool, before_options:list[str], options:list[str]) -> Union[FFmpegOpusAudio, FFmpegPCMAudio]:
        option:str = ' '.join(options)
        before_option:str = ' '.join(before_options)
        if opus:
            #options.extend(('-c:a', 'libopus', '-ar', '48000'))
            return FFmpegOpusAudio(self.stream_url, before_options=before_option, options=option)

        else:
            #options.extend(('-c:a', 'pcm_s16le', '-ar', '48000'))
            return FFmpegPCMAudio(self.stream_url, before_options=before_option, options=option)



    def get_ffmpegaudio(self, opus:bool, sec:float=0.0, speed:float=1.0, pitch:int=0) -> 'FFmpegReader':
        before_options = []
        options = ['-vn', '-application', 'audio', '-loglevel', 'quiet']
        #options = ['-vn', '-application', 'lowdelay']
        af = []

        # Sec
        if int(sec):
            before_options.extend(('-ss' ,str(sec)))
        before_options.extend(('-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5', '-analyzeduration', '2147483647', '-probesize', '2147483647'))
        
        # Pitch
        if pitch != 0:
            pitch_float = 2 ** (pitch / 12)
            af.append(f'rubberband=pitch={pitch_float}')
        
        if float(speed) != 1.0:
            af.append(f'rubberband=tempo={speed}')

        if self.volume:
            af.append(f'volume={self.volume}dB')
        
        # af -> str
        if af:
            options.extend(('-af', ','.join(af) ))

        return FFmpegReader(self._get_ffmpegaudio(opus, before_options, options))


class FFmpegReader():
    """ffmpegのreadのブロックをなくすことを目的としている"""
    def __init__(self, ffmpeg:FFmpegAudio) -> None:
        self.ffmpeg = ffmpeg
        self.next_q:deque[bytes] = deque() 
        self.prev_q:deque[bytes] = deque()

        def read_all():
            while not self.stop_flag.is_set() and (data := ffmpeg.read()):
                self.next_q.append(data)
            self.exe.shutdown()

        self.stop_flag = threading.Event()
        self.exe = ThreadPoolExecutor(max_workers=1)
        self.read_all_task = self.exe.submit(read_all)

    def read(self) -> bytes|None:
        """
        Returns
        -------
        bytes|None
            b''は読み込み終了を意味する。
            Noneはまだ読み込みは終わっていないがreadが間に合っていない
        """
        if self.next_q:
            data = self.next_q.popleft()
            self.prev_q.append(data)
            return data
        if self.read_all_task.done():
            return b''
        return None
    
    def cleanup(self):
        self.stop_flag.set()
        self.ffmpeg.cleanup()
        self.next_q.clear()
        self.prev_q.clear()

    def rewind(self, count:int):
        while self.prev_q and count > 0:
            self.next_q.appendleft(self.prev_q.pop())
            count -= 1

    def skip(self, count:int):
        while self.next_q and count > 0:
            self.prev_q.append(self.next_q.popleft())
            count -= 1



V = TypeVar("V", int, float)
class _Attribute(Generic[V]):
    def __init__(self, init:V, min:V, max:V, update_asource:Callable[..., Any]) -> None:
        self.value = init
        self.update_asource = update_asource
        self.min = min
        self.max = max
    
    def get(self) -> V:
        return self.value

    async def set(self, num) -> bool:
        return await self._check(num)

    async def add(self, num) -> bool:
        return await self._check(self.value + num)

    async def _check(self, num) -> bool:
        if self.min <= num <= self.max:
            self.value = num
            await self.update_asource()
            return True
        return False



class MultiAudioVoiceClient:
    """
    Discord に存在する AudioPlayer は 同時に1つまでの音源の再生にしか対応していないため
    独自で Playerを作成 
    self.run は制御方法知らんから、常にループしてる 0.02秒(20ms) 間隔で 
    """
    def __init__(self, guild:Guild, info:"DataInfo") -> None:
        self.enable_loop = True
        self.guild = guild
        self.loop = info.bot.loop
        self.info = info
        self.tracks:list['AudioTrack'] = []
        self.enc_bool = False
        self.info.vc.encoder = opus.Encoder()
        #self.vc.encoder.set_expected_packet_loss_percent(0.01)

    def kill(self):
        self.enable_loop = False

    def add_track(self ,RNum=0 ,opus=False) -> 'AudioTrack':
        player = AudioTrack(opus=opus ,vc=self)
        self.tracks.append(player)
        self.enc_bool = (len(self.tracks) != 1 or len(self.tracks) == 1 and opus == False)
        return player

    def _speaking(self,status: bool):
        playing = 0
        for p in self.tracks:
            playing += not p.is_paused()

        if status:
            if playing == 1:
                self.__speak(SpeakingState.voice)
                if not self.run_loop.is_running:
                    self.run_loop.run_in_thread()
        else:
            if playing == 0:
                self.__speak(SpeakingState.none)


    def __speak(self, speaking: SpeakingState) -> None:
        """
        これ (self._speak) がないと謎にバグる ※botがjoinしたときに居たメンツにしか 音が聞こえない
        友達が幻聴を聞いてたら怖いよね
        """
        try:
            asyncio.run_coroutine_threadsafe(self.info.vc.ws.speak(speaking), self.loop)
        except Exception:
            pass

    @run_check_storage()
    def run_loop(self):
        """
        音声データをを送る　別スレッドで動作する 
        音声データ (Bytes) を取得し、必要があれば Numpy で読み込んで 合成しています
        最後に音声データ送信
        """
        send_audio = self.info.vc.send_audio_packet
        _start = time.perf_counter()
        fin_loop = 0
        while self.enable_loop:
            audio_bytes = None
            byte_list = []
            for _ in self.tracks:
                if _byte := _.read_bytes():
                    byte_list.append(_byte)
                
            active_track = len(byte_list)
            if 1 <= active_track:
                if self.enc_bool:
                    adjast_vol = 1 / sqrt(active_track)
                    audio_numpy:np.ndarray = np.sum([np.frombuffer(byte_list[i], dtype=np.int16) * adjast_vol for i in range(active_track)], axis=0)
                    audio_bytes = audio_numpy.astype(np.int16).tobytes()
                else:
                    audio_bytes = byte_list[0]

            # Loop Delay
            _start += 0.02
            delay = max(0, _start - time.perf_counter())
            time.sleep(delay)
 
            # Send Bytes
            if audio_bytes:
                fin_loop = 0
                try: send_audio(audio_bytes, encode=self.enc_bool)
                except Exception as e:
                    traceback.print_exc()
                    break
            # thread fin
            else:
                playing = 0
                for p in self.tracks:
                    playing += not p.is_paused()

                if playing == 0:
                    fin_loop += 1
                if (AudioTrack.FRAME_PER_SEC * 0.1) < fin_loop:
                    break



class AudioTrack:
    FRAME_LENGTH = opus.Encoder.FRAME_LENGTH / 1000 #Second
    FRAME_PER_SEC = 1000 / opus.Encoder.FRAME_LENGTH

    def __init__(self ,opus ,vc:'MultiAudioVoiceClient'):
        self.ffmpeg_audio:FFmpegReader | None = None
        self.audio_data:StreamAudioData | None = None
        self.Pausing:bool = True
        self.vc = vc
        self.timer:float = 0.0
        self.pitch = _Attribute[int](init=0, min=-60, max=60, update_asource=self.update_asouce_sec)
        self.speed = _Attribute[float](init=1.0, min=0.1, max=3.0, update_asource=self.update_asouce_sec)
        self.after:Callable[[], Any] | None = None
        self.opus:bool = opus
        self._lock = threading.RLock()

    async def play(self, sad:StreamAudioData, after:Callable[[], Any]):
        self.audio_data = sad
        self.ffmpeg_audio = sad.get_ffmpegaudio(self.opus, speed=self.speed.value, pitch=self.pitch.value)
        # 最初のロードは少し時間かかるから先にロード
        self.timer = 0.0
        self.after = after
        self.Pausing = False
        self._speaking(True)

    def resume(self):
        if self.Pausing:
            self.Pausing = False
            self._speaking(True)

    def pause(self):
        if not self.Pausing:
            self.Pausing = True
            self._speaking(False)

    def has_play_data(self):
        if self.audio_data:
            return True
        return False

    def is_paused(self):
        return self.Pausing

    def _speaking(self,status: bool):
        if self.audio_data and self.ffmpeg_audio:
            self.vc._speaking(status=status)

    async def skip_time(self, sec:float):
        if self.audio_data == None or self.ffmpeg_audio == None:
            return
        
        with self._lock:
            # n秒 進む
            if 0 < sec:
                skip_data_len = int(sec * self.FRAME_PER_SEC / self.speed.get())
                target_sec = self.timer + sec
                if self.audio_data.duration != None and self.audio_data.duration < target_sec:
                    self._finish()
                    return
                
                if len(self.ffmpeg_audio.next_q) + (AudioTrack.FRAME_PER_SEC*10) < skip_data_len:
                    await self.update_asouce_sec(sec=target_sec)
                    return
                while len(self.ffmpeg_audio.next_q) < skip_data_len and not self.ffmpeg_audio.read_all_task.done():
                    await asyncio.sleep(0.01)
                self.ffmpeg_audio.skip(skip_data_len)
                self.timer += skip_data_len * self.FRAME_LENGTH * self.speed.get()

            # n秒 前に戻る
            elif sec < 0:
                target_sec = self.timer + sec
                if target_sec < 0:
                    target_sec = 0
                    sec = -self.timer
                rwd_data_len = int(-sec * self.FRAME_PER_SEC / self.speed.get())
                self.ffmpeg_audio.rewind(rwd_data_len)
                self.timer += -rwd_data_len * self.FRAME_LENGTH * self.speed.get()


    def read_bytes(self) -> bytes:
        """別スレッドからの呼び出しを想定

        Returns
        -------
        bytes
            音声データ ない場合はb''
        """
        _byte = b''
        if self.ffmpeg_audio and self.Pausing == False:            
            # Read Bytes
            if self._lock.acquire(blocking=False):
                _byte = self.ffmpeg_audio.read()
                # 終了
                if _byte:
                    self.timer += (self.FRAME_LENGTH * self.speed.get())
                    self._lock.release()
                    return _byte
                
                self._lock.release()
                if _byte == None:
                    _byte = b''
                else:
                    self._finish()
        return _byte
            

    async def update_asouce_sec(self, sec:float|None=None):
        if not self.audio_data:
            return
        if sec is None:
            sec = self.timer

        with self._lock:
            self.ffmpeg_audio = self.audio_data.get_ffmpegaudio(self.opus, sec, speed=self.speed.value, pitch=self.pitch.value)
            self.timer = sec


    def _finish(self):
        self.ffmpeg_audio = None
        self.audio_data = None
        self._speaking(False)
        if self.after:
            self.after()
from concurrent.futures import ThreadPoolExecutor
import threading
import asyncio
import time
import traceback
import numpy as np
from collections import deque
from math import sqrt
from discord import SpeakingState, opus, Guild, FFmpegPCMAudio, FFmpegOpusAudio
from typing import TYPE_CHECKING, Any, Callable, Generic, Union

from main import IS_MAIN_PROCESS
from pi_yo_8.type import T
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



    async def get_ffmpegaudio(self, opus:bool, sec:float=0.0, speed:float=1.0, pitch:int=0) -> tuple[bytes, FFmpegOpusAudio | FFmpegPCMAudio]:
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

        def io() -> tuple[bytes, FFmpegOpusAudio | FFmpegPCMAudio]:
            ffmpeg = self._get_ffmpegaudio(opus, before_options, options)
            _byte = ffmpeg.read()
            return _byte, ffmpeg
        
        return await asyncio.get_event_loop().run_in_executor(self.exe, io)



class _Attribute(Generic[T]):
    def __init__(self, init:T, min:T, max:T, update_asource:Callable[..., Any]) -> None:
        self.value = init
        self.update_asource = update_asource
        self.min = min
        self.max = max
    
    def get(self) -> T:
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
        self.players:list['AudioTrack'] = []
        self.enc_bool = False
        self.info.vc.encoder = opus.Encoder()
        #self.vc.encoder.set_expected_packet_loss_percent(0.01)


    def kill(self):
        self.enable_loop = False


    def add_track(self ,RNum=0 ,opus=False) -> 'AudioTrack':
        player = AudioTrack(RNum ,opus=opus ,vc=self)
        self.players.append(player)
        self.enc_bool = (len(self.players) != 1 or len(self.players) == 1 and opus == False)
        return player

    def _speaking(self,status: bool):
        playing = 0
        for p in self.players:
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
            for _ in self.players:
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
                for p in self.players:
                    playing += not p.is_paused()

                if playing == 0:
                    fin_loop += 1
                if (AudioTrack.FRAME_PER_SEC * 0.1) < fin_loop:
                    break


            

class AudioTrack:
    FRAME_LENGTH = opus.Encoder.FRAME_LENGTH / 1000 #Second
    FRAME_PER_SEC = 1000 / opus.Encoder.FRAME_LENGTH

    def __init__(self ,rwd_buffer_size_sec:float ,opus ,vc:'MultiAudioVoiceClient'):
        self.ffmpeg_audio:FFmpegOpusAudio | FFmpegPCMAudio | None = None
        self.audio_data:StreamAudioData | None = None
        self.Pausing:bool = True
        self.vc = vc
        self.rwd_buffer_size = int(rwd_buffer_size_sec * self.FRAME_PER_SEC)
        self.timer:float = 0.0
        self.pitch = _Attribute[int](init=0, min=-60, max=60, update_asource=self.update_asouce_sec)
        self.speed = _Attribute[float](init=1.0, min=0.1, max=3.0, update_asource=self.update_asouce_sec)
        self.after:Callable[[], Any] | None = None
        self.opus:bool = opus
        self.QBytes = deque()
        self.RBytes = deque()
        self._lock = threading.Lock()
    

    async def play(self, sad:StreamAudioData, after:Callable[[], Any]):
        self.audio_data = sad
        _byte, self.ffmpeg_audio = await sad.get_ffmpegaudio(self.opus, speed=self.speed.value, pitch=self.pitch.value)
        # 最初のロードは少し時間かかるから先にロード
        self.QBytes.clear()
        self.QBytes.append(_byte)
        self.RBytes.clear()
        self.timer = 0.0
        self.after = after
        self.Pausing = False
        self._speaking(True)


    def stop(self):
        if self.ffmpeg_audio:
            self.pause()
            self.ffmpeg_audio.cleanup()
        self.ffmpeg_audio = None
        self.audio_data = None

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

    def skip_time(self, sec:float):
        # n秒 進む
        loop = asyncio.get_event_loop()
        if self.audio_data == None or self.ffmpeg_audio == None:
            return
        if 0 < sec:
            skip_len = int(sec * self.FRAME_PER_SEC / self.speed.get())
            if 300*self.FRAME_PER_SEC < skip_len:
                target_sec = self.timer + sec
                if self.audio_data.duration != None and self.audio_data.duration < target_sec:
                    self._finish()
                    return
                loop.create_task(self.update_asouce_sec(sec=target_sec))

            else:
                with self._lock:
                    was_paused = self.is_paused()
                    if not was_paused: self.pause()

                    self.timer += skip_len * self.FRAME_LENGTH * self.speed.get()
                    for _ in range(skip_len):
                        _byte = self.QBytes.popleft() if self.QBytes else self.ffmpeg_audio.read()
                        if not _byte:
                            self._finish()
                            break
                        self.RBytes.append(_byte)
                    if not was_paused: self.resume()

        # n秒 前に戻る
        elif sec < 0:
            target_sec = self.timer + sec
            if target_sec < 0:
                target_sec = 0
                sec = -self.timer
            rwd_len = int(-sec * self.FRAME_PER_SEC / self.speed.get())
            if len(self.RBytes) < rwd_len:
                loop.create_task(self.update_asouce_sec(sec=target_sec))

            else:
                with self._lock:
                    self.timer += -rwd_len * self.FRAME_LENGTH * self.speed.get()
                    for _ in range(rwd_len):
                        self.QBytes.appendleft(self.RBytes.pop())



    def read_bytes(self) -> bytes|None:
        if self.ffmpeg_audio:            
            # Read Bytes
            if self.Pausing == False:
                with self._lock:
                    _byte = self.QBytes.popleft() if self.QBytes else self.ffmpeg_audio.read()
                    # 終了
                    if not _byte:
                        self._finish()
                        return

                    self.timer += (self.FRAME_LENGTH * self.speed.get())
                    if self.rwd_buffer_size != 0:
                        self.RBytes.append(_byte)
                        while self.rwd_buffer_size < len(self.RBytes):
                            self.RBytes.popleft()
                return _byte


    async def update_asouce_sec(self, sec:float|None=None):
        if not self.audio_data:
            return
        if sec is None:
            sec = self.timer

        _byte, self.ffmpeg_audio = await self.audio_data.get_ffmpegaudio(self.opus, sec, speed=self.speed.value, pitch=self.pitch.value)
        self.timer = sec
        self.QBytes.clear()
        self.QBytes.append(_byte)
        self.RBytes.clear()


    def _finish(self):
        self.ffmpeg_audio = None
        self.audio_data = None
        self._speaking(False)
        if self.after:
            self.after()
import threading
import asyncio
import time
import logging
import numpy as np

from math import sqrt
from discord import SpeakingState, opus, Guild, FFmpegPCMAudio, FFmpegOpusAudio
from discord.ext import commands
from typing import Union, Optional

from .utils import run_check_storage


lock = threading.Lock()



class StreamAudioData:
    def __init__(self, 
                 st_url:str,
                 volume:Optional[int] = None):
        self.stream_url = st_url
        self.volume = volume


    def _get_ffmpegaudio(self, opus:bool, before_options:list, options:list) -> Union[FFmpegOpusAudio, FFmpegPCMAudio]:
        options = ' '.join(options)
        before_options = ' '.join(before_options)
        if opus:
            #options.extend(('-c:a', 'libopus', '-ar', '48000'))
            return FFmpegOpusAudio(self.stream_url, before_options=before_options, options=options)

        else:
            #options.extend(('-c:a', 'pcm_s16le', '-ar', '48000'))
            return FFmpegPCMAudio(self.stream_url, before_options=before_options, options=options)



    async def get_ffmpegaudio(self, opus:bool, sec:int=0, speed:float=1.0, pitch:int=0) -> Union[FFmpegOpusAudio, FFmpegPCMAudio]:
        before_options = []
        options = ['-vn', '-application', 'lowdelay', '-loglevel', 'quiet']
        #options = ['-vn', '-application', 'lowdelay']
        af = []

        # Sec
        if int(sec):
            before_options.extend(('-ss' ,str(sec)))
        before_options.extend(('-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5', '-analyzeduration', '2147483647', '-probesize', '2147483647'))
        
        # Pitch
        if pitch != 0:
            pitch = 2 ** (pitch / 12)
            af.append(f'rubberband=pitch={pitch}')
        
        if float(speed) != 1.0:
            af.append(f'rubberband=tempo={speed}')

        if self.volume:
            af.append(f'volume={self.volume}dB')
        
        # af -> str
        if af:
            options.extend(('-af', ','.join(af) ))

        return self._get_ffmpegaudio(opus, before_options, options)



class _Attribute:
    def __init__(self, init, min, max, update_asource) -> None:
        self.get = init
        self.update_asource = update_asource
        self.min = min
        self.max = max
    
    async def set(self, num):
        return await self._check(num)

    async def add(self, num):
        return await self._check(self.get + num)

    async def _check(self, num):
        if self.min <= num <= self.max:
            self.get = num
            await self.update_asource()
            return True



class MultiAudioVoiceClient:
    """
    Discord に存在する AudioPlayer は 同時に1つまでの音源の再生にしか対応していないため
    独自で Playerを作成 
    self.run は制御方法知らんから、常にループしてる 0.02秒(20ms) 間隔で 
    """
    def __init__(self, guild:Guild, client:commands.Bot, parent) -> None:
        self.enable_loop = True
        self.guild = guild
        self.loop = client.loop
        self.parent = parent
        self.players:list['AudioTrack'] = []
        self.pLen = 0
        self.guild.voice_client.encoder = opus.Encoder()
        #self.vc.encoder.set_expected_packet_loss_percent(0.01)
        self.enc_bool = False


    def kill(self):
        self.enable_loop = False


    def add_track(self ,RNum=0 ,opus=False) -> 'AudioTrack':
        player = AudioTrack(RNum ,opus=opus ,vc=self)
        self.players.append(player)
        self.P1_read_bytes = player.read_bytes
        self.pLen = len(self.players)
        self.enc_bool = (self.pLen != 1 or self.pLen == 1 and opus == False)
        return player

    def _speaking(self,status: bool):
        playing = 0
        for p in self.players:
            if not p.is_paused():
                playing += 1
        if status:
            if playing == 1:
                self.__speak(SpeakingState.voice)
                with lock:
                    if not self.run_loop.is_running:
                        self.run_loop.set_running(True)
                        threading.Thread(target=self.run_loop,daemon=True).start()
        else:
            if playing == 0:
                self.__speak(SpeakingState.none)


    def __speak(self, speaking: SpeakingState) -> None:
        """
        これ (self._speak) がないと謎にバグる ※botがjoinしたときに居たメンツにしか 音が聞こえない
        友達が幻聴を聞いてたら怖いよね
        """
        try:
            asyncio.run_coroutine_threadsafe(self.vc.ws.speak(speaking), self.loop)
        except Exception:
            pass

    @run_check_storage()
    def run_loop(self):
        """
        音声データをを送る　別スレッドで動作する 
        音声データ (Bytes) を取得し、必要があれば Numpy で読み込んで 合成しています
        最後に音声データ送信
        """
        send_audio = self.guild.voice_client.send_audio_packet
        _start = time.perf_counter()
        fin_loop = 0
        while self.enable_loop:
            Bytes = None
            if self.pLen == 1:
                Bytes = self.P1_read_bytes()

            elif 2 <= self.pLen:
                byte_list = []
                byte_append = byte_list.append
                for _ in self.players:
                    if _byte := _.read_bytes():
                        byte_append(_byte)
                
                active_track = len(byte_list)
                if 1 <= active_track:
                    
                    if active_track == 1:
                        byte_numpy:np.ndarray = np.frombuffer(byte_list[0], dtype=np.int16)

                    else:
                        target_vol = sqrt(active_track * 2) / active_track
                        byte_numpy = np.frombuffer(byte_list.pop(0), dtype=np.int16) * target_vol
                        for _ in byte_list:
                            byte_numpy = byte_numpy + np.frombuffer(_, dtype=np.int16) * target_vol

                    Bytes = byte_numpy.astype(np.int16).tobytes()

            # Loop Delay
            _start += 0.02
            delay = max(0, _start - time.perf_counter())
            time.sleep(delay)
 
            # Send Bytes
            if Bytes:
                fin_loop = 0
                try: send_audio(Bytes, encode=self.enc_bool)
                except Exception as e:
                    print(f'Error send_audio_packet : {e}')
                    break
            # thread fin
            else:
                fin_loop += 1
                if (50 * 20) < fin_loop:
                    break


            

class AudioTrack:
    def __init__(self ,RNum ,opus ,vc:'MultiAudioVoiceClient'):
        self.ffmpeg_audio = None
        self.audio_data = None
        self.Pausing = True
        self.vc = vc
        self.RNum = RNum*50
        self.timer:float = 0.0
        self.pitch = _Attribute(init=0, min=-60, max=60, update_asource=self.update_asouce_sec)
        self.speed = _Attribute(init=1.0, min=0.1, max=3.0, update_asource=self.update_asouce_sec)
        self.read_fin = False
        self.After = None
        self.opus = opus
        self.QBytes = []
        self.RBytes = []
    

    async def play(self,sad:StreamAudioData,after):
        self.audio_data = sad
        self.ffmpeg_audio = await sad.get_ffmpegaudio(self.opus, speed=self.speed.get, pitch=self.pitch.get)
        # 最初のロードは少し時間かかるから先にロード
        self.QBytes.clear()
        self.RBytes.clear()
        self.timer = 0.0
        self.read_fin = False
        self.After = after
        self.Pausing = False
        self._speaking(True)


    def stop(self):
        if self.ffmpeg_audio:
            self.pause()
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

    def is_playing(self):
        if self.audio_data:
            return True
        return False

    def is_paused(self):
        return self.Pausing

    def _speaking(self,status: bool):
        self.vc._speaking(status=status)

    def skip_time(self, stime:int):
        # n秒 進む
        loop = asyncio.get_event_loop()
        if 0 < stime:
            if len(self.QBytes) < stime:
                target_time = int(self.timer) + stime
                target_sec = target_time // 50
                if target_sec > self.audio_data.st_sec:
                    self._finish()
                    return
                loop.create_task(self.update_asouce_sec(sec=target_sec))

            else:
                with lock:
                    self.timer += float(stime)
                self.RBytes.extend(self.QBytes[:stime])
                del self.QBytes[:stime]

        # n秒 前に戻る
        elif stime < 0:
            stime = -stime
            target_time = int(self.timer) - stime
            if target_time < 0:
                stime += target_time

            if len(self.RBytes) < stime:
                target_sec = target_time // 50
                if target_sec < 0: target_sec = 0
                loop.create_task(self.update_asouce_sec(sec=target_sec))

            else:
                with lock:
                    self.QBytes = self.RBytes[-stime:] + self.QBytes
                    self.timer -= float(stime)
                del self.RBytes[-stime:]



    def read_bytes(self):
        if self.ffmpeg_audio:            
            # Read Bytes
            if len(self.QBytes) <= (45 * 50):
                self._read_bytes()

            if self.Pausing == False:
                #print(len(self.QBytes))
                if self.QBytes:
                    _byte = self.QBytes.pop(0)
                    # 終了
                    if _byte == 'Fin':
                        self._finish()
                        return

                    with lock:
                        self.timer += (1.0 * self.speed.get)
                        if self.RNum != 0:
                            self.RBytes.append(_byte)
                            if len(self.RBytes) > self.RNum:
                                del self.RBytes[:len(self.RBytes) - self.RNum]

                    return _byte


    async def update_asouce_sec(self, time=None, sec=None):
        if time == None and sec == None:
            time = self.timer
        if time != None:
            sec = time // 50

        self.ffmpeg_audio = await self.audio_data.get_ffmpegaudio(self.opus, sec, speed=self.speed.get, pitch=self.pitch.get)
        self.timer = float(sec * 50)
        self.QBytes.clear()
        self.RBytes.clear()
        self.read_fin = False



    def _finish(self):
        self.ffmpeg_audio = None
        self.audio_data = None
        self._speaking(False)
        if self.After:
            self.After()


    def _read_bytes(self):
        if self.read_fin or self.read_bytes_loop.is_running: return
        self.read_bytes_loop.set_running(True)
        threading.Thread(target=self.read_bytes_loop, daemon=True).start()


    @run_check_storage()
    def read_bytes_loop(self):
        while len(self.QBytes) <= (90 * 50) and self.vc.enable_loop:
            if byte := self.ffmpeg_audio.read():
                self.QBytes.append(byte)
            else: 
                self.read_fin = True
                self.QBytes.append('Fin')
                break
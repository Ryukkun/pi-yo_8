import threading
import asyncio
import time
import numpy as np

from discord import SpeakingState, opus, Guild
from discord.ext import commands

from .audio_source import StreamAudioData


lock = threading.Lock()


class _Attribute:
    def __init__(self, init, min, max, update_asource) -> None:
        self.get = init
        self.update_asource = update_asource
        self.min = min
        self.max = max
    
    async def set(self, num):
        res = await self._check(num)
        return res

    async def add(self, num):
        res = await self._check(self.get + num)
        return res

    async def _check(self, num):
        if self.min <= num <= self.max:
            self.get = num
            await self.update_asource()
            return True



class MultiAudio:
    """
    Discord に存在する AudioPlayer は 同時に1つまでの音源の再生にしか対応していないため
    独自で Playerを作成 
    self.run は制御方法知らんから、常にループしてる 0.02秒(20ms) 間隔で 
    """
    def __init__(self, guild:Guild, client:commands.Bot, parent) -> None:
        self.loop = True
        self.guild = guild
        self.gid = guild.id
        self.vc = guild.voice_client
        self.CLoop = client.loop
        self.Parent = parent
        self.Players:list['_AudioTrack'] = []
        self.PLen = 0
        self.vc.encoder = opus.Encoder()
        self.vc.encoder.set_expected_packet_loss_percent(0.0)
        self.Enc_bool = False
        self.doing = {'run_loop':False}


    def kill(self):
        self.loop = False
        for P in self.Players:
            P._read_bytes(False)


    def add_player(self ,RNum=0 ,opus=False) -> '_AudioTrack':
        player = _AudioTrack(RNum ,opus=opus ,parent=self)
        self.Players.append(player)
        self.P1_read_bytes = player.read_bytes
        self.PLen = len(self.Players)
        self.Enc_bool = (self.PLen != 1 or self.PLen == 1 and opus == False)
        return player

    def _speaking(self,status: bool):
        playing = 0
        for P in self.Players:
            if not P.is_paused():
                playing += 1
        if status:
            if playing == 1:
                self.__speak(SpeakingState.voice)
                with lock:
                    if not self.doing['run_loop']:
                        self.doing['run_loop'] = True
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
            asyncio.run_coroutine_threadsafe(self.Parent.vc.ws.speak(speaking), self.Parent.vc.client.loop)
        except Exception:
            pass


    def run_loop(self):
        """
        音声データをを送る　別スレッドで動作する 
        音声データ (Bytes) を取得し、必要があれば Numpy で読み込んで 合成しています
        最後に音声データ送信
        """
        send_audio = self.vc.send_audio_packet
        _start = time.perf_counter()
        fin_loop = 0
        while self.loop:
            Bytes = None
            if self.PLen == 1:
                Bytes = self.P1_read_bytes()

            elif self.PLen >= 2:
                for P in self.Players:
                    _Byte = P.read_bytes(numpy=True)
                    if _Byte != None:
                        if Bytes == None:
                            Bytes = _Byte
                            continue
                        Bytes += _Byte
                Bytes = Bytes.astype(np.int16).tobytes()

            # Loop Delay
            _start += 0.02
            delay = max(0, _start - time.perf_counter())
            if delay == 0:
                #print(-(_start - time.perf_counter()))
                if (_start - time.perf_counter()) <= -0.5:
                    _start = time.perf_counter() + 0.02
                    delay = 0.02
            time.sleep(delay)
 
            # Send Bytes
            if Bytes:
                fin_loop = 0
                try:send_audio(Bytes, encode=self.Enc_bool)
                except Exception as e:
                    print(f'Error send_audio_packet : {e}')
                    time.sleep(10)
            # thread fin
            else:
                fin_loop += 1
                if 1500 < fin_loop:
                    break

        self.doing['run_loop'] = False
            

class _AudioTrack:
    def __init__(self ,RNum ,opus ,parent:'MultiAudio'):
        self.AudioSource = None
        self._SAD = None
        self.Pausing = True
        self.Parent = parent
        self.RNum = RNum*50
        self.Timer:float = 0.0
        self.pitch = _Attribute(init=0, min=-60, max=60, update_asource=self.update_asouce_sec)
        self.speed = _Attribute(init=1.0, min=-0.1, max=3.0, update_asource=self.update_asouce_sec)
        self.read_fin = False
        self.read_loop = False
        self.After = None
        self.opus = opus
        self.QBytes = []
        self.RBytes = []
        self.Duration = None
        self.first_delay = False
    

    async def play(self,_SAD:StreamAudioData,after):
        self._SAD = _SAD
        self.Duration = _SAD.st_sec
        AudioSource = await _SAD.AudioSource(self.opus, speed=self.speed.get, pitch=self.pitch.get)
        # 最初のロードは少し時間かかるから先にロード
        self.QBytes.clear()
        self.RBytes.clear()
        self.AudioSource = AudioSource
        self.Timer = 0.0
        self.read_fin = False
        self.After = after
        self.first_delay = False
        self.resume()

    def stop(self):
        if self.AudioSource:
            self.pause()
        self.AudioSource = None
        self._SAD = None

    def resume(self):
        self.Pausing = False
        self._speaking(True)

    def pause(self):
        self.Pausing = True
        self._speaking(False)

    def is_playing(self):
        if self._SAD:
            return True
        return False

    def is_paused(self):
        return self.Pausing

    def _speaking(self,status: bool):
        self.Parent._speaking(status=status)

    def skip_time(self, stime:int):
        # n秒 進む
        if 0 < stime:
            if len(self.QBytes) < stime:
                target_time = int(self.Timer) + stime
                target_sec = target_time // 50
                if target_sec > self._SAD.st_sec:
                    self._finish()
                    return
                self.Parent.CLoop.create_task(self._new_asouce_sec(target_sec))

            else:
                with lock:
                    self.Timer += float(stime)
                self.RBytes.extend(self.QBytes[:stime])
                del self.QBytes[:stime]

        # n秒 前に戻る
        elif stime < 0:
            stime = -stime
            target_time = int(self.Timer) - stime
            if target_time < 0:
                stime += target_time

            if len(self.RBytes) < stime:
                target_sec = target_time // 50
                if target_sec < 0: target_sec = 0
                self.Parent.CLoop.create_task(self._new_asouce_sec(target_sec))

            else:
                with lock:
                    self.QBytes = self.RBytes[-stime:] + self.QBytes
                    self.Timer -= float(stime)
                del self.RBytes[-stime:]



    def read_bytes(self, numpy=False):
        if self.AudioSource:            
            # Read Bytes
            if len(self.QBytes) <= (45 * 50):
                self._read_bytes(True)
            
            if not self.QBytes:
                self.first_delay = True
                return
            if self.first_delay:
                if (3 * 50) < len(self.QBytes):
                    self.first_delay = False
                else:
                    return

            if self.Pausing == False:
                #print(len(self.QBytes))
                if self.QBytes:
                    _byte = self.QBytes.pop(0)
                    # 終了
                    if _byte == 'Fin':
                        self._finish()
                        return

                    with lock:
                        self.Timer += (1.0 * self.speed.get)
                        if self.RNum != 0:
                            self.RBytes.append(_byte)
                            if len(self.RBytes) > self.RNum:
                                del self.RBytes[:len(self.RBytes) - self.RNum]

                    if numpy:
                        return np.frombuffer(_byte,np.int16)
                    return _byte


    async def _new_asouce_sec(self, sec):
        self.AudioSource = await self._SAD.AudioSource(self.opus, sec, speed=self.speed.get, pitch=self.pitch.get)
        self.Timer = float(sec * 50)
        self.QBytes.clear()
        self.RBytes.clear()
        self.read_fin = False
        self.first_delay = False


    async def update_asouce_sec(self):
        await self._new_asouce_sec(self.Timer // 50)


    def _finish(self):
        self.AudioSource = None
        self._SAD = None
        self._speaking(False)
        if self.After:
            self.After()


    def _read_bytes(self, status):
        if status:
            if self.read_loop or self.read_fin: return
            self.read_loop = True
            threading.Thread(target=self.__read_bytes, daemon=True).start()
        
        else:
            self.read_loop = False


    def __read_bytes(self):
        try:
            while len(self.QBytes) <= (90 * 50) and self.read_loop:
                if byte := self.AudioSource.read():
                    self.QBytes.append(byte)
                else: 
                    self.read_fin = True
                    self.QBytes.append('Fin')
                    break
        except Exception:
            pass

        self.read_loop = False
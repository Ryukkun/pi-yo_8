import threading
import asyncio
import time
import numpy as np

from discord import SpeakingState, opus, Guild
from discord.ext import commands

from .audio_source import StreamAudioData


lock = threading.Lock()

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
        self.Players = []
        self.PLen = 0
        self.vc.encoder = opus.Encoder()
        self.vc.encoder.set_expected_packet_loss_percent(0.0)
        self.Enc_bool = False
        threading.Thread(target=self.run,daemon=True).start()

    def add_player(self ,RNum=0 ,opus=False) -> '_APlayer':
        player = _APlayer(RNum ,opus=opus ,parent=self)
        self.Players.append(player)
        self.P1_read_bytes = player.read_bytes
        self.PLen = len(self.Players)
        self.Enc_bool = (self.PLen != 1 or self.PLen == 1 and opus == False)
        return player

    def _speaking(self,status: bool):
        temp = 0
        for P in self.Players:
            if P.Loop:
                temp += 1
        if status:
            if temp == 0:
                self.__speak(SpeakingState.voice)
        else:
            if temp == 1:
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


    def kill(self):
        self.loop = False
        for P in self.Players:
            P._read_bytes(False)


    def run(self):
        """
        これずっとloopしてます 止まりません loopの悪魔
        音声データ (Bytes) を取得し、必要があれば Numpy で読み込んで 合成しています
        最後に音声データ送信
        """
        send_audio = self.vc.send_audio_packet
        _start = time.perf_counter()
        P: _APlayer
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
                try:send_audio(Bytes, encode=self.Enc_bool)
                except Exception as e:
                    print(f'Error send_audio_packet : {e}')
                    time.sleep(1)

            

class _APlayer:
    def __init__(self ,RNum ,opus ,parent:'MultiAudio'):
        self.AudioSource = None
        self._SAD = None
        self.Pausing = False
        self.Parent = parent
        self.RNum = RNum*50
        self.Timer = 0
        self.read_fin = False
        self.read_loop = False
        self.After = None
        self.opus = opus
        self.QBytes = []
        self.RBytes = []
        self.Duration = None
        self.Loop = False
    

    async def play(self,_SAD:StreamAudioData,after):
        self._SAD = _SAD
        self.Duration = _SAD.St_Sec
        AudioSource = await _SAD.AudioSource(self.opus)
        # 最初のロードは少し時間かかるから先にロード
        self.QBytes.clear()
        self.RBytes.clear()
        self.AudioSource = AudioSource
        self.Timer = 0
        self.read_fin = False
        self.After = after
        self.resume()

    def stop(self):
        if self.AudioSource:
            self._speaking(False)
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
        self.Loop = status

    def skip_time(self, stime:int):
        # n秒 進む
        if 0 < stime:
            if len(self.QBytes) < stime:
                target_time = self.Timer + stime
                target_sec = target_time // 50
                if target_sec > self._SAD.St_Sec:
                    self._finish()
                    return
                self.Parent.CLoop.create_task(self._new_asouce_sec(target_sec))

            else:
                with lock:
                    self.Timer += stime
                self.RBytes.extend(self.QBytes[:stime])
                del self.QBytes[:stime]

        # n秒 前に戻る
        elif stime < 0:
            stime = -stime
            target_time = self.Timer - stime
            if target_time < 0:
                stime += target_time

            if len(self.RBytes) < stime:
                target_sec = target_time // 50
                if target_sec < 0: target_sec = 0
                self.Parent.CLoop.create_task(self._new_asouce_sec(target_sec))

            else:
                with lock:
                    self.QBytes = self.RBytes[-stime:] + self.QBytes
                    self.Timer -= stime
                del self.RBytes[-stime:]



    def read_bytes(self, numpy=False):
        if self.AudioSource:            
            # Read Bytes
            if len(self.QBytes) <= (45 * 50):
                self._read_bytes(True)

            if self.Pausing == False:
                #print(len(self.QBytes))
                if self.QBytes:
                    _byte = self.QBytes.pop(0)
                    # 終了
                    if _byte == 'Fin':
                        self._finish()
                        return

                    with lock:
                        self.Timer += 1
                        if self.RNum != 0:
                            self.RBytes.append(_byte)
                            if len(self.RBytes) > self.RNum:
                                del self.RBytes[:len(self.RBytes) - self.RNum]

                    if numpy:
                        return np.frombuffer(_byte,np.int16)
                    return _byte


    async def _new_asouce_sec(self, sec):
        self.AudioSource = await self._SAD.AudioSource(self.opus, sec)
        self.Timer = sec * 50
        self.QBytes.clear()
        self.RBytes.clear()
        self.read_fin = False


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
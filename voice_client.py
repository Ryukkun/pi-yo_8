import threading
import asyncio
import time
import numpy as np

from types import NoneType
from typing import Optional
from discord import SpeakingState, opus, Guild
from discord.ext import commands

from audio_source import StreamAudioData

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
        self.Players = {}
        self.PLen = 0
        self.vc.encoder = opus.Encoder()
        self.vc.encoder.set_expected_packet_loss_percent(0.0)
        self.play_audio = self.vc.send_audio_packet
        self.Enc_bool = False
        threading.Thread(target=self.run,daemon=True).start()

    def add_player(self ,name ,RNum ,opus=False ,def_getbyte=None) -> '_APlayer':
        self.Players[name] = _APlayer(RNum ,opus=opus ,def_getbyte=def_getbyte ,parent=self)
        self.PLen = len(self.Players)
        self.Enc_bool = (self.PLen != 1 or self.PLen == 1 and opus == False)
        return self.Players[name]

    def _speaking(self,status: bool):
        temp = 0
        for P in self.Players.values():
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
        これ（self._speak）がないと謎にバグる ※botがjoinしたときに居たメンツにしか 音が聞こえない
        友達が幻聴を聞いてたら怖いよね
        """
        try:
            asyncio.run_coroutine_threadsafe(self.Parent.vc.ws.speak(speaking), self.Parent.vc.client.loop)
        except Exception:
            pass


    def kill(self):
        self.loop = False
        for P in self.Players.values():
            P._read_bytes(False)


    def run(self):
        """
        これずっとloopしてます 止まりません loopの悪魔
        音声データ（Bytes）を取得し、必要があれば Numpy で読み込んで 合成しています
        最後に音声データ送信　ドルチェ
        """
        _start = time.perf_counter()
        delay = 1
        P: _APlayer
        while self.loop:
            Bytes = None
            if self.PLen == 1:
                P = list(self.Players.values())[0]
                Bytes = P.read_bytes()
                if Bytes != NoneType and P.def_getbyte:
                    P.def_getbyte()
            elif self.PLen >= 2:
                for P in self.Players.values():
                    _Byte = P.read_bytes(numpy=True)
                    if _Byte != NoneType:
                        if P.def_getbyte:
                            P.def_getbyte()

                        if Bytes == NoneType:
                            Bytes = _Byte
                            continue
                        Bytes += _Byte
                Bytes = Bytes.astype(np.int16).tobytes()

            # Loop Delay
            _start += 0.02
            delay = max(0, _start - time.perf_counter())
            time.sleep(delay)
            # if delay == 0:
            #     print(time.perf_counter() - _start)
 
            # Send Bytes
            if Bytes:
                #print(Bytes)
                try:self.play_audio(Bytes, encode=self.Enc_bool)
                except Exception as e:
                    print(f'Error send_audio_packet : {e}')
                    time.sleep(1)

            

class _APlayer:
    def __init__(self ,RNum ,opus ,def_getbyte ,parent):
        self.AudioSource = None
        self._SAD = None
        self.Pausing = False
        self.Parent:MultiAudio = parent
        self.RNum = RNum
        self.Timer = 0
        self.TargetTimer = 0
        self.read_fin = False
        self.read_loop = False
        self.After = None
        self.def_getbyte = def_getbyte
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
        self.QBytes = []
        self.RBytes = []
        self.AudioSource = AudioSource
        self.Timer = 0
        self.TargetTimer = 0
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


    def read_bytes(self, numpy=False):
        if self.AudioSource:
            # n秒 進む
            if self.Timer < self.TargetTimer:
                Dif = self.TargetTimer - self.Timer

                if len(self.QBytes) < Dif:
                    sec = self.TargetTimer // 50
                    if sec > self._SAD.St_Sec:
                        self._finish()
                        return
                    self.Timer = self.TargetTimer
                    self.Parent.CLoop.create_task(self._new_asouce_sec(sec))


                else:
                    self.Timer = self.TargetTimer
                    self.RBytes += self.QBytes[:Dif]
                    del self.QBytes[:Dif]


            # n秒 前に戻る
            if self.Timer > self.TargetTimer:
                Dif = self.Timer - self.TargetTimer

                if len(self.RBytes) < Dif:
                    sec = self.TargetTimer // 50
                    if sec < 0: sec = 0
                    self.Timer = self.TargetTimer
                    self.Parent.CLoop.create_task(self._new_asouce_sec(sec))

                else:
                    self.QBytes = self.RBytes[-Dif:] + self.QBytes
                    del self.RBytes[-Dif:]
                    self.Timer = self.TargetTimer
            
            # Read Bytes
            if len(self.QBytes) <= (45 * 50) and self.read_fin == False:
                self._read_bytes(True)

            if self.Pausing == False:
                #print(len(self.QBytes))
                if self.QBytes:
                    temp = self.QBytes[0]
                    # 終了
                    if temp == 'Fin':
                        self._finish()
                        return

                    self.Timer += 1
                    self.TargetTimer += 1
                    del self.QBytes[0]
                    self.RBytes.append(temp)
                    if self.RNum != -1:
                        if len(self.RBytes) > (self.RNum * 50):
                            del self.RBytes[:len(self.RBytes) - (self.RNum * 50)]

                    if numpy:
                        return np.frombuffer(temp,np.int16)
                    return temp


    async def _new_asouce_sec(self, sec):
        self.AudioSource = await self._SAD.AudioSource(self.opus, sec)
        self.Timer = self.TargetTimer = sec * 50
        self.QBytes = []
        self.RBytes = []
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
            while len(self.QBytes) <= (90 * 50) and self.read_loop:
                try:
                    if temp := self.AudioSource.read():
                        #print(temp)
                        self.QBytes.append(temp)
                    else: 
                        self.read_fin = True
                        self.QBytes.append('Fin')
                        break
                except Exception:
                    break

            self.read_loop = False
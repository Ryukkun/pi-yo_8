import threading
import asyncio
import time

import numpy as np

from json import load as json_load
from discord import opus, SpeakingState
from types import NoneType


class MultiAudio(threading.Thread):
    """
    Discord に存在する AudioPlayer は 同時に1つまでの音源の再生にしか対応していないため
    独自で Playerを作成 
    self.run は制御方法知らんから、常にループしてる 0.02秒(20ms) 間隔で 
    """
    def __init__(self,guild,client,parent) -> None:
        self.loop = True
        super(MultiAudio, self).__init__(daemon=True)
        self.guild = guild
        self.gid = guild.id
        self.vc = guild.voice_client
        self.CLoop = client.loop
        self.Parent = parent
        self.Music = _APlayer(self)
        self.play_audio = self.vc.send_audio_packet
        self.old_time = 0



    def _update_embed(self):
        # 秒数更新のため
        if 0 <= self.Music.Timer < (50*60):
            if (self.Music.Timer % (50*5)) == 1:
                self.CLoop.create_task(self.Parent.Music.Update_Embed())
        elif (50*60) <= self.Music.Timer < (50*1800):
            if (self.Music.Timer % (50*10)) == 1:
                self.CLoop.create_task(self.Parent.Music.Update_Embed())
        elif (50*1800) <= self.Music.Timer:
            if (self.Music.Timer % (50*30)) == 1:
                self.CLoop.create_task(self.Parent.Music.Update_Embed())


    def run(self):
        """
        これずっとloopしてます 止まりません loopの悪魔
        音声データ（Bytes）を取得し、必要があれば Numpy で読み込んで 合成しています
        最後に音声データ送信　ドルチェ
        """
        _start = time.perf_counter()
        while self.loop:
            Bytes = self.Music.read_bytes()

            # Loop Delay
            _start += 0.02
            delay = max(0, _start - time.perf_counter())
            time.sleep(delay)
 
            # Send Bytes
            if Bytes:
                self._update_embed()
                try:self.play_audio(Bytes, encode=False)
                except OSError:
                    print('Error send_audio_packet OSError')
                    time.sleep(1)

            

class _APlayer():
    def __init__(self,parent):
        self.AudioSource = None
        self._SAD = None
        self.Pausing = False
        self.Parent = parent
        self.Timer = 0
        self.After = None
        self.QBytes = None
        self.Duration = None
        self.Loop = False
        

    async def play(self,_SAD,after):
        self._SAD = _SAD
        self.Duration = _SAD.St_Sec
        AudioSource = await _SAD.AudioSource()
        # 最初のロードは少し時間かかるから先にロード
        self.QBytes = AudioSource.read()
        self.AudioSource = AudioSource
        self.Timer = 0
        self.After = after
        self.resume()

    def stop(self):
        self.AudioSource = None
        self._SAD = None
        self._speaking(False)

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
        if status:
            self._speak(SpeakingState.voice)
        else:
            self._speak(SpeakingState.none)
        self.Loop = status


    def _speak(self, speaking: SpeakingState) -> None:
        """
        これ（self._speak）がないと謎にバグる ※botがjoinしたときに居たメンツにしか 音が聞こえない
        友達が幻聴を聞いてたら怖いよね
        ついでにLOOPの制御も
        """
        try:
            asyncio.run_coroutine_threadsafe(self.Parent.vc.ws.speak(speaking), self.Parent.vc.client.loop)
        except Exception:
            pass



    def read_bytes(self):
        if self.AudioSource and self.Pausing == False:
            
            if self.QBytes:
                self.Timer += 1
                temp = self.QBytes
                self.QBytes = None
                return temp
            if Bytes := self.AudioSource.read():
                self.Timer += 1
                return Bytes
            else:
                self.AudioSource = None
                self._SAD = None
                self._speaking(False)
                self.After()
            
        return None
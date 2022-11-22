import threading
import asyncio
import time

from discord import SpeakingState


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


    def kill(self):
        self.loop = False
        self.Music._read_bytes(False)


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
        global _start, delay
        _start = time.perf_counter()
        delay = 1
        while self.loop:
            Bytes = self.Music.read_bytes()

            # Loop Delay
            _start += 0.02
            delay = max(0, _start - time.perf_counter())
            time.sleep(delay)
            # if delay == 0:
            #     print(time.perf_counter() - _start)
 
            # Send Bytes
            if Bytes:
                self._update_embed()
                try:self.play_audio(Bytes, encode=False)
                except OSError:
                    #print('Error send_audio_packet OSError')
                    time.sleep(1)

            

class _APlayer():
    def __init__(self,parent):
        self.AudioSource = None
        self._SAD = None
        self.Pausing = False
        self.Parent = parent
        self.Timer = 0
        self.TargetTimer = 0
        self.read_fin = False
        self.read_loop = False
        self.After = None
        self.QBytes = []
        self.RBytes = []
        self.Duration = None
        self.Loop = False
        

    async def play(self,_SAD,after):
        self._SAD = _SAD
        self.Duration = _SAD.St_Sec
        AudioSource = await _SAD.AudioSource()
        # 最初のロードは少し時間かかるから先にロード
        self.QBytes = [AudioSource.read()]
        self.RBytes = []
        self.AudioSource = AudioSource
        self.Timer = 0
        self.TargetTimer = 0
        self.read_fin = False
        self.After = after
        self.resume()

    def stop(self):
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
        if status:
            self._speak(SpeakingState.voice)
        else:
            self._speak(SpeakingState.none)
        self.Loop = status


    def _speak(self, speaking: SpeakingState) -> None:
        """
        これ（self._speak）がないと謎にバグる ※botがjoinしたときに居たメンツにしか 音が聞こえない
        友達が幻聴を聞いてたら怖いよね
        """
        try:
            asyncio.run_coroutine_threadsafe(self.Parent.vc.ws.speak(speaking), self.Parent.vc.client.loop)
        except Exception:
            pass



    def read_bytes(self):
        if self.AudioSource and self.Pausing == False:
            
            # n秒 進む
            if self.Timer < self.TargetTimer:
                Dif = self.TargetTimer - self.Timer
                if len(self.QBytes) < Dif:
                    if not self.QBytes and self.read_fin:
                        self.Timer = self._SAD.St_Sec * 50
                        self.TargetTimer = self.Timer
                    else:
                        self.Timer += len(self.QBytes)
                        self.RBytes += self.QBytes
                        self.QBytes = []
                        self._read_bytes(True)
                        return
                else:
                    self.Timer = self.TargetTimer
                    self.RBytes += self.QBytes[:Dif]
                    del self.QBytes[:Dif]

            # n秒 前に戻る
            if self.Timer > self.TargetTimer:
                Dif = self.Timer - self.TargetTimer
                if len(self.RBytes) <= Dif:
                    self.Timer -= len(self.RBytes)
                    self.TargetTimer = self.Timer
                    #print(self.Timer)
                    self.QBytes = self.RBytes + self.QBytes
                    self.RBytes = []
                else:
                    self.QBytes = self.RBytes[-Dif:] + self.QBytes
                    del self.RBytes[-Dif:]
                    self.Timer = self.TargetTimer

            # Read Bytes
            if len(self.QBytes) <= (60 * 50) and self.read_fin == False:
                self._read_bytes(True)

            if self.QBytes:
                temp = self.QBytes[0]
                if temp == 'Fin':
                    self.AudioSource = None
                    self._SAD = None
                    self._speaking(False)
                    self.After()
                    return

                self.Timer += 1
                self.TargetTimer += 1
                #print(len(self.QBytes))
                del self.QBytes[0]
                self.RBytes.append(temp)
                if len(self.RBytes) > (600 * 50):
                    del self.RBytes[:len(self.RBytes) - (600 * 50)]
                return temp

            

    def _read_bytes(self, status):
        if status:
            if self.read_loop or self.read_fin: return
            self.read_loop = True
            threading.Thread(target=self.__read_bytes, daemon=True).start()
        
        else:
            self.read_loop = False


    def __read_bytes(self):
            while len(self.QBytes) <= (120 * 50) and self.read_loop:
                if temp := self.AudioSource.read():
                    self.QBytes.append(temp)
                else: 
                    self.read_fin = True
                    self.QBytes.append('Fin')
                    break

            self.read_loop = False
import re
import random
import time
import tabulate
import asyncio

from discord import Embed, NotFound, TextChannel, Reaction, Message
from discord.ext import tasks

from .audio_source import StreamAudioData as SAD
from .view import CreateButton

if __name__ == '__main__':
    from ..main import DataInfo

re_URL_YT = re.compile(r'https://((www.|)youtube.com|youtu.be)/')
re_URL_Video = re.compile(r'https://((www.|)youtube.com/watch\?v=|(youtu.be/))(.+)')
re_URL_PL = re.compile(r'https://(www.|)youtube.com/playlist\?list=')
re_skip = re.compile(r'^((-|)\d+)([hms])$')
re_skip_set_h = re.compile(r'^(\d+):(\d+):(\d+)$')
re_skip_set_m = re.compile(r'^(\d+):(\d+)$')





class MusicController():
    def __init__(self, _Info):
        try: Info:DataInfo
        except Exception: pass
        Info = _Info
        self.Info = Info
        self.MA = Info.MA
        self.Mvc = Info.MA.add_player('Music' ,RNum=30 ,opus=True)
        self.guild = Info.guild
        self.gid = Info.gid
        self.gn = Info.gn
        self.vc = self.guild.voice_client
        self.Queue = []
        self.Index_PL = None
        self.Next_PL = {'PL':[],'index':None}
        self.PL = []
        self.Latest_CH:TextChannel = None
        self.status = {'loop':True,'loop_pl':True,'random_pl':True}
        self.last_status = self.status.copy()
        self.Rewind = []
        self.CLoop = Info.loop
        self.Embed_Message = None
        self.def_doing = {'_playing':False,'_load_next_pl':False}
        self.last_embed_update:float = 0.0
        self.run_loop.start()

    async def _play(self, ctx, args, Q):
        # 一時停止していた場合再生 開始
        if args == ():
            if self.Mvc.is_paused():
                self.Mvc.resume()
            return
        else:
            arg = ' '.join(args)


        # 君は本当に動画なのかい　どっちなんだい！
        res = await SAD(arg).Check()
        if not res: return

        self.Latest_CH = ctx.channel

        if type(res) == tuple:
            self.Index_PL = self.Next_PL['index'] = res[0] - 1
            self.status['random_pl'] = res[1]
            self.PL = res[2]
            self.Next_PL['PL'] = []

            self.status['loop'] = False
            self.Queue = []
            self.last_status = self.status.copy()

            # 再生
            await self.play_loop(None,0)
            if self.Mvc.is_paused():
                self.Mvc.resume()

        else:
            # playlist 再生中のお客様はお断り
            if self.PL:
                self.PL = []
                self.Index_PL = None

            #Queueに登録
            if Q:
                self.Queue.append(res)
            else:
                if self.Queue == []:
                    self.Queue.append(res)
                else:
                    self.Queue[0] = res

            # 再生されるまでループ
            if Q:
                if not self.Mvc.is_playing():
                    await self.play_loop(None,0)
                if self.Mvc.is_paused():
                    self.Mvc.resume()
            else:
                await self.play_loop(None,0)
                if self.Mvc.is_paused():
                    self.Mvc.resume()
        


    async def _skip(self, sec:str):
        if self.vc:
            if sec:
                try:sec = int(sec)
                except Exception:
                    sec = sec.lower()
                    if res := re_skip.match(sec):
                        sec = int(res.group(1))
                        suf = res.group(3)
                        if suf == 'h':
                            sec = sec * 3600
                        elif suf == 'm':
                            sec = sec * 60

                    elif res := re_skip_set_h.match(sec):
                        sec = int(res.group(3))
                        sec += int(res.group(2)) * 60
                        sec += int(res.group(1)) * 3600
                        self.Mvc.TargetTimer = sec * 50
                        return

                    elif res := re_skip_set_m.match(sec):
                        sec = int(res.group(2))
                        sec += int(res.group(1)) * 60
                        self.Mvc.TargetTimer = sec * 50
                        return

                self.Mvc.TargetTimer += int(sec) * 50

            else:
                if self.Queue:
                    self.Rewind.append(self.Queue[0])
                    del self.Queue[0]
                    print(f'{self.gn} : #次の曲へ skip')
                    self.Mvc.stop()
                    await self.play_loop(None,0)





    #--------------------------------------------------
    # GUI操作
    #--------------------------------------------------
    async def _playing(self):
        if self.def_doing['_playing']: return
        self.def_doing['_playing'] = True
        try :
            if self.Mvc.is_playing():
                
                # Get Embed
                if embed := await self.generate_embed():

                    # 古いEmbedを削除
                    if late_E := self.Embed_Message:
                        try: await late_E.delete()
                        except NotFound: pass

                    # 新しいEmbed
                    Sended_Mes = await self.Latest_CH.send(embed=embed,view=CreateButton(self))
                    self.Embed_Message = Sended_Mes 
                    self.CLoop.create_task(Sended_Mes.add_reaction("🔁"))
                    if self.PL:
                        self.CLoop.create_task(Sended_Mes.add_reaction("♻"))
                        self.CLoop.create_task(Sended_Mes.add_reaction("🔀"))

                    #print(f"{guild.name} : #再生中の曲　<{g_opts[guild.id]['queue'][0][1]}>")
        except Exception: pass
        self.def_doing['_playing'] = False
        self.last_embed_update = time.perf_counter()


    async def on_reaction_add(self, Reac:Reaction, User):
        if User.bot or Reac.message.author.id != self.Info.client.user.id: return
        if em := Reac.message.embeds:
            if em[0].colour.value != 14794075: return
        self.CLoop.create_task(Reac.remove(User))
        if self.vc:

            #### Setting
            # 単曲ループ
            if Reac.emoji =='🔁':
                if not self.status['loop']:
                    self.status['loop'] = True
                else:
                    self.status['loop'] = False

            # Playlistループ
            if Reac.emoji =='♻':
                if self.status['loop_pl']:        #True => False
                    self.status['loop_pl'] = False
                else:                   #False => True
                    self.status['loop_pl'] = True

            # Random
            if Reac.emoji =='🔀':
                if self.status['random_pl']:      #True => False
                    self.status['random_pl'] = False
                else:                   #False => True
                    self.status['random_pl'] = True

            #### Message
            if self.def_doing['_playing']: return
            if (time.perf_counter() - self.last_embed_update) <= 2: return
            await self._edit_embed(Reac.message)




    async def update_embed(self):
        if self.def_doing['_playing']: return
        if (time.perf_counter() - self.last_embed_update) <= 4: return
        if not self.Latest_CH: return

        if late_E := self.Latest_CH.last_message:
            if late_E.author.id == self.Info.client.user.id:
                if late_E.embeds:
                    if late_E.embeds[0].colour.value == 14794075:
                        if await self._edit_embed(late_E):
                            return
        await self._playing()



    async def _edit_embed(self, late_E:Message):
        self.last_embed_update = time.perf_counter()
        embed = await self.generate_embed()
        # embedが無効だったら 古いEmbedを削除
        if not embed:
            try: await late_E.delete()
            except NotFound: pass
            return True

        try: await late_E.edit(embed= embed,view=self.CreateButton(self))
        except NotFound:
            # メッセージが見つからなかったら 新しく作成
            print('見つかりませんでした！')
        else:
            try:
                # Reaction 修正
                if self.PL:
                    await late_E.add_reaction('♻')
                    await late_E.add_reaction('🔀')
                else:
                    await late_E.clear_reaction('♻')
                    await late_E.clear_reaction('🔀')
            except Exception: pass
            return True



    @classmethod
    def _Calc_Time(self, Time):
        Sec = Time % 60
        Min = Time // 60 % 60
        Hour = Time // 3600
        if Sec <= 9:
            Sec = f'0{Sec}'
        if Hour == 0:
            Hour = ''
        else:
            Hour = f'{Hour}:'
            if Min <= 9:
                Min = f'0{Min}'
        
        return f'{Hour}{Min}:{Sec}'


    async def generate_embed(self):
        _SAD:SAD
        if _SAD := self.Mvc._SAD: pass
        else: return

        # emoji
        V_loop= PL_loop= Random_P= ':red_circle:'
        if self.status['loop']: V_loop = ':green_circle:'
        if self.PL:
            if self.status['loop_pl']: PL_loop = ':green_circle:'
            if self.status['random_pl']: Random_P = ':green_circle:'

        # Embed
        if _SAD.YT:
            embed=Embed(title=_SAD.Title, url=_SAD.Web_Url, colour=0xe1bd5b)
            embed.set_thumbnail(url=f'https://img.youtube.com/vi/{_SAD.VideoID}/mqdefault.jpg')
            embed.set_author(name=_SAD.CH, url=_SAD.CH_Url, icon_url=_SAD.CH_Icon)
            

            def get_progress(II):
                NTime = self.Mvc.Timer // 50
                Duration = _SAD.St_Sec / II
                Progress = ''
                for I in range(II):
                    I = I * Duration
                    if I <= NTime < (I + Duration):
                        Progress += '|'
                    else:
                        Progress += '-'
                return Progress
            Progress = get_progress(42)
            NTime = self._Calc_Time(self.Mvc.Timer // 50)
            Duration = self._Calc_Time(_SAD.St_Sec)
            embed.set_footer(text=f'{NTime} {Progress} {Duration}')
        else:
            embed=Embed(title=_SAD.Web_Url, url=_SAD.Web_Url, colour=0xe1bd5b)

        if self.PL:
            embed.add_field(name="単曲ループ", value=f'🔁 : {V_loop}', inline=True)
            embed.add_field(name="Playlistループ", value=f'♻ : {PL_loop}', inline=True)
            embed.add_field(name="シャッフル", value=f'🔀 : {Random_P}', inline=True)
        else:
            embed.add_field(name="ループ", value=f'🔁 : {V_loop}', inline=True)
        
        return embed




#---------------------------------------------------------------------------------------
#   Download
#---------------------------------------------------------------------------------------
    @classmethod
    async def _download(self, arg):

        # Download Embed

        # よそはよそ　うちはうち
        if re_URL_PL.match(arg):
            return
        if re_URL_YT.match(arg) and not re_URL_Video.match(arg):
            return

        # 君は本当に動画なのかい　どっちなんだい！
        AudioData = await SAD(arg).Check_V()
        if not AudioData: return

        if AudioData.YT:
            embed=Embed(title=AudioData.Title, url=AudioData.Web_Url, colour=0xe1bd5c)
            embed.set_thumbnail(url=f'https://img.youtube.com/vi/{AudioData.VideoID}/mqdefault.jpg')
            embed.set_author(name=AudioData.CH, url=AudioData.CH_Url, icon_url=AudioData.CH_Icon)
            
        else:
            embed=Embed(title=AudioData.Web_Url, url=AudioData.Web_Url, colour=0xe1bd5c)

        if AudioData.St_Sec:
            Duration = self._Calc_Time(AudioData.St_Sec)
            embed.add_field(name="Length", value=Duration, inline=True)

        re_video = re.compile(r'video/(.+);')
        re_audio = re.compile(r'audio/(.+);')
        re_codecs = re.compile(r'codecs="(.+)"')
        re_space = re.compile(r'\)` +?\|')
        re_space2 = re.compile(r'(( |-)\|$|^\|( |-))')
        re_space3 = re.compile(r'^\|( |-)+?\|')
            
        __list = []
        if AudioData.formats:
            for F in AudioData.formats:

                _dl = f'[`download`]({F["url"]})`'

                if F.get('width'):
                    _res = f"{F['width']}x{F['height']}"
                elif F.get('resolution'):
                    _res = F.get('resolution')
                else: 
                    _res = ''

                ext = F.get('ext','')
                acodec = F.get('acodec','')
                vcodec = F.get('vcodec','')
                abr = F.get('abr','?k')
                protocol = F.get('protocol','')

                if res := re_codecs.search(F.get('mimeType','')):
                    codec = res.group(1).split(', ')
                    _type = F.get('mimeType')
                    _type = _type.replace(f' {res.group(0)}','')

                    if res := re_video.match(_type):
                        ext = res.group(1)
                        vcodec = codec[0]
                        if len(codec) == 2:
                            acodec = codec[1]
                    
                    elif res := re_audio.match(_type):
                        ext = res.group(1)
                        _res = 'audio'
                        acodec = codec[0]
                        abr = f"{F['bitrate']//10/100}k"

                if '3gpp' in ext or 'm3u8' in protocol:
                    continue

                __list.append([_dl,ext,_res,vcodec,acodec,abr])

            headers = ['','EXT','RES','Video','Audio','ABR']
            table = tabulate.tabulate(tabular_data=__list, headers=headers, tablefmt='github')
            table = re_space.sub(')`|',table)
            table = table.split('\n')
            table[0] = re_space2.sub('',re_space3.sub('[`        `]()`|',table[0]))
            table[1] = re_space2.sub('',re_space3.sub('[`--------`]()`|',table[1]))

            _embeds = [embed]
            while table:
                __table = ''
                embed = Embed(colour=0xe1bd5c)
                while len(__table) <= 4000:
                    if __table: 
                        del table[0]
                    if len(table) == 0:
                        _table = __table
                        break
                    _table = __table
                    temp = re_space2.sub('',table[0])
                    __table += f'{temp}`\n'

                embed.description = _table
                _embeds.append(embed)
                embed = None

            return _embeds



        else:
            embed=Embed(title=AudioData.Web_Url, url=AudioData.Web_Url, colour=0xe1bd5c)
            embed_list = [embed]
            embed=Embed(title='Download', url=AudioData.St_Url, colour=0xe1bd5c)
            embed_list.append(embed)

        return embed_list
            


#---------------------------------------------------------------------------------------
#   再生 Loop
#---------------------------------------------------------------------------------------
    async def _load_next_pl(self):
        if self.def_doing['_load_next_pl']: return
        self.def_doing['_load_next_pl'] = True
        while len(self.Next_PL['PL']) <= 19:
            if self.status['random_pl']:
                for_count = 0
                new_index = 0
                while self.Next_PL['index'] == (new_index := random.randint(0,len(self.PL) - 1)):
                    for_count += 1
                    if for_count == 10: break

            else:
                new_index = self.Next_PL['index'] + 1
            if new_index >= len(self.PL):
                new_index = 0
                if self.status['loop_pl'] == False:
                    break

            url = self.PL[new_index]
            try :AudioData = await SAD(url).Pyt_V()
            except Exception as e:
                print(f'Error : Playlist Extract {e}')
                break

            AudioData.index = new_index
            self.Next_PL['PL'].append(AudioData)
            self.Next_PL['index'] = new_index
            #print(new_index)

        self.def_doing['_load_next_pl'] = False



    async def play_loop(self, played, did_time):
        # あなたは用済みよ
        if not self.vc: return

        # Queue削除
        if self.Queue:
            if self.status['loop'] == False and self.Queue[0].St_Url == played or (time.time() - did_time) <= 0.5:
                self.Rewind.append(self.Queue[0])
                del self.Queue[0]
                
        # Playlistのお客様Only
        if self.PL:
            if self.Queue == []:
                self.CLoop.create_task(self._load_next_pl())

                # 最初が読み込まれるまで wait
                while not self.Next_PL['PL']:
                    await asyncio.sleep(0.1)

                # Queue
                self.Queue.append(self.Next_PL['PL'][0])
                self.Index_PL = self.Next_PL['PL'][0].index
                del self.Next_PL['PL'][0]

                # Print
                print(f"{self.gn} : Paylist add Queue  [Now len: {str(len(self.Queue))},{str(len(self.Next_PL['PL']))}]")

        # 再生
        if self.Queue:
            AudioData = self.Queue[0]
            played_time = time.time()
            print(f"{self.gn} : Play  [Now len: {str(len(self.Queue))}]")
                
            await self.Mvc.play(AudioData,after=lambda : self.CLoop.create_task(self.play_loop(AudioData.St_Url,played_time)))


    @tasks.loop(seconds=7.0)
    async def run_loop(self):
        
        try:
            if self.PL and self.status['random_pl'] != self.last_status['random_pl']:
                while self.def_doing['_load_next_pl']:
                    self.Next_PL['PL'] = [i for i in range(25)]
                    await asyncio.sleep(1)
                self.last_status = self.status.copy()
                self.Queue = [self.Queue[0]]
                self.Next_PL['PL'] = []
                self.Next_PL['index'] = self.Index_PL
                self.CLoop.create_task(self._load_next_pl())
        
            self.CLoop.create_task(self.update_embed())
        except Exception as e:
            print(e)
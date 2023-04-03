import re
import random
import time
import tabulate
import asyncio
from typing import Optional, Literal
from discord import Embed, NotFound, TextChannel, Button, Message, SelectMenu
from discord.ext.commands import Context


from .data_analysis import int_analysis, date_difference, calc_time
from .audio_source import AnalysisUrl
from .audio_source import StreamAudioData as SAD
from .view import CreateButton
from .embeds import EmBase


re_URL_YT = re.compile(r'https://((www.|)youtube.com|youtu.be)/')
re_URL_Video = re.compile(r'https://((www.|)youtube.com/watch\?v=|(youtu.be/))(.+)')
re_URL_PL = re.compile(r'https://(www.|)youtube.com/playlist\?list=')
re_skip = re.compile(r'^((-|)\d+)([hms])$')
re_skip_set_h = re.compile(r'^(\d+)[:;,](\d+)[:;,](\d+)$')
re_skip_set_m = re.compile(r'^(\d+)[:;,](\d+)$')


re_video = re.compile(r'video/(.+);')
re_audio = re.compile(r'audio/(.+);')
re_codecs = re.compile(r'codecs="(.+)"')
re_space = re.compile(r'\)` +?\|')
re_space2 = re.compile(r'(( |-)\|$|^\|( |-))')
re_space3 = re.compile(r'^\|( |-)+?\|')




class MusicController():
    def __init__(self, _Info):
        try:
            from ..main import DataInfo
            Info:DataInfo
        except Exception: pass
        Info = _Info
        self.Info = Info
        self.MA = Info.MA
        self.Mvc = Info.MA.add_player(RNum=30 ,opus=True)
        self.guild = Info.guild
        self.gid = Info.gid
        self.gn = Info.gn
        self.vc = self.guild.voice_client
        self.Queue:list[SAD] = []
        self.Index_PL = None
        self.PL:list[SAD] = []
        self.Latest_CH:TextChannel = None
        self.status = {'loop':True,'loop_pl':True,'random_pl':True}
        self.last_status = self.status.copy()
        self.Rewind = []
        self.CLoop = Info.loop
        self.Embed_Message:Optional[Message] = None
        self.def_doing = {'playing':False,'_load_next_pl':False}
        self.last_action:float = 0.0
        

    def _update_action(self, channel= None):
        self.last_action = time.time()
        if channel:
            self.Latest_CH = channel
            

    def _reset_pl(self):
        ' Playlistのキュー をリセットする '
        if self.PL:
            self.PL = []
            del self.Queue[1:]
            self.Index_PL = None


    async def def_queue(self, ctx:Context, args):
        self._update_action(ctx.channel)
        # 一時停止していた場合再生 開始
        if args == ():
            self.Mvc.resume()
            return
        else:
            arg = ' '.join(args)


        # 君は本当に動画なのかい　どっちなんだい！
        res = await AnalysisUrl().video_check()
        if not res: return

        # playlist 再生中のお客様はお断り
        self._reset_pl()

        #Queueに登録
        self.Queue.append(res)

        # 再生されるまでループ
        if not self.Mvc.is_playing():
            await self.play_loop(None,0)
        self.Mvc.resume()





    async def play(self, ctx:Context, args):
        self._update_action(ctx.channel)
        # 一時停止していた場合再生 開始
        if args == ():
            self.Mvc.resume()
            return
        else:
            arg = ' '.join(args)


        # 君は本当に動画なのかい　どっちなんだい！
        res = await AnalysisUrl().url_check(arg)
        if not res: return

        if res.playlist:
            self.Index_PL = res.index
            self.status['random_pl'] = res.random_pl
            self.PL = res.sad

            self.status['loop'] = False
            self.Queue = []
            self.last_status = self.status.copy()


        else:
            # playlist 再生中のお客様はお断り
            self._reset_pl()

            #Queueに登録
            if self.Queue == []:
                self.Queue.append(res.sad)
            else:
                self.Queue[0] = res.sad

        # 再生されるまでループ
        await self.play_loop(None,0)
        self.Mvc.resume()



    async def skip(self, sec:str):
        if self.vc:

            self.last_action = time.time()
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
                        self.Mvc.skip_time((sec * 50) - int(self.Mvc.Timer))
                        return

                    elif res := re_skip_set_m.match(sec):
                        sec = int(res.group(2))
                        sec += int(res.group(1)) * 60
                        self.Mvc.skip_time((sec * 50) - int(self.Mvc.Timer))
                        return

                self.Mvc.skip_time(int(sec) * 50)

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
    async def playing(self):
        if self.def_doing['playing']: return
        self.def_doing['playing'] = True

        try:
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

                    #print(f"{guild.name} : #再生中の曲　<{g_opts[guild.id]['queue'][0][1]}>")
        except Exception as e:
            print(e)
        self.def_doing['playing'] = False





    async def update_embed(self):
        if self.def_doing['playing']: return
        if not self.Latest_CH: return

        if late_E := self.Latest_CH.last_message:
            if late_E.author.id == self.Info.client.user.id:
                if late_E.embeds:
                    em_color = late_E.embeds[0].colour.value
                    if em_color == EmBase.dont_replace_color().value:
                        if await self._edit_embed(self.Embed_Message):
                            return

                    if em_color == EmBase.player_color().value:
                        if await self._edit_embed(late_E):
                            return
        await self.playing()



    async def _edit_embed(self, late_E:Message):
        embed = await self.generate_embed()
        # embedが無効だったら 古いEmbedを削除
        if not embed:
            try: await late_E.delete()
            except NotFound: pass
            return True

        # viewを変更する必要があるか
        view = CreateButton(self)
        menu_change = True
        for v in late_E.components:
            v = v.children[0]
            if type(v) == SelectMenu:
                if [temp.label for temp in view.select_opt] == [temp.label for temp in v.options]:
                    menu_change = False
                    break
            if type(v) == Button:
                if v.label == "単曲ループ" and v.disabled == bool(self.PL):
                    menu_change = False
                    print('False')
                    break
                

        try:
            if menu_change:
                await late_E.edit(embed= embed,view=view)
            else:
                await late_E.edit(embed= embed)
            return True
        except NotFound:
            # メッセージが見つからなかったら 新しく作成
            print('見つかりませんでした！')



    async def generate_embed(self):
        _SAD = self.Mvc._SAD

        # Embed
        if not _SAD:
             embed=Embed(title='N/A', colour=EmBase.player_color())

        elif _SAD.YT:
            embed=Embed(title=_SAD.title, url=_SAD.web_url, colour=EmBase.player_color())
            embed.set_thumbnail(url=f'https://img.youtube.com/vi/{_SAD.video_id}/mqdefault.jpg')
            embed.set_author(name=_SAD.ch_name, url=_SAD.ch_url, icon_url=_SAD.ch_icon)
            des = []
            if _SAD.view_count:
                des.append(f'{int_analysis(_SAD.view_count)} 回再生')
            if _SAD.upload_date:
                des.append(date_difference(_SAD.upload_date))
                des.append(_SAD.upload_date)
            # if _SAD.like_count:
            #     des.append(f'\n👍{int_analysis(_SAD.like_count)}')
            if des:
                embed.description = '　'.join( des)

            # Progress Bar
            i_length = 16
            NTime = int(self.Mvc.Timer) // 50
            unit_time = _SAD.st_sec / i_length
            Progress = ''
            text_list = ['　','▏','▎','▍','▌','▋','▋','▊','▉','█']
            for I in range(i_length):
                I = I * unit_time
                if I <= NTime < (I + unit_time):
                    level = int((NTime - I) / unit_time * 9)
                    Progress += text_list[level]
                elif I <= NTime:
                    Progress += '█'
                else:
                    Progress += '　'
            NTime = calc_time(int(self.Mvc.Timer) // 50)
            Duration = calc_time(_SAD.st_sec)
            embed.set_footer(text=f'{NTime} | {Progress} | {Duration}')
        else:
            embed=Embed(title=_SAD.web_url, url=_SAD.web_url, colour=EmBase.player_color())

        

        return embed




#---------------------------------------------------------------------------------------
#   Download
#---------------------------------------------------------------------------------------
    @classmethod
    async def download(self, arg):

        # Download Embed

        # よそはよそ　うちはうち
        if re_URL_PL.match(arg):
            return
        if re_URL_YT.match(arg) and not re_URL_Video.match(arg):
            return

        # 君は本当に動画なのかい　どっちなんだい！
        AudioData = await AnalysisUrl().video_check(arg)
        if not AudioData: return

        AudioData = AudioData.sad
        if AudioData.YT:
            embed=Embed(title=AudioData.title, url=AudioData.web_url, colour=EmBase.main_color())
            embed.set_thumbnail(url=f'https://img.youtube.com/vi/{AudioData.video_id}/mqdefault.jpg')
            embed.set_author(name=AudioData.ch_name, url=AudioData.ch_url, icon_url=AudioData.ch_icon)
            
        else:
            embed=Embed(title=AudioData.web_url, url=AudioData.web_url, colour=EmBase.main_color())

        if AudioData.st_sec:
            Duration = calc_time(AudioData.st_sec)
            embed.add_field(name="Length", value=Duration, inline=True)

            
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
                embed = Embed(colour=EmBase.main_color())
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
            embed=Embed(title=AudioData.web_url, url=AudioData.web_url, colour=EmBase.main_color())
            embed_list = [embed]
            embed=Embed(title='Download', url=AudioData.st_url, colour=EmBase.main_color())
            embed_list.append(embed)

        return embed_list
            


#---------------------------------------------------------------------------------------
#   再生 Loop
#---------------------------------------------------------------------------------------
    async def _load_next_pl(self):
        '''
        create_taskによる非同期投げっぱなし動作
        PlayList有効中に動作
        load中に PLが無効になる場合も考え 非同期処理が入るたびに PLがTrueか確認しよう！
        '''
        if self.def_doing['_load_next_pl']: return
        if not self.PL: return
        self.def_doing['_load_next_pl'] = True
        while len(self.Queue) <= 19 and self.def_doing['_load_next_pl']:
            if not self.PL: break
            
            if self.Queue:
                last_index = self.Queue[-1].index
            else:
                last_index = self.Index_PL
            
            if self.status['random_pl']:
                for_count = 0
                while last_index == (new_index := random.randint(0,len(self.PL) - 1)):
                    for_count += 1
                    if for_count == 10:
                        new_index = last_index
                        break

            else:
                new_index = last_index + 1
            if new_index >= len(self.PL):
                new_index = 0
                if self.status['loop_pl'] == False:
                    break

            sad = self.PL[new_index]
            try :await sad.Pyt_V()
            except Exception as e:
                print(f'Error : Playlist Extract {e}')
                break
            
            if not self.PL: break
            sad.index = new_index
            self.Queue.append(sad)
            #print(new_index)

        self.def_doing['_load_next_pl'] = False



    async def play_loop(self, played, did_time):
        # あなたは用済みよ
        if not self.vc: return

        # Queue削除
        if self.Queue:
            if self.status['loop'] == False and self.Queue[0].st_url == played or (time.time() - did_time) <= 0.5:
                self.Rewind.append(self.Queue[0])
                del self.Queue[0]
                
        # Playlistのお客様Only
        if self.PL:
            self.CLoop.create_task(self._load_next_pl())
            if self.Queue == []:

                # 最初が読み込まれるまで wait
                while not self.Queue:
                    await asyncio.sleep(0.5)
                
                if not self.PL: return

                # Queue
                self.Index_PL = self.Queue[0].index

                # Print
                #print(f"{self.gn} : Paylist add Queue  [Now len: {str(len(self.Queue))}]")

        # 再生
        if self.Queue:
            AudioData = self.Queue[0]
            played_time = time.time()
            print(f"{self.gn} : Play  [Now len: {str(len(self.Queue))}]")
                
            await self.Mvc.play(AudioData,after=lambda : self.CLoop.create_task(self.play_loop(AudioData.st_url,played_time)))


    async def _loop_5(self):
        
        try:
            # PlayList再生時に 次の動画を取得する
            if self.PL and self.status['random_pl'] != self.last_status['random_pl']:
                if self.def_doing['_load_next_pl']:
                    self.def_doing['_load_next_pl'] = None
                    while self.def_doing['_load_next_pl'] == None:
                        await asyncio.sleep(1)
                self.last_status = self.status.copy()
                del self.Queue[1:]
                self.CLoop.create_task(self._load_next_pl())

            # Embed
            now = time.time()
            delay = now - self.last_action
            if delay < 30:
                await self.update_embed()
            elif delay < 300:
                if 0 <= (now % 10) < 5:
                    await self.update_embed()
            else:
                if 0 <= (now % 20) < 5:
                    await self.update_embed()

        except Exception as e:
            print(e)
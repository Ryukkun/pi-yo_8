import re
import random
import time
import tabulate

from discord import ui, Embed, ButtonStyle, NotFound

from audio_source import StreamAudioData as SAD


re_URL_YT = re.compile(r'https://((www.|)youtube.com|youtu.be)/')
re_URL_Video = re.compile(r'https://((www.|)youtube.com/watch\?v=|(youtu.be/))(.+)')
re_URL_PL = re.compile(r'https://(www.|)youtube.com/playlist\?list=')



class MusicController():
    def __init__(self, Info):
        self.Info = Info
        self.MA = Info.MA
        self.Mvc = Info.MA.add_player('Music' ,RNum=600 ,opus=True ,def_getbyte=self._update_embed)
        self.guild = Info.guild
        self.gid = Info.gid
        self.gn = Info.gn
        self.vc = self.guild.voice_client
        self.Queue = []
        self.Index_PL = None
        self.PL = None
        self.Latest_CH = None
        self.Loop = True
        self.Loop_PL = True
        self.Random_PL = True
        self.Rewind = []
        self.CLoop = Info.loop
        self.Embed_Message = None
        self.sending_embed = False

    async def _play(self, ctx, args, Q):
        # 一時停止していた場合再生 開始
        if args == ():
            if self.Mvc.is_paused():
                self.Mvc.resume()
            return
        else:
            arg = ' '.join(args)

        # よそはよそ　うちはうち
        if re_URL_PL.match(arg):
            await self._playlist(ctx,arg)
            return
        if re_URL_YT.match(arg) and not re_URL_Video.match(arg):
            return

        # 君は本当に動画なのかい　どっちなんだい！
        AudioData = await SAD(arg).Check_V()
        if not AudioData: return

        # playlist 再生中のお客様はお断り
        if self.PL:
            self.PL = None
            self.Index_PL = None

        self.Latest_CH = ctx.channel

        #Queueに登録
        if Q:
            self.Queue.append(AudioData)
        else:
            if self.Queue == []:
                self.Queue.append(AudioData)
            else:
                self.Queue[0] = AudioData

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




    async def _playlist(self, ctx ,args):
        # 一時停止していた場合再生 開始
        if args == ():
            if self.Mvc.is_paused():
                self.Mvc.resume()
            return
        elif type(args) == str:
            arg = args
        else:
            arg = ' '.join(args)

        # 君はほんとにplaylistなのかい　どっちなんだい！
        if res := await SAD(arg).Check_P():
            self.Index_PL = res[0]
            self.Random_PL = res[1]
            self.PL = res[2]
        else:
            return
        self.Latest_CH = ctx.channel
        self.Loop = False
        #self.Index_PL -= 1
        self.Queue = []

        # 再生
        await self.play_loop(None,0)
        if self.Mvc.is_paused():
            self.Mvc.resume()


    async def _skip(self, sec):
        if self.vc:
            if sec:
                self.Mvc.TargetTimer += int(sec) * 50
            else:
                if self.Queue:
                    self.Rewind.append(self.Queue[0])
                    del self.Queue[0]
                    print(f'{self.gn} : #次の曲へ skip')
                    await self.play_loop(None,0)




    #--------------------------------------------------
    # GUI操作
    #--------------------------------------------------
    # Button
    class CreateButton(ui.View):
        def __init__(self, Parent):
            super().__init__(timeout=None)
            self.Parent = Parent

        @ui.button(label="<")
        async def def_button0(self, interaction, button):
            Parent = self.Parent
            Parent.CLoop.create_task(interaction.response.defer())


            if not Parent.Rewind: return
            AudioData = Parent.Rewind[-1]
            if len(Parent.Queue) >= 1:
                del Parent.Queue[0]
            Parent.Queue.insert(0,AudioData)
            del Parent.Rewind[-1]
            if Parent.PL:
                index = None
                for i, temp in enumerate(Parent.PL):
                    if AudioData.VideoID in temp:
                        index = i
                        break
                if index:
                    Parent.Index_PL = index

            await Parent.play_loop(None,0)
            if Parent.Mvc.is_paused():
                Parent.Mvc.resume()

        @ui.button(label="10↩︎")
        async def def_button1(self, interaction, button):
            Parent = self.Parent
            Parent.CLoop.create_task(interaction.response.defer())
            Parent.Mvc.TargetTimer -= 10*50

        @ui.button(label="⏯",style=ButtonStyle.blurple)
        async def def_button2(self, interaction, button):
            Parent = self.Parent
            Parent.CLoop.create_task(interaction.response.defer())

            if Parent.Mvc.is_paused():
                print(f'{Parent.gn} : #resume')
                Parent.Mvc.resume()
            elif Parent.Mvc.is_playing():
                print(f'{Parent.gn} : #stop')
                Parent.Mvc.pause()
                await Parent.Update_Embed()

        @ui.button(label="↪︎10")
        async def def_button3(self, interaction, button):
            Parent = self.Parent
            Parent.CLoop.create_task(interaction.response.defer())
            Parent.Mvc.TargetTimer += 10*50

        @ui.button(label=">")
        async def def_button4(self, interaction, button):
            Parent = self.Parent
            Parent.CLoop.create_task(interaction.response.defer())
            await Parent._skip(None)




    async def _playing(self):
        if self.sending_embed: return
        self.sending_embed = True
        if self.Mvc.is_playing():
            
            # Get Embed
            if embed := await self.Edit_Embed():

                # 古いEmbedを削除
                if late_E := self.Embed_Message:
                    try: await late_E.delete()
                    except NotFound: pass

                # 新しいEmbed
                Sended_Mes = await self.Latest_CH.send(embed=embed,view=self.CreateButton(self))
                self.Embed_Message = Sended_Mes 
                self.CLoop.create_task(Sended_Mes.add_reaction("🔁"))
                if self.PL:
                    self.CLoop.create_task(Sended_Mes.add_reaction("♻"))
                    self.CLoop.create_task(Sended_Mes.add_reaction("🔀"))

                #print(f"{guild.name} : #再生中の曲　<{g_opts[guild.id]['queue'][0][1]}>")
        self.sending_embed = False


    async def on_reaction_add(self, Reac, User):
        if User.bot or Reac.message.author.id != self.Info.client.user.id: return
        self.CLoop.create_task(Reac.remove(User))
        if self.vc:

            #### Setting
            # 単曲ループ
            if Reac.emoji =='🔁':
                if not self.Loop:
                    self.Loop = True
                else:
                    self.Loop = False

            # Playlistループ
            if Reac.emoji =='♻':
                if self.Loop_PL:        #True => False
                    self.Loop_PL = False
                else:                   #False => True
                    self.Loop_PL = True

            # Random
            if Reac.emoji =='🔀':
                if self.Random_PL:      #True => False
                    self.Random_PL = False
                else:                   #False => True
                    self.Random_PL = True


            #### Message
            # Get Embed
            embed = await self.Edit_Embed()
            if not embed: return
            # Edit
            await Reac.message.edit(embed=embed)


    def _update_embed(self):
        # 秒数更新のため
        if 0 <= self.Mvc.Timer < (50*60):
            if (self.Mvc.Timer % (50*5)) == 1:
                self.CLoop.create_task(self.Update_Embed())
        elif (50*60) <= self.Mvc.Timer < (50*1800):
            if (self.Mvc.Timer % (50*10)) == 1:
                self.CLoop.create_task(self.Update_Embed())
        elif (50*1800) <= self.Mvc.Timer:
            if (self.Mvc.Timer % (50*30)) == 1:
                self.CLoop.create_task(self.Update_Embed())



    async def Update_Embed(self):
        if late_E := self.Latest_CH.last_message:
            if late_E.author.id == self.Info.client.user.id:
                embed = await self.Edit_Embed()
                # embedが無効だったら 古いEmbedを削除
                if not embed:
                    try: await late_E.delete()
                    except NotFound: pass
                    return

                try: await late_E.edit(embed= embed)
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
                    return
        
        await self._playing()

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


    async def Edit_Embed(self):
        
        if _SAD := self.Mvc._SAD: pass
        else: return

        # emoji
        V_loop= PL_loop= Random_P= ':red_circle:'
        if self.Loop: V_loop = ':green_circle:'
        if self.PL:
            if self.Loop_PL: PL_loop = ':green_circle:'
            if self.Random_PL: Random_P = ':green_circle:'

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
            embed=Embed(title=AudioData.Title, url=AudioData.Web_Url, colour=0xe1bd5b)
            embed.set_thumbnail(url=f'https://img.youtube.com/vi/{AudioData.VideoID}/mqdefault.jpg')
            embed.set_author(name=AudioData.CH, url=AudioData.CH_Url, icon_url=AudioData.CH_Icon)
            
        else:
            embed=Embed(title=AudioData.Web_Url, url=AudioData.Web_Url, colour=0xe1bd5b)

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

                _dl = f'[download]({F["url"]})`'

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
            table[0] = '`'+re_space2.sub('',re_space3.sub('        |',table[0]))
            table[1] = '`'+re_space2.sub('',re_space3.sub('--------|',table[1]))

            _embeds = [embed]
            while table:
                __table = ''
                embed = Embed(colour=0xe1bd5b)
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
            embed=Embed(title=AudioData.Web_Url, url=AudioData.Web_Url, colour=0xe1bd5b)
            embed_list = [embed]
            embed=Embed(title='Download', url=AudioData.St_Url, colour=0xe1bd5b)
            embed_list.append(embed)

        return embed_list
            


#---------------------------------------------------------------------------------------
#   再生 Loop
#---------------------------------------------------------------------------------------
    async def play_loop(self, played, did_time):
        # あなたは用済みよ
        if not self.vc: return

        # Queue削除
        if self.Queue:
            if self.Loop != 1 and self.Queue[0].St_Url == played or (time.time() - did_time) <= 0.5:
                self.Rewind.append(self.Queue[0])
                del self.Queue[0]

        # Playlistのお客様Only
        if self.PL and self.Queue == []:
            if self.Random_PL:
                for_count = 0
                while self.Index_PL == (new_index := random.randint(0,len(self.PL) - 1)):
                    for_count += 1
                    if for_count == 10: break
                self.Index_PL = new_index
            else:
                self.Index_PL += 1
            if self.Index_PL >= len(self.PL):
                self.Index_PL = 0
                if self.Loop_PL == 0:
                    del self.PL
                    del self.Index_PL
                    return

            extract_url = self.PL[self.Index_PL]
            try :AudioData = await SAD(extract_url).Pyt_V()
            except Exception as e:
                print(f'Error : Playlist Extract {e}')
                return
            # Queue
            self.Queue.append(AudioData)
            # Print
            print(f"{self.gn} : Paylist add Queue  [Now len: {str(len(self.Queue))}]")

        # 再生
        if self.Queue != []:
            AudioData = self.Queue[0]
            played_time = time.time()
            print(f"{self.gn} : Play  [Now len: {str(len(self.Queue))}]")
                
            await self.Mvc.play(AudioData,after=lambda : self.CLoop.create_task(self.play_loop(AudioData.St_Url,played_time)))

import discord
from discord.ext import commands, tasks
import asyncio
import os
import re
import time
import configparser
from pytube.innertube import InnerTube
import random
import aiohttp
from bs4 import BeautifulSoup
import audio as SAudio
from audio import StreamAudioData as SAD
from concurrent.futures import ThreadPoolExecutor



####  Config
if not os.path.isfile('config.ini'):
    config = configparser.ConfigParser()
    config['DEFAULT'] = {
        'Prefix':'.',
        'Token':''
    }
    with open('config.ini', 'w') as f:
        config.write(f)

config = configparser.ConfigParser()
config.read('config.ini')




####  起動準備 And 初期設定
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
client = commands.Bot(command_prefix=config['DEFAULT']['Prefix'],intents=intents)
voice_client = None
g_opts = {}
Play_Loop_Embed = []

re_false = re.compile(r'(f|0|ふぁlせ)')
re_true = re.compile(r'(t|1|ｔるえ)')
re_random = re.compile(r'(r|2|らんどm)')
re_URL_YT = re.compile(r'https://((www.|)youtube.com|youtu.be)/')
re_URL_Video = re.compile(r'https://((www.|)youtube.com/watch\?v=|(youtu.be/))(.+)')
re_URL_PL_Video = re.compile(r'https://(www.|)youtube.com/watch\?v=(.+)&list=(.+)')
re_str_PL = re.compile(r'p')
re_URL_PL = re.compile(r'https://(www.|)youtube.com/playlist\?list=')
re_URL = re.compile(r'http')




####  基本的コマンド
@client.event
async def on_ready():
    print('Logged in')
    print(client.user.name)
    print(client.user.id)
    print('----------------')
    


@client.command()
async def join(ctx):
    if vc := ctx.author.voice:
        gid = ctx.guild.id
        print(f'{ctx.guild.name} : #join')
        await vc.channel.connect()
        g_opts[gid] = {}
        g_opts[gid]['loop'] = 1
        g_opts[gid]['loop_playlist'] = 1
        g_opts[gid]['random_playlist'] = 1
        g_opts[gid]['queue'] = []
        g_opts[gid]['may_i_edit'] = {}
        g_opts[gid]['rewind'] = []
        g_opts[gid]['Ma'] = MultiAudio(ctx.guild)
    

@client.command()
async def bye(ctx):
    gid = ctx.guild.id
    vc = ctx.voice_client
    if vc:
        print(f'{ctx.guild.name} : #切断')

        # 古いEmbedを削除
        if late_E := g_opts[gid].get('Embed_Message'):
            await late_E.delete()
        g_opts[gid] = {}
        await vc.disconnect()


@client.command()
async def stop(ctx):
    Mvc = g_opts[ctx.guild.id]['Ma'].Music
    if Mvc.is_playing():
        print(f'{ctx.guild.name} : #stop')
        Mvc.pause()
  


#--------------------------------------------------
# GUI操作
#--------------------------------------------------
# Button
class CreateButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="<",)
    async def def_button0(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        guild = interaction.guild
        gid = interaction.guild_id
        Mvc = g_opts[gid]['Ma'].Music
        
        if not g_opts[gid]['rewind']: return
        AudioData = g_opts[gid]['rewind'][-1]
        g_opts[gid]['queue'].insert(0,AudioData)
        del g_opts[gid]['rewind'][-1]

        await play_loop(guild,None,0)
        if Mvc.is_paused():
            Mvc.resume()


    @discord.ui.button(label="⏯",style=discord.ButtonStyle.blurple)
    async def def_button1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        guild = interaction.guild
        Mvc = g_opts[guild.id]['Ma'].Music
        if Mvc.is_paused():
            print(f'{guild.name} : #resume')
            Mvc.resume()
        elif Mvc.is_playing():
            print(f'{guild.name} : #stop')
            Mvc.pause()

    @discord.ui.button(label=">")
    async def def_button2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await def_skip(interaction.message)




@client.command()
async def playing(ctx,*args):
    if ctx:
        guild = ctx.guild
        gid = guild.id
        Mvc = g_opts[gid]['Ma'].Music
        channel = ctx.channel
        g_opts[gid]['latest_ch'] = channel
    else:
        guild = args[0]
        gid = guild.id
        Mvc = g_opts[guild.id]['Ma'].Music
        channel = args[1]

    if not Mvc.is_playing(): return
    
    # Get Embed
    embed = await Edit_Embed(gid)
    if not embed: return

    # 古いEmbedを削除
    if late_E := g_opts[gid].get('Embed_Message'):
        try: await late_E.delete()
        except discord.NotFound: pass



    # 新しいEmbed
    Sended_Mes = await channel.send(embed=embed,view=CreateButton())
    g_opts[gid]['Embed_Message'] = Sended_Mes 
    await Sended_Mes.add_reaction("🔁")
    if g_opts[gid].get('playlist'):
        await Sended_Mes.add_reaction("♻")
        await Sended_Mes.add_reaction("🔀")

    #print(f"{guild.name} : #再生中の曲　<{g_opts[guild.id]['queue'][0][1]}>")


@client.event
async def on_reaction_add(Reac,User):
    guild = Reac.message.guild
    gid = guild.id
    Mvc = g_opts[gid]['Ma'].Music
    if User.bot or Reac.message.author.id != client.user.id: return
    asyncio.create_task(Reac.remove(User))
    if Mvc.is_playing():

        #### Setting
        # 単曲ループ
        if Reac.emoji =='🔁':
            if g_opts[gid]['loop'] == 0:
                g_opts[gid]['loop'] = 1
            else:
                g_opts[gid]['loop'] = 0

        # Playlistループ
        if Reac.emoji =='♻':
            if g_opts[gid]['loop_playlist'] == 0:     #Flse => True
                g_opts[gid]['loop_playlist'] = 1
            elif g_opts[gid]['loop_playlist'] == 1:     #True => False
                g_opts[gid]['loop_playlist'] = 0

        # Random
        if Reac.emoji =='🔀':
            if g_opts[gid]['random_playlist'] == 0:     #Flse => Random
                g_opts[gid]['random_playlist'] = 1
            elif g_opts[gid]['random_playlist'] == 1:     #True => Random
                g_opts[gid]['random_playlist'] = 0


        #### Message
        # Get Embed
        embed = await Edit_Embed(gid)
        if not embed: return
        # Edit
        await Reac.message.edit(embed=embed)




async def Edit_Embed(gid):
    try:
        url = g_opts[gid]['queue'][0].Web_Url
    except IndexError:
        return None


    # emoji
    V_loop= PL_loop= Random_P= ':red_circle:'
    if g_opts[gid]['loop'] == 1: V_loop = ':green_circle:'
    if g_opts[gid].get('playlist'):
        if g_opts[gid]['loop_playlist'] >= 1: PL_loop = ':green_circle:'
        if g_opts[gid]['random_playlist'] >= 1: Random_P = ':green_circle:'

    # Embed
    if re_URL_YT.match(url):
        Vid = re_URL_Video.match(url).group(4)
        loop = asyncio.get_event_loop()

        # Get Youtube Data
        Vdic = await loop.run_in_executor(None,InnerTube().player,Vid)
        Title = Vdic["videoDetails"]["title"]
        CH = Vdic["videoDetails"]["author"]
        CH_Url = f'https://www.youtube.com/channel/{Vdic["videoDetails"]["channelId"]}'

        async with aiohttp.ClientSession() as session:
            async with session.get(CH_Url) as resp:
                text = await resp.read()
        CH_Icon = BeautifulSoup(text.decode('utf-8'), 'html.parser')
        CH_Icon = CH_Icon.find('link',rel="image_src").get('href')
        

        embed=discord.Embed(title=Title, url=url, colour=0xe1bd5b)
        embed.set_thumbnail(url=f'https://img.youtube.com/vi/{Vid}/mqdefault.jpg')
        embed.set_author(name=CH, url=CH_Url, icon_url=CH_Icon)
    else:
        embed=discord.Embed(title=url, url=url, colour=0xe1bd5b)

    if g_opts[gid].get('playlist'):
        embed.add_field(name="単曲ループ", value=f'🔁 : {V_loop}', inline=True)
        embed.add_field(name="Playlistループ", value=f'♻ : {PL_loop}', inline=True)
        embed.add_field(name="シャッフル", value=f'🔀 : {Random_P}', inline=True)
    else:
        embed.add_field(name="ループ", value=f'🔁 : {V_loop}', inline=True)
    
    return embed




#---------------------------------------------------------------------------------------------------
#   Skip
#---------------------------------------------------------------------------------------------------

@client.command()
async def skip(ctx):
    await def_skip(ctx)

@client.command()
async def s(ctx):
    await def_skip(ctx)

async def def_skip(ctx):
    guild = ctx.guild
    vc = guild.voice_client
    gid = guild.id
    if vc:
        if g_opts[gid]['queue'] != []:
            g_opts[gid]['rewind'].append(g_opts[gid]['queue'][0])
            del g_opts[gid]['queue'][0]
            print(f'{guild.name} : #次の曲へ skip')
            await play_loop(guild,None,0)
        




##############################################################################
# Play & Queue
##############################################################################

@client.command()
async def queue(ctx,*args):
    await def_play(ctx,args,True)

@client.command()
async def q(ctx,*args):
    await def_play(ctx,args,True)

@client.command()
async def play(ctx,*args):
    await def_play(ctx,args,False)

@client.command()
async def p(ctx,*args):
    await def_play(ctx,args,False)

async def def_play(ctx,args,Q):
    if not await join_check(ctx): return
    guild = ctx.guild
    vc = guild.voice_client
    Mvc = g_opts[gid]['Ma'].Music
    gid = guild.id

    # 一時停止していた場合再生 開始
    if args == ():
        if Mvc.is_paused():
            Mvc.resume()
        return
    else:
        arg = ' '.join(args)

    # よそはよそ　うちはうち
    if re_URL_PL.match(arg):
        await def_playlist(ctx,arg)
        return
    if re_URL_YT.match(arg) and not re_URL_Video.match(arg):
        return

    # Stream URL
    ### 動画+playlist
    if re_result := re_URL_PL_Video.match(arg):
        arg = f'https://www.youtube.com/watch?v={re_result.group(2)}'
    if not re_URL.match(arg):
        AudioData = await SAD(arg).Pyt_V_Search()

    ### youtube 動画オンリー
    elif re_URL_YT.match(arg):
        try: AudioData = await SAD(arg).Pyt_V()
        except Exception as e:
            print(f"Error : Audio only 失敗 {e}")
            return

    ### それ以外のサイト yt-dlp を使用
    else:
        try: AudioData = await SAD(arg).Ytdlp_V()
        except Exception as e:
            print(f"Error : Audio + Video 失敗 {e}")
            return

    
        # URL確認
    if not re_URL.match(AudioData.St_Url): return

        # playlist 再生中のお客様はお断り
    if g_opts[gid].get('playlist'):
        del g_opts[gid]['playlist']
        del g_opts[gid]['playlist_index']

    g_opts[gid]['latest_ch'] = ctx.channel

        #Queueに登録
    if Q:
        g_opts[gid]['queue'].append(AudioData)
    else:
        if g_opts[gid]['queue'] == []:
            g_opts[gid]['queue'].append(AudioData)
        else:
            g_opts[gid]['queue'][0] = AudioData


        # 再生されるまでループ
    if Q:
        if not Mvc.is_playing():
            await play_loop(guild,None,0)
        if Mvc.is_paused():
            Mvc.resume()
    else:
        await play_loop(guild,None,0)
        if Mvc.is_paused():
            Mvc.resume()





############################################################################################
#   Playlist
############################################################################################

@client.command()
async def playlist(ctx,*args):
    await def_playlist(ctx,args)

@client.command()
async def pl(ctx,*args):
    await def_playlist(ctx,args)

async def def_playlist(ctx,args):
    if not await join_check(ctx):
        return
    guild = ctx.guild
    vc = guild.voice_client
    gid = guild.id
    Mvc = g_opts[gid]['Ma'].Music

    # 一時停止していた場合再生 開始
    if args == ():
        if Mvc.is_paused():
            Mvc.resume()
        return
    elif type(args) == str:
        arg = args
    else:
        arg = ' '.join(args)




    # 君はほんとにplaylistなのかい　どっちなんだい！
    yt_first = None
    watch_url = None
    loud_vol = None
    

    ### PlayList 本体のURL ------------------------------------------------------------------------#
    if re_URL_PL.match(arg): 
        g_opts[gid]['playlist_index'] = 0
        Pl = await SAudio.Pyt_P(arg)
        if Pl:
            print(f"{guild.name} : Loaded all video in the playlist  [playlist_count: {str(len(Pl))}]")
            g_opts[gid]['playlist'] = Pl

    ### PlayList と 動画が一緒についてきた場合 --------------------------------------------------------------#
    ###
    ### ここは特別 elif の範囲だけで処理終わらせる
    ###
    elif result_re := re_URL_PL_Video.match(arg):
        watch_url = result_re.group(2)
        arg = f'https://www.youtube.com/playlist?list={result_re.group(3)}'
        extract_url = f'https://www.youtube.com/watch?v={watch_url}'

        try: AudioData = await SAD(extract_url).Pyt_V()
        except Exception as e:
            print(f'Error : Playlist First-Music {e}')
        else:
            g_opts[gid]['queue'] = [AudioData]
            g_opts[gid]['playlist'] = 'Temp'
            g_opts[gid]['playlist_index'] = None
            g_opts[gid]['loop'] = 0
            g_opts[gid]['latest_ch'] = ctx.channel
            await play_loop(guild,None,0)
            if Mvc.is_paused():
                Mvc.resume()

        # Load Video in the Playlist 
        Pl = await SAudio.Pyt_P(arg)
        if Pl:
            print(f"{guild.name} : Loaded all video in the playlist  [playlist_count: {str(len(Pl))}]")
            g_opts[gid]['playlist'] = Pl

        # Playlist Index 特定
        for i, temp in enumerate(g_opts[gid]['playlist']):
            if watch_url in temp:
                g_opts[gid]['playlist_index'] = i
                break
        if not g_opts[gid]['playlist_index']:
            g_opts[gid]['playlist_index'] = 0
        
        return
        

    ### URLじゃなかった場合 -----------------------------------------------------------------------#
    elif not re_URL.match(arg):
        g_opts[gid]['playlist_index'] = 0
        g_opts[gid]['playlist'] = await SAudio.Pyt_P_Search(arg)
        g_opts[gid]['random_playlist'] = 0

    ### その他 例外------------------------------------------------------------------------#
    else: 
        print("playlistじゃないみたい")
        return

    g_opts[gid]['latest_ch'] = ctx.channel
    g_opts[gid]['loop'] = 0

    g_opts[gid]['playlist_index'] -= 1
    g_opts[gid]['queue'] = []

    # 再生
    await play_loop(guild,None,0)
    if Mvc.is_paused():
        Mvc.resume()



# playlistダウンロード
async def ydl_playlist(guild):
    gid = guild.id
    if g_opts[gid]['playlist_index'] >= len(g_opts[gid]['playlist']):
        g_opts[gid]['playlist_index'] = 0
        if g_opts[gid]['loop_playlist'] == 0:
            del g_opts[gid]['playlist']
            del g_opts[gid]['playlist_index']
            return

    extract_url = g_opts[gid]['playlist'][g_opts[gid]['playlist_index']]
    try :AudioData = await SAD(extract_url).Pyt_V()
    except Exception as e:
        print(f'Error : Playlist Extract {e}')
        return

    # Queue
    g_opts[gid]['queue'].append(AudioData)

    # Print
    print(f"{guild.name} : Paylist add Queue  [Now len: {str(len(g_opts[gid]['queue']))}]")




#---------------------------------------------------------------------------------------
#   再生 Loop
#---------------------------------------------------------------------------------------
async def play_loop(guild,played,did_time):
    gid = guild.id


    # あなたは用済みよ
    if not guild.voice_client: return

    # Queue削除
    if g_opts[gid]['queue']:
        if g_opts[gid]['loop'] != 1 and g_opts[gid]['queue'][0].St_Url == played or (time.time() - did_time) <= 0.5:
            g_opts[gid]['rewind'].append(g_opts[gid]['queue'][0])
            del g_opts[gid]['queue'][0]

    # Playlistのお客様Only
    if g_opts[gid].get('playlist') and g_opts[gid]['queue'] == []:
        if g_opts[gid]['random_playlist'] == 1:
            for_count = 0
            while g_opts[gid]['playlist_index'] == (new_index := random.randint(0,len(g_opts[gid]['playlist']) - 1)):
                for_count += 1
                if for_count == 10: break
            g_opts[gid]['playlist_index'] = new_index
        else:
            g_opts[gid]['playlist_index'] += 1
        await ydl_playlist(guild)

    # 再生
    if g_opts[gid]['queue'] != []:
        AudioData = g_opts[gid]['queue'][0]
        played_time = time.time()
        print(f"{guild.name} : Play  [Now len: {str(len(g_opts[gid]['queue']))}]")
            
        await g_opts[guild.id]['Ma'].Music.play(AudioData,lambda : client.loop.create_task(play_loop(guild,AudioData.St_Url,played_time)))
        Channel = g_opts[guild.id]['latest_ch']
        if late_E := g_opts[gid]['may_i_edit'].get(Channel.id):
            try: 
                await late_E.edit(embed= await Edit_Embed(gid))
            except discord.NotFound:
                await playing(None,guild,Channel)

        else:
            await playing(None,guild,Channel)


class MultiAudio():
    def __init__(self,guild) -> None:
        self.guild = guild
        self.gid = guild.id
        self.vc = guild.voice_client
        self.Music = self._Music(self)
        self.Voice = self._Voice()


    class _Voice():
        def play(self,VAudioSource):
            self.VAudioSource = VAudioSource

    class _Music():
        def __init__(self,parent):
            self.AudioSource = None
            self.Pausing = False
            self.Parent = parent
            self.Time = 0
            self.After = None

        async def play(self,AudioSource,after):
            self.AudioSource = await AudioSource.AudioSource()
            self.Timer = 0
            self.Pausing = False
            self.Parent.After = after
            if not self.Parent.Loop.is_running():
                self.Parent.Loop.start()

        def stop(self):
            self.MAudioSource = None

        def resume(self):
            self.Pausing = False

        def pause(self):
            self.Pausing = True

        def is_playing(self):
            if self.AudioSource:
                return True
            return False

        def is_paused(self):
            return self.Pausing
        
        def read_bytes(self):
            if self.AudioSource and self.Pausing == False:
                if Bytes := self.AudioSource.read():
                    self.Timer += 1
                    return Bytes
                else:
                    self.AudioSource = None
                    self.Parent.Loop.stop()
                    return 'Fin'



    @tasks.loop(seconds=0.02)
    async def Loop(self):
        self.MBytes = self.Music.read_bytes()
        if self.MBytes == 'Fin':
            self.After()
        elif self.MBytes:
            self.vc.send_audio_packet(self.MBytes,encode=False)

            

# 最新の投稿か確認
@client.event
async def on_message(message):
    """
    チャンネルの履歴が見れないため チャンネル毎に 投稿があったか記録していく
    user.id で判別してるため、playing以外の投稿があったらバグる
    """
    if message.guild.voice_client:
        if message.author.id == client.user.id:
            g_opts[message.guild.id]['may_i_edit'][message.channel.id] = message
        else:
            g_opts[message.guild.id]['may_i_edit'][message.channel.id] = None
    
    await client.process_commands(message)




#--------------------------------------------------------------------------------------------
#   居たら楽な関数達
#--------------------------------------------------------------------------------------------
async def join_check(ctx):

    guild = ctx.guild
    vc = guild.voice_client

    print(f'\n#message.server  : {guild.name} ({ctx.channel.name})')
    print( ctx.author.name +" (",ctx.author.display_name,') : '+ ctx.message.content)
    
        # Joinしていない場合
    if not vc:
        await join(ctx)
        # Joinしてるよね！！
    return guild.voice_client
    



client.run(config['DEFAULT']['Token'])
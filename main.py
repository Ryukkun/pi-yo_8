import discord
from discord.ext import commands
import asyncio
import os
import ffmpeg
import re
import time
import configparser
import shutil
from yt_dlp import YoutubeDL
import pytube
from pytube.innertube import InnerTube
from pytube.helpers import DeferredGeneratorList
import random
import aiohttp
from bs4 import BeautifulSoup



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
    await Send_Embed()


@client.command()
async def join(ctx):
    if ctx.author.voice:
        gid = ctx.guild.id
        print(f'{ctx.guild.name} : #join')
        await ctx.author.voice.channel.connect()
        g_opts[gid] = {}
        g_opts[gid]['loop'] = 1
        g_opts[gid]['loop_playlist'] = 1
        g_opts[gid]['random_playlist'] = 1
        g_opts[gid]['queue'] = []
        g_opts[gid]['may_i_edit'] = {}
    

@client.command()
async def bye(ctx):
    gid = ctx.guild.id
    if ctx.voice_client:
        print(f'{ctx.guild.name} : #切断')

        # 古いEmbedを削除
        if late_E := g_opts[gid].get('Embed_Message'):
            await late_E.delete()
        g_opts[gid] = {}
        await ctx.voice_client.disconnect()


@client.command()
async def stop(ctx):
    vc = ctx.voice_client
    if vc.is_playing():
        print(f'{ctx.guild.name} : #stop')
        vc.pause()




#--------------------------------------------------
# GUI操作
#--------------------------------------------------

@client.command()
async def playing(ctx):
    guild = ctx.guild
    vc = guild.voice_client
    gid = guild.id
    if not vc.is_playing() and not vc.is_paused(): return
    
    # Get Embed
    embed = await Edit_Embed(gid)
    if not embed: return

    # 古いEmbedを削除
    if late_E := g_opts[gid].get('Embed_Message'):
        await late_E.delete()

    # 新しいEmbed
    Sended_Mes = await ctx.send(embed=embed)
    g_opts[gid]['Embed_Message'] = Sended_Mes 
    await Sended_Mes.add_reaction("⏯")
    await Sended_Mes.add_reaction("⏩")
    await Sended_Mes.add_reaction("🔁")
    if g_opts[gid].get('playlist'):
        await Sended_Mes.add_reaction("♻")
        await Sended_Mes.add_reaction("🔀")

    #print(f"{guild.name} : #再生中の曲　<{g_opts[guild.id]['queue'][0][1]}>")


@client.event
async def on_reaction_add(Reac,User):
    vc = Reac.message.guild.voice_client
    guild = Reac.message.guild
    gid = guild.id
    if User.bot or Reac.message.author.id != client.user.id: return
    asyncio.create_task(Reac.remove(User))
    if vc.is_playing() or vc.is_paused():

        #### Setting
        # Play Pause
        if Reac.emoji == '⏯':
            if vc.is_paused():
                print(f'{guild.name} : #resume')
                vc.resume()
            elif vc.is_playing():
                print(f'{guild.name} : #stop')
                vc.pause()

        # 次の曲
        if Reac.emoji == '⏩':
            await def_skip(Reac.message)

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
        url = g_opts[gid]['queue'][0][1]
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
        IN = InnerTube()
        Vdic = await loop.run_in_executor(None,IN.player,Vid)
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
            del g_opts[gid]['queue'][0]
            print(f'{guild.name} : #次の曲へ skip')
            vc.stop()
        




##############################################################################
# Play & Queue
##############################################################################

@client.command()
async def queue(ctx,*args):
    await def_play(ctx,args,1)

@client.command()
async def q(ctx,*args):
    await def_play(ctx,args,1)

@client.command()
async def play(ctx,*args):
    await def_play(ctx,args,0)

@client.command()
async def p(ctx,*args):
    await def_play(ctx,args,0)

async def def_play(ctx,args,mode_q):
    if not await join_check(ctx): return
    guild = ctx.guild
    vc = guild.voice_client
    gid = guild.id

    # 一時停止していた場合再生 開始
    if args == ():
        if vc.is_paused():
            vc.resume()
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
    web_url = None
    loud_vol = None
    loop = asyncio.get_event_loop()
    if not re_URL.match(arg):
        source,web_url,loud_vol = await pytube_search(arg,'video')

    elif re_URL_YT.match(arg):
        try: source,loud_vol = await pytube_vid(arg)
        except Exception as e:
            print(f"Error : Audio only 失敗 {e}")
            return
        else:
            web_url = arg

    else:
        with YoutubeDL({'format': 'best','quiet':True,'noplaylist':True}) as ydl:
            try: info = await loop.run_in_executor(None,ydl.extract_info,arg,False)
            except Exception as e:
                print(f"Error : Audio + Video 失敗 {e}")
                return
            else:
                source = info['url']
                web_url = arg
    
        # URL確認
    if not re_URL.match(source): return

        # playlist 再生中のお客様はお断り
    if g_opts[gid].get('playlist'):
        del g_opts[gid]['playlist']
        del g_opts[gid]['playlist_index']

        #Queueに登録
    if mode_q == 0:
        if g_opts[gid]['queue'] == []:
            g_opts[gid]['queue'].append((source,web_url,loud_vol))
        else:
            g_opts[gid]['queue'][0] = (source,web_url,loud_vol)
    else:
        g_opts[gid]['queue'].append((source,web_url,loud_vol))

        # 再生されるまでループ
    if mode_q == 0:
        if vc.is_playing():
            vc.stop()
        else:
            await play_loop(ctx,None,0)
        if vc.is_paused():
            vc.resume()
    else:
        if not vc.is_playing():
            await play_loop(ctx,None,0)
        if vc.is_paused():
            vc.resume()




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

    # 一時停止していた場合再生 開始
    if args == ():
        if vc.is_paused():
            vc.resume()
        return
    elif type(args) == str:
        arg = args
    else:
        arg = ' '.join(args)


    #**************************#　ネスト関数 #****************************#
    # Playlist 全体ダウンロード
    async def yt_all_list():
        yt_pl = pytube.Playlist(arg)
        loop = asyncio.get_event_loop()
        try: yt_pl = await loop.run_in_executor(None,DeferredGeneratorList,yt_pl.url_generator())
        except Exception as e:
            print(f'Error : Playlist All-List {e}')
            return
        else:
            print(f"{guild.name} : Loaded all video in the playlist  [playlist_count: {str(len(yt_pl))}]")
            g_opts[gid]['playlist'] = yt_pl
    #*******************************************************************#


    # 君はほんとにplaylistなのかい　どっちなんだい！
    yt_first = None
    watch_url = None
    loud_vol = None
    

    ### PlayList 本体のURL ------------------------------------------------------------------------#
    if re_URL_PL.match(arg): 
        g_opts[gid]['playlist_index'] = 0
        await yt_all_list()

    ### PlayList と 動画が一緒についてきた場合 --------------------------------------------------------------#
    elif result_re := re_URL_PL_Video.match(arg):
        watch_url = result_re.group(2)
        arg = f'https://www.youtube.com/playlist?list={result_re.group(3)}'
        extract_url = f'https://www.youtube.com/watch?v={watch_url}'

        try: yt_first,loud_vol = await pytube_vid(extract_url)
        except Exception as e:
            print(f'Error : Playlist First-Music {e}')
        else:
            g_opts[gid]['queue'] = [(yt_first,extract_url,loud_vol)]
            g_opts[gid]['playlist'] = 'Temp'
            g_opts[gid]['loop'] = 0
            if vc.is_playing():
                vc.stop()
            else:
                await play_loop(ctx,None,0)
            if vc.is_paused():
                vc.resume()

        await yt_all_list()

        for i, temp in enumerate(g_opts[gid]['playlist']):
            if watch_url in temp:
                g_opts[gid]['playlist_index'] = i
                break
        if not g_opts[gid]['playlist_index']:
            g_opts[gid]['playlist_index'] = 0
        
    ### URLじゃなかった場合 -----------------------------------------------------------------------#
    elif not re_URL.match(arg):
        g_opts[gid]['playlist_index'] = 0
        g_opts[gid]['playlist'] = await pytube_search(arg,'playlist')
        g_opts[gid]['random_playlist'] = 0

    ### その他 例外------------------------------------------------------------------------#
    else: 
        print("playlistじゃないみたい")
        return

    g_opts[gid]['loop'] = 0
    if yt_first:
        # 再生
        if not vc.is_playing():
            await play_loop(ctx,None,0)

    else:
        g_opts[gid]['playlist_index'] -= 1
        g_opts[gid]['queue'] = []
    
        # 再生
        if vc.is_playing():
            vc.stop()
        else:
            await play_loop(ctx,None,0)
        if vc.is_paused():
            vc.resume()



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
    try :yt,loud_vol = await pytube_vid(extract_url)
    except Exception as e:
        print(f'Error : Playlist Extract {e}')
        return

    # Queue
    if yt:
        g_opts[gid]['queue'].append((yt,extract_url,loud_vol))

    # Print
    print(f"{guild.name} : Paylist add Queue  [Now len: {str(len(g_opts[gid]['queue']))}]")




#---------------------------------------------------------------------------------------
#   再生 Loop
#---------------------------------------------------------------------------------------
async def play_loop(ctx,played,did_time):
    guild = ctx.guild
    gid = guild.id
    vc = ctx.voice_client


    # あなたは用済みよ
    if not vc: return

    # Queue削除
    if g_opts[gid]['queue']:
        if g_opts[gid]['loop'] != 1 and g_opts[gid]['queue'][0][0] == played or (time.time() - did_time) <= 0.5:
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
    vc = ctx.voice_client
    if g_opts[gid]['queue'] != [] and not vc.is_playing():
        source_url = g_opts[gid]['queue'][0][0]
        played_time = time.time()
        print(f"{guild.name} : Play  [Now len: {str(len(g_opts[gid]['queue']))}]")

        volume = -20
        if loud_vol := g_opts[gid]['queue'][0][2]:
            if loud_vol <= 0:
                loud_vol /= 2
            volume -= int(loud_vol)

        FFMPEG_OPTIONS = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -analyzeduration 2147483647 -probesize 2147483647",
            'options': f'-vn -c:a libopus -af "volume={volume}dB" -application lowdelay'
            }
            
        source_play = await discord.FFmpegOpusAudio.from_probe(source_url,**FFMPEG_OPTIONS)
        vc.play(source_play,after=lambda e: asyncio.run(play_loop(ctx,source_url,played_time)))

        print(ctx.channel.id)
        if late_E := g_opts[gid]['may_i_edit'].get(ctx.channel.id):
            embed = await Edit_Embed(gid)
            Play_Loop_Embed.append((False,late_E,embed))

        else:
            Play_Loop_Embed.append((True,ctx))


async def Send_Embed():
    while True:
        try:
            await asyncio.sleep(0.2)
            while Play_Loop_Embed:
                late_E = Play_Loop_Embed[0][1]
                if Play_Loop_Embed[0][0]:
                    await playing(late_E)
                else:
                    embed = Play_Loop_Embed[0][2]
                    await late_E.edit(embed=embed)
                del Play_Loop_Embed[0]
        except Exception as e:
            print(f'Error Send_Embed : {e}')



@client.event
async def on_message(message):
    if message.guild.voice_client:
        print(message.channel.id)
        if message.author.id == client.user.id:
            g_opts[message.guild.id]['may_i_edit'][message.channel.id] = message
        else:
            g_opts[message.guild.id]['may_i_edit'][message.channel.id] = None
    
    await client.process_commands(message)




#--------------------------------------------------------------------------------------------
#   居たら楽な関数達
#--------------------------------------------------------------------------------------------
async def pytube_vid(url):
    Vid = re_URL_Video.match(url).group(4)
    loop = asyncio.get_event_loop()
    INN = InnerTube()
    Vdic = await loop.run_in_executor(None,INN.player,Vid)

    St_Url = await _format(Vdic)
    St_Vol = Vdic.get('playerConfig',{}).get('audioConfig',{}).get('loudnessDb',None)
    return St_Url,St_Vol


async def _format(Vdic):
    formats = Vdic['streamingData'].get('formats',[])
    formats.extend(Vdic['streamingData'].get('adaptiveFormats',[]))
    res = []
    for fm in formats:
        if 249 <= fm['itag'] <= 251 or 139 <= fm['itag'] <= 141:
            res.append(fm)
    return res[-1]['url']


async def pytube_search(arg,mode):
    loop = asyncio.get_event_loop()
    pyt = pytube.Search(arg)
    Vdic = await loop.run_in_executor(None,pyt.fetch_and_parse)
    if pyt:
        if mode == 'video':
            INN = InnerTube()
            Vdic = await loop.run_in_executor(None,INN.player,Vdic[0][0].video_id)
            Web_Url = f"https://youtu.be/{Vdic['videoDetails']['videoId']}"
            St_Vol = Vdic.get('playerConfig',{}).get('audioConfig',{}).get('loudnessDb',None)
            St_Url = await _format(Vdic)
            return St_Url,Web_Url,St_Vol

        if mode == 'playlist':
            Web_Url = [temp.watch_url for temp in Vdic[0]]
            return Web_Url


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
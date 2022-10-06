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
import random
from concurrent.futures import ThreadPoolExecutor
import requests
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
_executor = ThreadPoolExecutor(1)
Play_Loop_Embed = []

re_false = re.compile(r'(f|0|ふぁlせ)')
re_true = re.compile(r'(t|1|ｔるえ)')
re_random = re.compile(r'(r|2|らんどm)')
re_URL_YT = re.compile(r'https://((www.|)youtube.com|youtu.be)/')
re_URL_Video = re.compile(r'https://((www.|)youtube.com/watch|youtu.be/)')
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
        print(f'{ctx.guild.name} : #join')
        await ctx.author.voice.channel.connect()
        g_opts[ctx.guild.id] = {}
        g_opts[ctx.guild.id]['loop'] = 1
        g_opts[ctx.guild.id]['loop_playlist'] = 1
        g_opts[ctx.guild.id]['queue'] = []
    

@client.command()
async def bye(ctx):
    gid = ctx.guild.id
    if ctx.voice_client:
        print(f'{ctx.guild.name} : #切断')
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
    if User.bot: return
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
            if g_opts[gid]['loop_playlist'] == 2:       #Random => False     LOOPしてるからね
                g_opts[gid]['loop_playlist'] = 0
            elif g_opts[gid]['loop_playlist'] == 0:     #Flse => True
                g_opts[gid]['loop_playlist'] = 1
            elif g_opts[gid]['loop_playlist'] == 1:     #True => False
                g_opts[gid]['loop_playlist'] = 0

        # Random
        if Reac.emoji =='🔀':
            if g_opts[gid]['loop_playlist'] == 2:       #Random => True     LOOPしてるからね
                g_opts[gid]['loop_playlist'] = 1
            elif g_opts[gid]['loop_playlist'] == 0:     #Flse => Random
                g_opts[gid]['loop_playlist'] = 2
            elif g_opts[gid]['loop_playlist'] == 1:     #True => Random
                g_opts[gid]['loop_playlist'] = 2


        #### Message
        # Get Embed
        embed = await Edit_Embed(gid)
        if not embed: return
        # Edit
        await Reac.message.edit(embed=embed)
        if Reac.message != (late_E := g_opts[gid]['Embed_Message']):
            await late_E.edit(embed=embed)



async def Edit_Embed(gid):
    try:
        url = g_opts[gid]['queue'][0][1]
    except IndexError:
        return None

    def pytube_info(url):
        pyt_def = pytube.YouTube(url)
        pyt_title = str(pyt_def.title)
        pyt_channel = pyt_def.author
        pyt_VidID = pyt_def.video_id
        pyt_C_url = pyt_def.channel_url
        r = BeautifulSoup(requests.get(pyt_def.channel_url).text,'html.parser')
        r = r.find('link',rel="image_src").get('href')
        return pyt_title, pyt_channel, pyt_VidID, r, pyt_C_url
    
    # emoji
    V_loop= PL_loop= Random_P= ':red_circle:'
    if g_opts[gid]['loop'] == 1: V_loop = ':green_circle:'
    if g_opts[gid].get('playlist'):
        if g_opts[gid]['loop_playlist'] >= 1: PL_loop = ':green_circle:'
        if g_opts[gid]['loop_playlist'] == 2: Random_P = ':green_circle:'

    # Embed
    if re_URL_YT.match(url):
        loop = asyncio.get_event_loop()
        title, channnel, VidID, C_Icon, C_url = await loop.run_in_executor(_executor,pytube_info,url)
        embed=discord.Embed(title=title, url=url)
        embed.set_thumbnail(url=f'https://img.youtube.com/vi/{VidID}/mqdefault.jpg')
        embed.set_author(name=channnel, url=C_url, icon_url=C_Icon)
    else:
        embed=discord.Embed(title=url, url=url)

    if g_opts[gid].get('playlist'):
        embed.add_field(name="単曲ループ", value=f'🔁 : {V_loop}', inline=True)
        embed.add_field(name="Playlistループ", value=f'♻ : {PL_loop}', inline=True)
        embed.add_field(name="シャッフル", value=f'🔀 : {Random_P}', inline=True)
    else:
        embed.add_field(name="ループ", value=f'🔁 : {V_loop}', inline=True)
    
    return embed




#----------------------------------------------------------------------------
#   Loop 
#----------------------------------------------------------------------------
@client.command()
async def loop(ctx,*args):
    await def_loop(ctx,args)

@client.command()
async def l(ctx,*args):
    await def_loop(ctx,args)

async def def_loop(ctx,args):
    # joinしてる？
    if not ctx.voice_client: return
    gid = ctx.guild.id

    # loop 単体切り替え
    if args == ():
        if g_opts[gid]['loop'] == 0:args = ("1")
        if g_opts[gid]['loop'] == 1:args = ("0")

    # loop 指定切り替え
    if args != ():
        arg = args[0].lower()

        if re_false.match(arg):
            g_opts[gid]['loop'] = 0

        if re_true.match(arg):
            g_opts[gid]['loop'] = 1

    # playlist
    if args != ():
        if re_str_PL.match(args[0].lower()):
            if len(args) == 1:
                if g_opts[gid]['loop_playlist'] == 0: args = ('pl','1')
                if g_opts[gid]['loop_playlist'] == 1: args = ('pl','2')
                if g_opts[gid]['loop_playlist'] == 2: args = ('pl','0')
            if len(args) >= 2:
                arg = args[1].lower()
                if re_false.match(arg):
                    g_opts[gid]['loop_playlist'] = 0
                if re_true.match(arg):
                    g_opts[gid]['loop_playlist'] = 1
                if re_random.match(arg):
                    g_opts[gid]['loop_playlist'] = 2

    # 現在の Loop の状態を送信
    pl = ''
    if g_opts[gid].get('playlist'):
        pl_ = 'None'
        if g_opts[gid]['loop_playlist'] == 0: pl_ = 'False'
        if g_opts[gid]['loop_playlist'] == 1: pl_ = 'True'
        if g_opts[gid]['loop_playlist'] == 2: pl_ = 'Random'
        pl = f' [Playlist : {pl_}]'

    if g_opts[gid]['loop'] <= 0:
        await ctx.send(embed=discord.Embed(title=f"Loop : False{pl}"))
        print(f'{ctx.guild.name} : #loop False{pl}')

    if g_opts[gid]['loop'] == 1:
        await ctx.send(embed=discord.Embed(title=f"Loop : True{pl}"))
        print(f'{ctx.guild.name} : #loop True{pl}')




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
    vc = ctx.guild.voice_client
    if vc:
        if g_opts[ctx.guild.id]['queue'] != []:
            del g_opts[ctx.guild.id]['queue'][0]
            print(f'{ctx.guild.name} : #次の曲へ skip')
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
        source,web_url,loud_vol = await loop.run_in_executor(_executor,pytube_search,arg,'video')

    elif re_URL_YT.match(arg):
        try: source,loud_vol = await loop.run_in_executor(_executor,pytube_vid,arg)
        except Exception as e:
            print(f"Error : Audio only 失敗 {e}")
            return
        else:
            web_url = arg

    else:
        with YoutubeDL({'format': 'best','quiet':True,'noplaylist':True}) as ydl:
            try: info = await loop.run_in_executor(_executor,ydl.extract_info,arg,False)
            except Exception as e:
                print(f"Error : Audio + Video 失敗 {e}")
                return
            else:
                source = info['url']
                web_url = arg
    
        # URL確認
    if not re_URL.match(source): return

        # playlist 再生中のお客様はお断りよ
    if g_opts[guild.id].get('playlist'):
        del g_opts[guild.id]['playlist']
        del g_opts[guild.id]['playlist_index']

        #Queueに登録
    if mode_q == 0:
        if g_opts[guild.id]['queue'] == []:
            g_opts[guild.id]['queue'].append((source,web_url,loud_vol))
        else:
            g_opts[guild.id]['queue'][0] = (source,web_url,loud_vol)
    else:
        g_opts[guild.id]['queue'].append((source,web_url,loud_vol))

        # 再生されるまでループ
    if mode_q == 0:
        if vc.is_playing():
            if late_E := g_opts[guild.id].get('Embed_Message'):
                await late_E.delete()
                g_opts[guild.id]['Embed_Message'] = None
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
        try: yt_pl = await loop.run_in_executor(_executor,pytube_pl,arg)
        except Exception as e:
            print(f'Error : Playlist All-List {e}')
            return
        else:
            print(f"{guild.name} : Loaded all video in the playlist  [playlist_count: {str(len(yt_pl))}]")
            g_opts[guild.id]['playlist'] = yt_pl
    #*******************************************************************#


    # 君はほんとにplaylistなのかい　どっちなんだい！
    yt_first = None
    watch_url = None
    loud_vol = None
    loop = asyncio.get_event_loop()

    ### PlayList 本体のURL ------------------------------------------------------------------------#
    if re_URL_PL.match(arg): 
        g_opts[guild.id]['playlist_index'] = 0
        await yt_all_list()

    ### PlayList と 動画が一緒についてきた場合 --------------------------------------------------------------#
    elif result_re := re_URL_PL_Video.match(arg):
        watch_url = result_re.group(2)
        arg = f'https://www.youtube.com/playlist?list={result_re.group(3)}'
        extract_url = f'https://www.youtube.com/watch?v={watch_url}'

        try: yt_first,loud_vol = await loop.run_in_executor(_executor,pytube_vid,extract_url)
        except Exception as e:
            print(f'Error : Playlist First-Music {e}')
        else:
            g_opts[guild.id]['queue'] = [(yt_first,extract_url,loud_vol)]
            g_opts[guild.id]['playlist'] = 'Temp'
            g_opts[guild.id]['loop'] = 0
            if vc.is_playing():
                if late_E := g_opts[guild.id].get('Embed_Message'):
                    await late_E.delete()
                    g_opts[guild.id]['Embed_Message'] = None
                    vc.stop()
            else:
                await play_loop(ctx,None,0)
            if vc.is_paused():
                vc.resume()

        await yt_all_list()

        for i, temp in enumerate(g_opts[guild.id]['playlist']):
            if watch_url in temp:
                g_opts[guild.id]['playlist_index'] = i
                break
        if not g_opts[guild.id]['playlist_index']:
            g_opts[guild.id]['playlist_index'] = 0
        
    ### URLじゃなかった場合 -----------------------------------------------------------------------#
    elif not re_URL.match(arg):
        g_opts[guild.id]['playlist_index'] = 0
        g_opts[guild.id]['playlist'] = await loop.run_in_executor(_executor,pytube_search,arg,'playlist')

    ### その他 例外------------------------------------------------------------------------#
    else: 
        print("playlistじゃないみたい")
        return

    g_opts[guild.id]['loop'] = 0
    if yt_first:
        # 再生
        if not vc.is_playing():
            await play_loop(ctx,None,0)

    else:
        g_opts[guild.id]['playlist_index'] -= 1
        g_opts[guild.id]['queue'] = []
    
        # 再生
        if vc.is_playing():
            if late_E := g_opts[guild.id].get('Embed_Message'):
                await late_E.delete()
                g_opts[guild.id]['Embed_Message'] = None
                vc.stop()
        else:
            await play_loop(ctx,None,0)
        if vc.is_paused():
            vc.resume()



# playlistダウンロード
async def ydl_playlist(guild):

    if g_opts[guild.id]['playlist_index'] >= len(g_opts[guild.id]['playlist']):
        g_opts[guild.id]['playlist_index'] = 0
        if g_opts[guild.id]['loop_playlist'] == 0:
            del g_opts[guild.id]['playlist']
            del g_opts[guild.id]['playlist_index']
            return

    loop = asyncio.get_event_loop()
    extract_url = g_opts[guild.id]['playlist'][g_opts[guild.id]['playlist_index']]
    try :yt,loud_vol = await loop.run_in_executor(_executor,pytube_vid,extract_url)
    except Exception as e:
        print(f'Error : Playlist Extract {e}')
        return

    # Queue
    if yt:
        g_opts[guild.id]['queue'].append((yt,extract_url,loud_vol))

    # Print
    print(f"{guild.name} : Paylist add Queue  [Now len: {str(len(g_opts[guild.id]['queue']))}]")




#---------------------------------------------------------------------------------------
#   再生 Loop
#---------------------------------------------------------------------------------------
async def play_loop(ctx,played,did_time):
    guild = ctx.guild
    gid = guild.id
    vc = ctx.voice_client


    # あなたは用済みよ
    if not vc.is_connected(): return

    # Queue削除
    if g_opts[gid]['queue']:
        if g_opts[gid]['loop'] != 1 and g_opts[gid]['queue'][0][0] == played or (time.time() - did_time) <= 0.5:
            del g_opts[guild.id]['queue'][0]

    # Playlistのお客様Only
    if g_opts[gid].get('playlist') and g_opts[gid]['queue'] == []:
        if g_opts[gid]['loop_playlist'] == 2:
            for_count = 0
            while g_opts[gid]['playlist_index'] == (new_index := random.randint(0,len(g_opts[gid]['playlist']) - 1)):
                for_count += 1
                if for_count == 10: break
            g_opts[gid]['playlist_index'] = new_index
        else:
            g_opts[guild.id]['playlist_index'] += 1
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

        if did_time != 0 and g_opts[gid].get('Embed_Message'):
            late_E = g_opts[gid].get('Embed_Message')
            embed = await Edit_Embed(gid)
            Play_Loop_Embed.append((False,late_E,embed))

        else:
            Play_Loop_Embed.append((True,ctx))


async def Send_Embed():
    while True:
        try:
            await asyncio.sleep(0.5)
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




#--------------------------------------------------------------------------------------------
#   居たら楽な関数達
#--------------------------------------------------------------------------------------------
def pytube_vid(url):
    pyt_def = pytube.YouTube(url)
    pyt_url = str(pyt_def.streams.filter(only_audio=True).last().url)
    pyt_vol = pyt_def.vid_info.get('playerConfig',{}).get('audioConfig',{}).get('loudnessDb',None)
    return pyt_url,pyt_vol


def pytube_pl(url):
    pyt_def = pytube.Playlist(url).video_urls
    return list(pyt_def)


def pytube_search(arg,mode):
    pyt_def = pytube.Search(arg).results
    source,web_url = None,None
    if pyt_def:
        if mode == 'video':
            source = str(pyt_def[0].streams.filter(only_audio=True).last().url)
            web_url = str(pyt_def[0].watch_url)
            pyt_vol = pyt_def[0].vid_info.get('playerConfig',{}).get('audioConfig',{}).get('loudnessDb',None)
            return source,web_url,pyt_vol

        if mode == 'playlist':
            web_url = [str(temp.watch_url) for temp in pyt_def]
            return web_url


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
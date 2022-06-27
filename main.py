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



#--------------------# 設定 関係 #------------------------#

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

#-----------------------------------------------------------#




client = commands.Bot(command_prefix=config['DEFAULT']['Prefix'])
voice_client = None
g_opts = {}
_executor = ThreadPoolExecutor(1)

@client.event
async def on_ready():
    print('Logged in')
    print(client.user.name)
    print(client.user.id)
    print('----------------')


@client.command()
async def join(ctx):
    if ctx.author.voice:
        print(f'{ctx.guild.name} : #join')
        await ctx.author.voice.channel.connect()
        g_opts[ctx.guild.id] = {}
        g_opts[ctx.guild.id]['loop'] = 1
        g_opts[ctx.guild.id]['loop_playlist'] = 1
        g_opts[ctx.guild.id]['queue'] = []
        g_opts[ctx.guild.id]['playing'] = []
    
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


@client.command()
async def playing(ctx):
    vc = ctx.voice_client
    if vc.is_playing():
        print(f"{ctx.guild.name} : #再生中の曲　<{g_opts[ctx.guild.id]['playing'][0]}>")
        await ctx.send(g_opts[ctx.guild.id]['playing'][0])


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
    re_false = re.compile(r'(false|f|0|ふぁlせ)$')
    re_true = re.compile(r'(true|t|1|tるえ)$')


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
        if re.match(r'(playlist|pl|p|pぁyぃst)$',args[0].lower()):
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
                if re.match(r'(random|r|2|らんどm)$',arg):
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
            del g_opts[ctx.guild.id]['playing'][0]
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
    if re.match(r'https://(www.|)youtube.com/playlist\?list=.+$',arg):
        await def_playlist(ctx,arg)
        return
    if re.match(r'https://(www.|)youtube.com/',arg) and not re.match(r'https://(www.|)youtube.com/watch.+$',arg):
        return

    # Stream URL
    loop = asyncio.get_event_loop()
    web_url = None
    if not re.match(r'http.+$',arg):
        source,web_url = await loop.run_in_executor(_executor,pytube_search,arg,'video')
        if web_url:
            await ctx.send(web_url)
        else:
            await ctx.send('検索結果なし')
            return

    elif re.match(r'https://(www.|)youtube.com/',arg):
        try: source = await loop.run_in_executor(_executor,pytube_vid,arg)
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
    if not re.match(r'http.+$',source): return

        # playlist 再生中のお客様はお断りよ
    if g_opts[guild.id].get('playlist'):
        del g_opts[guild.id]['playlist']
        del g_opts[guild.id]['playlist_index']
        g_opts[guild.id]['queue'] = []
        g_opts[guild.id]['playing'] = []
        g_opts[guild.id]['loop'] = 1

        #Queueに登録
    if mode_q == 0:
        if g_opts[guild.id]['queue'] == []:
            g_opts[guild.id]['queue'].append(source)
            g_opts[guild.id]['playing'].append(web_url)
        else:
            g_opts[guild.id]['queue'][0] = source
            g_opts[guild.id]['playing'][0] = web_url
    else:
        g_opts[guild.id]['queue'].append(source)
        g_opts[guild.id]['playing'].append(web_url)

        # 再生されるまでループ
    if mode_q == 0:
        if vc.is_playing():
            vc.stop()
        else:
            await play_loop(guild,None,0)
        if vc.is_paused():
            vc.resume()
    else:
        if not vc.is_playing():
            await play_loop(guild,None,0)
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
    loop = asyncio.get_event_loop()
    watch_url = None
    # --------------------------------------------------------------------------------#
    if re.match(r'https://(www.|)youtube.com/playlist\?list=.+$',arg): 
        g_opts[guild.id]['playlist_index'] = 0
        await yt_all_list()

    # --------------------------------------------------------------------------------#
    elif result_re := re.match(r'https://(www.|)youtube.com/watch\?v=(.+)&list=(.+)&index=(\d+)$',arg):
        watch_url = result_re.group(2)
        g_opts[guild.id]['playlist_index'] = int(result_re.group(4))
        arg = f'https://www.youtube.com/playlist?list={result_re.group(3)}'
        extract_url = f'https://www.youtube.com/watch?v={watch_url}'

        try: yt_first = await loop.run_in_executor(_executor,pytube_vid,extract_url)
        except Exception as e:
            print(f'Error : Playlist First-Music {e}')
        else:
            g_opts[guild.id]['queue'] = [yt_first]
            g_opts[guild.id]['playing'] = [extract_url]
            if vc.is_playing():
                vc.stop()
            else:
                await play_loop(guild,None,0)
            if vc.is_paused():
                vc.resume()

        await yt_all_list()

        for i, temp in enumerate(g_opts[guild.id]['playlist']):
            if watch_url in temp:
                g_opts[guild.id]['playlist_index'] = i
                break

    # --------------------------------------------------------------------------------#
    elif not re.match(r'http',arg):
        g_opts[guild.id]['playlist_index'] = 0
        g_opts[guild.id]['playlist'] = await loop.run_in_executor(_executor,pytube_search,arg,'playlist')

    # --------------------------------------------------------------------------------#
    else: 
        print("playlistじゃないみたい")
        return


    g_opts[guild.id]['loop'] = 0
    if yt_first:
        # 再生
        if not vc.is_playing():
            await play_loop(guild,None,0)

    else:
        g_opts[guild.id]['playlist_index'] -= 1
        g_opts[guild.id]['queue'] = []
        g_opts[guild.id]['playing'] = []
    
        # 再生
        if vc.is_playing():
            vc.stop()
        else:
            await play_loop(guild,None,0)
        if vc.is_paused():
            vc.resume()






# playlistダウンロード
async def ydl_playlist(guild):
    loop = asyncio.get_event_loop()

    if g_opts[guild.id]['playlist_index'] >= len(g_opts[guild.id]['playlist']):
        g_opts[guild.id]['playlist_index'] = 0
        if g_opts[guild.id]['loop_playlist'] == 0:
            del g_opts[guild.id]['playlist']
            del g_opts[guild.id]['playlist_index']
            return

    extract_url = g_opts[guild.id]['playlist'][g_opts[guild.id]['playlist_index']]
    try :yt = await loop.run_in_executor(_executor,pytube_vid,extract_url)
    except Exception as e:
        print(f'Error : Playlist Extract {e}')
        return

    # Queue
    if yt:
        g_opts[guild.id]['queue'].append(yt)
        g_opts[guild.id]['playing'].append(extract_url)

    # Print
    print(f"{guild.name} : Paylist add Queue  [Now len: {str(len(g_opts[guild.id]['queue']))}]")





#---------------------------------------------------------------------------------------
#   再生 Loop
#---------------------------------------------------------------------------------------
async def play_loop(guild,played,did_time):

    # あなたは用済みよ
    if not guild.voice_client: return

    # Queue削除
    if g_opts[guild.id]['queue']:
        if g_opts[guild.id]['loop'] != 1 and g_opts[guild.id]['queue'][0] == played or (time.time() - did_time) <= 0.5:
            del g_opts[guild.id]['queue'][0]
            del g_opts[guild.id]['playing'][0]

    # Playlistのお客様Only
    if g_opts[guild.id].get('playlist') and g_opts[guild.id]['queue'] == []:
        if g_opts[guild.id]['loop_playlist'] == 2:
            for_count = 0
            while g_opts[guild.id]['playlist_index'] == (new_index := random.randint(0,len(g_opts[guild.id]['playlist']) - 1)):
                for_count += 1
                if for_count == 10: break
            g_opts[guild.id]['playlist_index'] = new_index
        else:
            g_opts[guild.id]['playlist_index'] += 1
        await ydl_playlist(guild)

    # 再生
    vc = guild.voice_client
    if g_opts[guild.id]['queue'] != [] and not vc.is_playing():
        source_url = g_opts[guild.id]['queue'][0]
        played_time = time.time()
        print(f"{guild.name} : Play  [Now len: {str(len(g_opts[guild.id]['queue']))}]")

        FFMPEG_OPTIONS = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -analyzeduration 2147483647 -probesize 2147483647",
            'options': '-vn -c:a libopus -af "volume=0.1" -application lowdelay'}
            
        source_play = discord.FFmpegOpusAudio(source_url,**FFMPEG_OPTIONS,bitrate=128)
        vc.play(source_play,after=lambda e: asyncio.run(play_loop(guild,source_url,played_time)))





#--------------------------------------------------------------------------------------------
#   居たら楽な関数達
#--------------------------------------------------------------------------------------------
def pytube_vid(url):
    pyt_def = pytube.YouTube(url)
    return str(pyt_def.streams.get_audio_only().url)

def pytube_pl(url):
    pyt_def = pytube.Playlist(url).video_urls
    return list(pyt_def)

def pytube_search(arg,mode):
    pyt_def = pytube.Search(arg).results
    source,web_url = None,None
    if pyt_def:
        if mode == 'video':
            source = str(pyt_def[0].streams.get_audio_only().url)
            web_url = str(pyt_def[0].watch_url)
            return source,web_url

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
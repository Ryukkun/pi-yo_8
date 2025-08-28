import discord
import os
import asyncio
import logging
from discord.ext import commands, tasks
from typing import Dict


os.chdir(os.path.dirname(os.path.abspath(__file__)))


####  Config
try: from pi_yo_8 import config
except Exception:
    CLines= [
        "Prefix = ','",
        "#youtube data api v3",
        "youtube_key = ''",
        "Token = ''"
    ]
    with open('config.py','w') as f:
        f.write('\n'.join(CLines))
    
    raise Exception('Config ファイルを生成しました')


from pi_yo_8.gui._embed_controller import EmbedController
from pi_yo_8.voice_client import MultiAudioVoiceClient
from pi_yo_8.music_control import MusicController
from pi_yo_8.utils import set_logger


set_logger()
_log = logging.getLogger(__name__)


####  起動準備 And 初期設定
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.voice_states = True
client = commands.Bot(command_prefix=config.Prefix,intents=intents)
g_opts:Dict[int, 'DataInfo'] = {}





tree = client.tree

@tree.command(description="年中無休でカラオケ生活 のど自慢系ぴーよ")
@discord.app_commands.describe(arg='URL or 検索したい文字')
async def download(ctx:discord.Interaction, arg:str):
    if embeds := await MusicController.download(arg):
        ctx:commands.Context = await commands.Context.from_interaction(ctx)
        for em in embeds:
            await ctx.send(embed=em, ephemeral=True)


####  基本的コマンド
@client.event
async def on_ready():
    _log.info('Logged in')
    _log.info(client.user.name)
    _log.info(client.user.id)
    print('--------------------------')
    await tree.sync()

    activity = discord.Activity(name='華麗なる美声', type=discord.ActivityType.listening)
    await client.change_presence(activity=activity)
    # Bot Activity
    # while True:
    #     mem = psutil.virtual_memory()
    #     detail = f'CPU: {psutil.cpu_percent()}%   Mem: {mem.used//100000000/10}/{mem.total//100000000/10}'
    #     activity = discord.Activity(name='華麗なる美声', type=discord.ActivityType.listening)
    #     await client.change_presence(activity=activity)
    #     await asyncio.sleep(60)
    


@client.command()
async def join(ctx:commands.Context):
    gid = ctx.guild.id
    if not g_opts.get(gid):
        try: 
            await ctx.author.voice.channel.connect(self_deaf=True)
            _log.info(f'{ctx.guild.name} : #join')
            g_opts[gid] = DataInfo(ctx.guild)
            return True
        except Exception as e:
            print(e)


@client.command()
async def bye(ctx:commands.Context):
    guild = ctx.guild
    if info := g_opts.get(guild.id):
        await info.bye()

    

@client.command()
async def speed(ctx:commands.Context, arg:float):
    gid = ctx.guild.id
    if data := g_opts.get(gid):
        await data.music.player_track.speed.set(arg)


@client.command()
async def pitch(ctx:commands.Context, arg:int):
    gid = ctx.guild.id
    if data := g_opts.get(gid):
        await data.music.player_track.pitch.set(arg)


#--------------------------------------------------
# GUI操作
#--------------------------------------------------
@client.command()
async def playing(ctx:commands.Context):
    if info := g_opts.get(ctx.guild.id):
        info.music.lastest_ch = ctx.channel
        await info.music.playing()



#---------------------------------------------------------------------------------------------------
#   Skip
#---------------------------------------------------------------------------------------------------

@client.command(aliases=['s'])
async def skip(ctx:commands.Context, *arg):
    if arg:
        arg = arg[0]
    else: arg = None
    try:
        await g_opts[ctx.guild.id].music.skip(arg)
    except KeyError:pass


#---------------------------------------------------------------------------------------
#   Download
#---------------------------------------------------------------------------------------
@client.command(aliases=['dl'])
async def download(ctx:commands.Context, arg):
    if embeds := await MusicController.download(arg):
       for em in embeds:
            await ctx.send(embed=em)



##############################################################################
# Play & Queue
##############################################################################

@client.command(aliases=['q'])
async def queue(ctx:commands.Context, *args):
    await join(ctx)
    if g_opts.get(ctx.guild.id):
        await g_opts[ctx.guild.id].music.def_queue(ctx,args)



@client.command(aliases=['p','pl'])
async def play(ctx:commands.Context, *args):
    await join(ctx)
    if g_opts.get(ctx.guild.id):
        await g_opts[ctx.guild.id].music.play(ctx,args)








class DataInfo():
    def __init__(self, guild:discord.Guild):
        self.guild = guild
        self.vc = guild.voice_client
        self.loop = client.loop
        self.client = client
        self.config = config
        self.MA = MultiAudioVoiceClient(guild, client, self)
        self.music = MusicController(self)
        self.embed = EmbedController(self)
        self.loop_5.start()


    async def bye(self, text:str='切断'):
        self.loop.create_task(self._bye(text))
        self.loop_5.stop()


    async def _bye(self, text:str):
        self.MA.kill()
        del g_opts[self.guild.id]

        _log.info(f'{self.guild.name} : #{text}')
        await asyncio.sleep(0.02)
        try: await self.vc.disconnect()
        except Exception: pass

        while self.loop_5.is_running():
            await asyncio.sleep(1)
        if message := self.music.embed_playing:
            await message.delete()
        if message := self.music.embed_play_options:
            await message.delete()


    @tasks.loop(seconds=5.0)
    async def loop_5(self):
        if not g_opts.get(self.guild.id):
            return

        # 強制切断検知
        mems = self.vc.channel.members
        if not client.user.id in [_.id for _ in mems]:
            await self.bye('強制切断')

        # voice channelに誰もいなくなったことを確認
        elif not False in [_.bot for _ in mems]:
            self.count_loop += 1
            if 2 <= self.count_loop:
                await self.bye('誰もいなくなったため 切断')

        # Reset Count
        else:
            self.count_loop = 0


        # Music Embed
        await self.embed.task_loop()


client.run(config.Token, log_level=logging.WARNING)
import discord
import os
import asyncio
import time
import logging
from discord.ext import commands, tasks
from typing import Dict

from pi_yo_8.voice_client import MultiAudio
from pi_yo_8.music import MusicController




os.chdir(os.path.dirname(os.path.abspath(__file__)))

####  Config
try: import config
except Exception:
    CLines= [
        "Prefix = '.'",
        "Token = None"
    ]
    with open('config.py','w') as f:
        f.write('\n'.join(CLines))
    import config




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
    if embeds := await MusicController._download(arg):
        ctx:commands.Context = await commands.Context.from_interaction(ctx)
        for em in embeds:
            await ctx.send(embed=em, ephemeral=True)


####  基本的コマンド
@client.event
async def on_ready():
    print('Logged in')
    print(client.user.name)
    print(client.user.id)
    print('----------------')
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
    if vc := ctx.author.voice:
        gid = ctx.guild.id
        print(f'{ctx.guild.name} : #join')
        try: await vc.channel.connect(self_deaf=True)
        except discord.ClientException: return
        g_opts[gid] = DataInfo(ctx.guild)
        return True


@client.command()
async def bye(ctx:commands.Context):
    guild = ctx.guild
    gid = guild.id
    vc = guild.voice_client
    if vc:
        print(f'{guild.name} : #切断')
        await g_opts[gid]._bye()

    

@client.command()
async def speed(ctx:commands.Context, arg:float):
    guild = ctx.guild
    gid = guild.id
    vc = guild.voice_client
    if vc:
        if data := g_opts.get(gid):
            await data.Music.Mvc.speed.set(arg)


@client.command()
async def pitch(ctx:commands.Context, arg:int):
    guild = ctx.guild
    gid = guild.id
    vc = guild.voice_client
    if vc:
        if data := g_opts.get(gid):
            await data.Music.Mvc.pitch.set(arg)


#--------------------------------------------------
# GUI操作
#--------------------------------------------------
@client.command()
async def playing(ctx:commands.Context):
    try:
        g_opts[ctx.guild.id].Music.Latest_CH = ctx.channel
        await g_opts[ctx.guild.id].Music.playing()
    except KeyError:pass



#---------------------------------------------------------------------------------------------------
#   Skip
#---------------------------------------------------------------------------------------------------

@client.command(aliases=['s'])
async def skip(ctx:commands.Context, *arg):
    if arg:
        arg = arg[0]
    else: arg = None
    try:
        await g_opts[ctx.guild.id].Music.skip(arg)
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
    if not ctx.guild.voice_client:
        if not await join(ctx):
            return
    await g_opts[ctx.guild.id].Music.def_queue(ctx,args)



@client.command(aliases=['p','pl'])
async def play(ctx:commands.Context, *args):
    if not ctx.guild.voice_client:
        if not await join(ctx):
            return
    await g_opts[ctx.guild.id].Music.play(ctx,args)








class DataInfo():
    def __init__(self, guild:discord.Guild):
        self.guild = guild
        self.gn = guild.name
        self.gid = guild.id
        self.vc = guild.voice_client
        self.loop = client.loop
        self.client = client
        self.config = config
        self.MA = MultiAudio(guild, client, self)
        self.Music = MusicController(self)
        self.loop_5.start()


    async def _bye(self):
        self.loop_5.stop()
        self.MA.kill()
        del g_opts[self.gid]
        
        await asyncio.sleep(0.1)
        try: await self.vc.disconnect()
        except Exception: pass

        await asyncio.sleep(5)
        if late_E := self.Music.Embed_Message:
            await late_E.delete()


    @tasks.loop(seconds=5.0)
    async def loop_5(self):
        # Music Embed
        await self.Music._loop_5()

        # 強制切断検知
        mems = self.vc.channel.members
        if not client.user.id in [_.id for _ in mems]:
            self.count_loop += 1
            if 2 <= self.count_loop:
                print(f'{self.gn} : #強制切断')
                await self._bye()

        # voice channelに誰もいなくなったことを確認
        elif not False in [_.bot for _ in mems]:
            self.count_loop += 1
            if 2 <= self.count_loop:
                print(f'{self.gn} : #誰もいなくなったため 切断')
                await self._bye()

        # Reset Count
        else:
            self.count_loop = 0


client.run(config.Token, log_level=logging.WARNING)
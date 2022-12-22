import discord
import os
import asyncio
from discord.ext import commands, tasks

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
g_opts:dict[int, 'DataInfo'] = {}





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
        await _bye(guild)


async def _bye(guild:discord.Guild):
    gid = guild.id
    vc = guild.voice_client
    # 古いEmbedを削除
    Old_Music:MusicController = g_opts[gid].Music

    g_opts[gid].loop_5.cancel()
    g_opts[gid].MA.kill()
    g_opts[gid].Music.run_loop.cancel()
    del g_opts[gid]
    try: await vc.disconnect()
    except Exception: pass

    await asyncio.sleep(1.0)
    if late_E := Old_Music.Embed_Message:
        await late_E.delete()
    del Old_Music



#--------------------------------------------------
# GUI操作
#--------------------------------------------------
@client.command()
async def playing(ctx:commands.Context):
    try:
        g_opts[ctx.guild.id].Music.Latest_CH = ctx.channel
        await g_opts[ctx.guild.id].Music._playing()
    except KeyError:pass


@client.event
async def on_reaction_add(Reac:discord.Reaction, User:discord.Member):
    try:
        await g_opts[User.guild.id].Music.on_reaction_add(Reac,User)
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
        await g_opts[ctx.guild.id].Music._skip(arg)
    except KeyError:pass


#---------------------------------------------------------------------------------------
#   Download
#---------------------------------------------------------------------------------------
@client.command(aliases=['dl'])
async def download(ctx:commands.Context, arg):
    if embeds := await MusicController._download(arg):
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
    await g_opts[ctx.guild.id].Music._play(ctx,args,True)



@client.command(aliases=['p','pl'])
async def play(ctx:commands.Context, *args):
    if not ctx.guild.voice_client:
        if not await join(ctx):
            return
    await g_opts[ctx.guild.id].Music._play(ctx,args,False)








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


    @tasks.loop(seconds=5.0)
    async def loop_5(self):
        mems = self.vc.channel.members
        # 強制切断検知
        if not client.user.id in [_.id for _ in mems]:
            self.count_loop += 1
            if 2 <= self.count_loop:
                print(f'{self.gn} : #強制切断')
                await _bye(self.guild)

        # voice channelに誰もいなくなったことを確認
        elif not False in [_.bot for _ in mems]:
            self.count_loop += 1
            if 2 <= self.count_loop:
                print(f'{self.gn} : #誰もいなくなったため 切断')
                await _bye(self.guild)

        # Reset Count
        else:
            self.count_loop = 0


client.run(config.Token)
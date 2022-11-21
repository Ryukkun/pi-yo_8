import discord
import os
import asyncio
from discord.ext import commands

from voice_client import MultiAudio
from music import MusicController




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
g_opts = {}




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
        try: await vc.channel.connect(self_deaf=True)
        except discord.ClientException: return
        g_opts[gid] = DataInfo(ctx.guild)
        return True


@client.command()
async def bye(ctx):
    guild = ctx.guild
    gid = guild.id
    vc = guild.voice_client
    if vc:
        print(f'{guild.name} : #切断')

        # 古いEmbedを削除
        Old_Music = g_opts[gid].Music

        g_opts[gid].MA.loop = False
        del g_opts[gid]
        await vc.disconnect()
        
        await asyncio.sleep(1.0)
        if late_E := Old_Music.Embed_Message:
            await late_E.delete()
        del Old_Music
  
  
@client.event
async def on_voice_state_update(member, befor, after):
    # voice channelに誰もいなくなったことを確認
    if not befor.channel:
        return
    if befor.channel != after.channel:
        if vc := befor.channel.guild.voice_client:
            if not befor.channel == vc.channel:
                return
            if mems := befor.channel.members:
                for mem in mems:
                    if not mem.bot:
                        return
                await bye(befor.channel)



#--------------------------------------------------
# GUI操作
#--------------------------------------------------
@client.command()
async def playing(ctx):
    try:
        await g_opts[ctx.guild.id].Music._playing()
    except KeyError:pass


@client.event
async def on_reaction_add(Reac,User):
    try:
        await g_opts[User.guild.id].Music.on_reaction_add(Reac,User)
    except KeyError:pass


#---------------------------------------------------------------------------------------------------
#   Skip
#---------------------------------------------------------------------------------------------------

@client.command()
async def skip(ctx, arg):
    try:
        await g_opts[ctx.guild.id].Music._skip(arg)
    except KeyError:pass

@client.command()
async def s(ctx, arg):
    try:
        await g_opts[ctx.guild.id].Music._skip(arg)
    except KeyError:pass


##############################################################################
# Play & Queue
##############################################################################

@client.command()
async def queue(ctx,*args):
    if not ctx.guild.voice_client:
        if not await join(ctx):
            return
    await g_opts[ctx.guild.id].Music._play(ctx,args,True)


@client.command()
async def q(ctx,*args):
    if not ctx.guild.voice_client:
        if not await join(ctx):
            return
    await g_opts[ctx.guild.id].Music._play(ctx,args,True)


@client.command()
async def play(ctx,*args):
    if not ctx.guild.voice_client:
        if not await join(ctx):
            return
    await g_opts[ctx.guild.id].Music._play(ctx,args,False)


@client.command()
async def p(ctx,*args):
    if not ctx.guild.voice_client:
        if not await join(ctx):
            return
    await g_opts[ctx.guild.id].Music._play(ctx,args,False)







############################################################################################
#   Playlist
############################################################################################

@client.command()
async def playlist(ctx,*args):
    if not ctx.guild.voice_client:
        if not await join(ctx):
            return
    await g_opts[ctx.guild.id].Music._playlist(ctx,args)


@client.command()
async def pl(ctx,*args):
    if not ctx.guild.voice_client:
        if not await join(ctx):
            return
    await g_opts[ctx.guild.id].Music._playlist(ctx,args)










class DataInfo():
    def __init__(self, guild):
        self.guild = guild
        self.gn = guild.name
        self.gid = guild.id
        self.vc = guild.voice_client
        self.loop = client.loop
        self.client = client
        self.config = config
        self.MA = MultiAudio(guild, client, self)
        self.MA.start()
        self.Music = MusicController(self)



client.run(config.Token)
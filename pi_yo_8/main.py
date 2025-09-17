import discord
import asyncio
import logging
from discord.ext import commands, tasks

from pi_yo_8 import config
from pi_yo_8.type import SendableChannels
from pi_yo_8.gui.controller import EmbedController
from pi_yo_8.voice_client import MultiAudioVoiceClient
from pi_yo_8.music_control.controller import MusicController




_log = logging.getLogger(__name__)




class MyCog(commands.Cog):
    def __init__(self, bot:commands.Bot) -> None:
        self.bot = bot
        self.g_opts:dict[int, 'DataInfo'] = {}

    @discord.app_commands.command(name="download", description='URL or 検索したい文字')
    async def download(self, interaction:discord.Interaction, arg:str): # type: ignore
        await interaction.response.defer(thinking=True)
        if embeds := await MusicController.download(arg):
            for em in embeds:
                await interaction.followup.send(embed=em, ephemeral=True)


    ####  基本的コマンド
    @commands.Cog.listener()
    async def on_ready(self):
        _log.info('Logged in')
        _log.info(self.bot.user.name if self.bot.user else "error")
        _log.info(self.bot.user.id if self.bot.user else -1)
        print('--------------------------')

        activity = discord.Activity(name='華麗なる美声', type=discord.ActivityType.listening)
        await self.bot.change_presence(activity=activity)
    


    @commands.command()
    async def join(self, ctx:commands.Context):
        if ctx.guild and not self.g_opts.get(ctx.guild.id):
            try: 
                if isinstance(ctx.author, discord.Member) and ctx.author.voice and ctx.author.voice.channel:
                    await ctx.author.voice.channel.connect(self_deaf=True)
                    _log.info(f'{ctx.guild.name} : #join')
                    self.g_opts[ctx.guild.id] = DataInfo(ctx.guild, self)
                    return True
            except Exception as e:
                print(e)


    @commands.command()
    async def bye(self, ctx:commands.Context):
        if ctx.guild and (info := self.g_opts.get(ctx.guild.id)):
            await info.bye()

        
    @commands.command()
    async def speed(self, ctx:commands.Context, arg:float):
        if ctx.guild and (data := self.g_opts.get(ctx.guild.id)):
            await data.music.player_track.speed.set(arg)


    @commands.command()
    async def pitch(self, ctx:commands.Context, arg:int):
        if ctx.guild and (data := self.g_opts.get(ctx.guild.id)):
            await data.music.player_track.pitch.set(arg)


#--------------------------------------------------
# GUI操作
#--------------------------------------------------
    @commands.command()
    async def playing(self, ctx:commands.Context):
        if ctx.guild and (info := self.g_opts.get(ctx.guild.id)):
            if isinstance(ctx.channel, SendableChannels):
                info.embed.lastest_action_ch = ctx.channel
            await info.embed.generate_main_display()



#---------------------------------------------------------------------------------------------------
#   Skip
#---------------------------------------------------------------------------------------------------
    @commands.command(aliases=['s'])
    async def skip(self, ctx:commands.Context, arg:str | None):
        if ctx.guild:
            try:
                await self.g_opts[ctx.guild.id].music.skip(arg)
            except KeyError:pass


#---------------------------------------------------------------------------------------
#   Download
#---------------------------------------------------------------------------------------
    @commands.command(aliases=['dl'])
    async def download(self, ctx:commands.Context, arg):
        if embeds := await MusicController.download(arg):
            for em in embeds:
                await ctx.send(embed=em)



##############################################################################
# Play & Queue
##############################################################################

    @commands.command(aliases=['q'])
    async def queue(self, ctx:commands.Context, *args):
        if ctx.guild:
            await self.join(ctx)
            if self.g_opts.get(ctx.guild.id):
                await self.g_opts[ctx.guild.id].music.def_queue(ctx,args)



    @commands.command(aliases=['p','pl'])
    async def play(self, ctx:commands.Context, *args):
        if ctx.guild:
            await self.join(ctx)
            if self.g_opts.get(ctx.guild.id):
                await self.g_opts[ctx.guild.id].music.play(ctx,args)








class DataInfo():
    def __init__(self, guild:discord.Guild, cog:MyCog):
        if isinstance(guild.voice_client, discord.VoiceClient):
            self.vc:discord.VoiceClient = guild.voice_client
        else:
            _log.error("vcがVoiceClientじゃない")
            asyncio.get_event_loop().create_task(self.bye())
        self.guild = guild
        self.bot = cog.bot
        self.g_opts = cog.g_opts
        self.client_user_id = self.bot.user.id if self.bot.user else -1
        self.MA = MultiAudioVoiceClient(guild, self)
        self.music = MusicController(self)
        self.embed = EmbedController(self)
        self.loop_5.start()
            


    async def bye(self, text:str='切断'):
        asyncio.get_event_loop().create_task(self._bye(text))
        self.loop_5.stop()


    async def _bye(self, text:str):
        self.MA.kill()
        del self.g_opts[self.guild.id]

        _log.info(f'{self.guild.name} : #{text}')
        await asyncio.sleep(0.02)
        try: await self.vc.disconnect()
        except Exception: pass

        while self.loop_5.is_running():
            await asyncio.sleep(1)
        if message := self.embed.main_display:
            await message.delete()
        if message := self.embed.options_display:
            await message.delete()


    @tasks.loop(seconds=5.0)
    async def loop_5(self):
        if not self.guild.id in self.g_opts:
            return

        # 強制切断検知
        mems = self.vc.channel.members
        if not self.client_user_id in [_.id for _ in mems]:
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
import discord
import asyncio
import logging
from discord.ext import commands, tasks

from pi_yo_8.patch import patch
from pi_yo_8.type import SendableChannels
from pi_yo_8.gui.controller import EmbedController
from pi_yo_8.voice_client import MultiTrackVoiceClient
from pi_yo_8.music_control.controller import MusicController
from pi_yo_8.yt_dlp.status_manager import YTDLPStatusManager



patch()
_log = logging.getLogger(__name__)




class MusicBotCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.guild_sessions: dict[int, 'GuildSession'] = {}


    @discord.app_commands.command(name="download", description='URL or 検索したい文字')
    async def download_command(self, interaction: discord.Interaction, query: str):
        task = asyncio.create_task(MusicController.download(query))
        await interaction.response.defer(thinking=True)
        if embed_list := await task:
            for embed in embed_list:
                await interaction.followup.send(embed=embed, ephemeral=True)


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
    async def join(self, ctx: commands.Context):
        if ctx.guild and not self.guild_sessions.get(ctx.guild.id):
            try: 
                if isinstance(ctx.author, discord.Member) and ctx.author.voice and ctx.author.voice.channel:
                    await ctx.author.voice.channel.connect(self_deaf=True)
                    _log.info(f'{ctx.guild.name} : #join')
                    self.guild_sessions[ctx.guild.id] = GuildSession(ctx.guild, self)
                    return True
            except Exception:
                _log.exception(f"func:join guild:{ctx.guild.name}")


    @commands.command()
    async def bye(self, ctx: commands.Context):
        if ctx.guild and (guild_session := self.guild_sessions.get(ctx.guild.id)):
            await guild_session.bye()

        
    @commands.command()
    async def speed(self, ctx: commands.Context, speed_value: float):
        if ctx.guild and (guild_session := self.guild_sessions.get(ctx.guild.id)):
            await guild_session.music.player_track.speed.set(speed_value)


    @commands.command()
    async def pitch(self, ctx: commands.Context, pitch_value: int):
        if ctx.guild and (guild_session := self.guild_sessions.get(ctx.guild.id)):
            await guild_session.music.player_track.pitch.set(pitch_value)


    @commands.command()
    async def playing(self, ctx: commands.Context):
        if ctx.guild and (guild_session := self.guild_sessions.get(ctx.guild.id)):
            if isinstance(ctx.channel, SendableChannels):
                guild_session.embed.record_channel_activity(ctx.channel)
            await guild_session.embed.build_main_embed()


#---------------------------------------------------------------------------------------------------
#   Skip
#---------------------------------------------------------------------------------------------------
    @commands.command(aliases=['s'])
    async def skip(self, ctx: commands.Context, skip_input: str | None):
        if ctx.guild and (guild_session := self.guild_sessions.get(ctx.guild.id)):
            guild_session.embed.record_channel_activity(ctx.channel if isinstance(ctx.channel, SendableChannels) else None)
            await guild_session.music.seek_or_skip(skip_input)


#---------------------------------------------------------------------------------------
#   Download
#---------------------------------------------------------------------------------------
    @commands.command(aliases=['dl'])
    async def download(self, ctx: commands.Context, query: str):
        if embed_list := await MusicController.download(query):
            for embed in embed_list:
                await ctx.send(embed=embed)



##############################################################################
# Play & Queue
##############################################################################

    @commands.command(aliases=['q'])
    async def queue(self, ctx: commands.Context, *args):
        if ctx.guild:
            await self.join(ctx)
            if guild_session := self.guild_sessions.get(ctx.guild.id):
                guild_session.embed.record_channel_activity(ctx.channel if isinstance(ctx.channel, SendableChannels) else None)
                await guild_session.music.enqueue(ctx, args)



    @commands.command(aliases=['p', 'pl'])
    async def play(self, ctx: commands.Context, *args):
        if ctx.guild:
            await self.join(ctx)
            if guild_session := self.guild_sessions.get(ctx.guild.id):
                guild_session.embed.record_channel_activity(ctx.channel if isinstance(ctx.channel, SendableChannels) else None)
                await guild_session.music.play(ctx, args)








class GuildSession:
    """
    Guildごとの接続セッション・音楽コントローラー・UI表示・タスク状態を管理するクラス
    """
    def __init__(self, guild: discord.Guild, cog: MusicBotCog):
        if isinstance(guild.voice_client, discord.VoiceClient):
            self.vc: discord.VoiceClient = guild.voice_client
        else:
            _log.error("VoiceClientが見つからないか無効です")
            asyncio.create_task(self.bye())

        self.guild = guild
        self.bot = cog.bot
        self.guild_sessions = cog.guild_sessions
        self.client_user_id = self.bot.user.id if self.bot.user else -1
        self.empty_channel_loop_count = 0

        self.multi_track_voice_client = MultiTrackVoiceClient(guild, self) # type: ignore
        self.music = MusicController(self) # type: ignore
        self.embed = EmbedController(self) # type: ignore
        self.ytdlp_status_managers: list[YTDLPStatusManager] = []
        self.inactivity_check_loop.start()


    async def bye(self, text: str = '切断'):
        asyncio.create_task(self._bye(text))
        self.inactivity_check_loop.stop()

    async def _bye(self, text: str):
        self.multi_track_voice_client.kill()
        if self.guild.id in self.guild_sessions:
            del self.guild_sessions[self.guild.id]

        _log.info(f'{self.guild.name} : #{text}')
        await asyncio.sleep(0.02)
        try:
            await self.vc.disconnect()
        except Exception:
            pass

        while self.inactivity_check_loop.is_running():
            await asyncio.sleep(1)

        if message := self.embed.main_display:
            try:
                await message.delete()
            except Exception:
                pass

        if message := self.embed.options_display:
            try:
                await message.delete()
            except Exception:
                pass

    @tasks.loop(seconds=5.0)
    async def inactivity_check_loop(self):
        if self.guild.id not in self.guild_sessions:
            return

        # 強制切断検知
        if not self.vc.channel:
            await self.bye('チャンネル未存在のため切断')
            return

        channel_members = self.vc.channel.members
        if self.client_user_id not in [member.id for member in channel_members]:
            await self.bye('強制切断検知')

        # voice channelにBot以外誰もいなくなったことを確認
        elif not any(not member.bot for member in channel_members):
            self.empty_channel_loop_count += 1
            if self.empty_channel_loop_count >= 2:
                await self.bye('誰もいなくなったため切断')

        else:
            self.empty_channel_loop_count = 0

        # Embedの自動更新タスク
        await self.embed.task_loop()
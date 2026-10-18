import asyncio
import logging
import discord
from discord.ext import commands
from pi_yo_8.services.download_service import DownloadService
from pi_yo_8.services.session import GuildSession
from pi_yo_8.type import SendableChannels

_log = logging.getLogger(__name__)

class MusicBotCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.guild_sessions: dict[int, GuildSession] = {}

    def _remove_session(self, guild_id: int) -> None:
        self.guild_sessions.pop(guild_id, None)

    @discord.app_commands.command(name="download", description='URL or 検索したい文字')
    async def download_command(self, interaction: discord.Interaction, query: str):
        task = asyncio.create_task(DownloadService.create_download_embeds(query))
        await interaction.response.defer(thinking=True)
        if embed_list := await task:
            for embed in embed_list:
                await interaction.followup.send(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_ready(self):
        _log.info('Logged in')
        _log.info(self.bot.user.name if self.bot.user else "error")
        _log.info(self.bot.user.id if self.bot.user else -1)
        print('--------------------------')
        activity = discord.Activity(name='華麗なる美声', type=discord.ActivityType.listening)
        await self.bot.change_presence(activity=activity)

    @commands.command()
    async def join(self, ctx: commands.Context) -> bool:
        if ctx.guild and ctx.guild.id not in self.guild_sessions:
            try:
                if isinstance(ctx.author, discord.Member) and ctx.author.voice and ctx.author.voice.channel:
                    await ctx.author.voice.channel.connect(self_deaf=True)
                    _log.info(f"{ctx.guild.name} : #join")
                    self.guild_sessions[ctx.guild.id] = GuildSession(
                        ctx.guild, self.bot, on_destroy=self._remove_session
                    )
                    return True
            except Exception:
                _log.exception(f"func:join guild:{ctx.guild.name}")
        return False

    @commands.command()
    async def bye(self, ctx: commands.Context):
        if ctx.guild and (session := self.guild_sessions.get(ctx.guild.id)):
            await session.bye()

    @commands.command()
    async def speed(self, ctx: commands.Context, speed_value: float):
        if ctx.guild and (session := self.guild_sessions.get(ctx.guild.id)):
            await session.music.player_track.speed.set(speed_value)

    @commands.command()
    async def pitch(self, ctx: commands.Context, pitch_value: int):
        if ctx.guild and (session := self.guild_sessions.get(ctx.guild.id)):
            await session.music.player_track.pitch.set(pitch_value)

    @commands.command()
    async def playing(self, ctx: commands.Context):
        if ctx.guild and (session := self.guild_sessions.get(ctx.guild.id)):
            if isinstance(ctx.channel, SendableChannels):
                session.embed.record_channel_activity(ctx.channel)
            await session.embed.build_main_embed()

    @commands.command(aliases=['s'])
    async def skip(self, ctx: commands.Context, skip_input: str | None = None):
        if ctx.guild and (session := self.guild_sessions.get(ctx.guild.id)):
            session.embed.record_channel_activity(ctx.channel if isinstance(ctx.channel, SendableChannels) else None)
            await session.music.seek_or_skip(skip_input)

    @commands.command(aliases=['dl'])
    async def download(self, ctx: commands.Context, *, query: str):
        if embed_list := await DownloadService.create_download_embeds(query):
            for embed in embed_list:
                await ctx.send(embed=embed)

    @commands.command(aliases=['q'])
    async def queue(self, ctx: commands.Context, *args):
        if ctx.guild:
            await self.join(ctx)
            if session := self.guild_sessions.get(ctx.guild.id):
                session.embed.record_channel_activity(ctx.channel if isinstance(ctx.channel, SendableChannels) else None)
                query = ' '.join(args)
                await session.music.enqueue(query)

    @commands.command(aliases=['p', 'pl'])
    async def play(self, ctx: commands.Context, *args):
        if ctx.guild:
            await self.join(ctx)
            if session := self.guild_sessions.get(ctx.guild.id):
                session.embed.record_channel_activity(ctx.channel if isinstance(ctx.channel, SendableChannels) else None)
                query = ' '.join(args)
                await session.music.play(query)
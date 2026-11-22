import asyncio
import logging

import discord
from discord.ext import commands

from pi_yo_8.core.config import guild_configs
from pi_yo_8.core.types import SENDABLE_CHANNEL_TYPES
from pi_yo_8.gui.utils import EmbedTemplates
from pi_yo_8.services.download_service import DownloadService
from pi_yo_8.services.session import GuildSession

_log = logging.getLogger(__name__)


class MusicBotCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.guild_sessions: dict[int, GuildSession] = {}
        self._empty_vc_tasks: dict[int, asyncio.Task[None]] = {}

    async def cog_unload(self) -> None:
        for task in list(self._empty_vc_tasks.values()):
            if not task.done():
                task.cancel()
        self._empty_vc_tasks.clear()

        if self.guild_sessions:
            await asyncio.gather(
                *(
                    session.bye(text="bot_shutdown", wait=True)
                    for session in list(self.guild_sessions.values())
                ),
                return_exceptions=True,
            )

    def _remove_session(self, guild_id: int) -> None:
        self.guild_sessions.pop(guild_id, None)
        self._cancel_empty_timer(guild_id)

    def _cancel_empty_timer(self, guild_id: int) -> None:
        task = self._empty_vc_tasks.pop(guild_id, None)
        if task and not task.done():
            task.cancel()

    def _schedule_empty_disconnect(self, guild: discord.Guild, delay: float | None = None) -> None:
        self._cancel_empty_timer(guild.id)
        if delay is None:
            delay = guild_configs.get(guild.id).data.empty_disconnect_delay

        async def _auto_disconnect() -> None:
            try:
                await asyncio.sleep(delay)
                session = self.guild_sessions.get(guild.id)
                if not session or not session.vc or not session.vc.channel:
                    return
                if not any(not m.bot for m in session.vc.channel.members):
                    _log.info("VCが空になったため自動切断します: %s", guild.name)
                    await session.bye(text="empty_vc")
            except asyncio.CancelledError:
                pass
            finally:
                self._empty_vc_tasks.pop(guild.id, None)

        self._empty_vc_tasks[guild.id] = self.bot.loop.create_task(_auto_disconnect())

    async def _ensure_joined(self, ctx: commands.Context) -> tuple[bool, str | None]:
        """VC未接続なら接続を試み、(成功したか, 失敗理由メッセージ) を返す"""
        if not ctx.guild:
            return False, "サーバー内でのみ実行できます。"
        if ctx.guild.id in self.guild_sessions:
            return True, None
        if not isinstance(ctx.author, discord.Member) or not ctx.author.voice or not ctx.author.voice.channel:
            return False, "先にボイスチャンネルへ参加してください。"
        try:
            await ctx.author.voice.channel.connect(self_deaf=True)
            _log.info(f"{ctx.guild.name} : #join")
            self.guild_sessions[ctx.guild.id] = GuildSession(
                ctx.guild, self.bot, on_destroy=self._remove_session
            )
            return True, None
        except Exception as e:
            _log.exception(f"func:join guild:{ctx.guild.name}")
            return False, str(e)

    @discord.app_commands.command(name="download", description='URL or 検索したい文字')
    async def download_command(self, interaction: discord.Interaction, query: str) -> None:
        task = asyncio.create_task(DownloadService.create_download_embeds(query))
        await interaction.response.defer(thinking=True)
        if embed_list := await task:
            for embed in embed_list:
                await interaction.followup.send(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        _log.info('Logged in')
        _log.info(self.bot.user.name if self.bot.user else "error")
        _log.info(self.bot.user.id if self.bot.user else -1)
        activity = discord.Activity(name='華麗なる美声', type=discord.ActivityType.listening)
        await self.bot.change_presence(activity=activity)

    @commands.command()
    async def join(self, ctx: commands.Context) -> bool:
        joined, err = await self._ensure_joined(ctx)
        if not joined:
            await ctx.reply(embed=EmbedTemplates.create_failure_embed("VCに接続できませんでした", err or ""))
            return False
        return True

    @commands.command()
    async def bye(self, ctx: commands.Context) -> None:
        if not ctx.guild:
            return
        if session := self.guild_sessions.get(ctx.guild.id):
            await session.bye()
        else:
            await ctx.reply(embed=EmbedTemplates.create_failure_embed("VCに接続していません"))

    @commands.command()
    async def speed(self, ctx: commands.Context, speed_value: float) -> None:
        if ctx.guild and (session := self.guild_sessions.get(ctx.guild.id)):
            await session.music.player_track.speed.set(speed_value)

    @commands.command()
    async def pitch(self, ctx: commands.Context, pitch_value: int) -> None:
        if ctx.guild and (session := self.guild_sessions.get(ctx.guild.id)):
            await session.music.player_track.pitch.set(pitch_value)

    @commands.command()
    async def playing(self, ctx: commands.Context) -> None:
        if ctx.guild and (session := self.guild_sessions.get(ctx.guild.id)):
            if isinstance(ctx.channel, SENDABLE_CHANNEL_TYPES):
                session.embed.record_channel_activity(ctx.channel)
            await session.embed.build_main_embed()

    @commands.command(aliases=['s'])
    async def skip(self, ctx: commands.Context, skip_input: str | None = None) -> None:
        if ctx.guild and (session := self.guild_sessions.get(ctx.guild.id)):
            session.embed.record_channel_activity(ctx.channel if isinstance(ctx.channel, SENDABLE_CHANNEL_TYPES) else None)
            await session.music.seek_or_skip(skip_input)

    @commands.command(aliases=['dl'])
    async def download(self, ctx: commands.Context, *, query: str) -> None:
        if embed_list := await DownloadService.create_download_embeds(query):
            for embed in embed_list:
                await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.CommandNotFound):
            return
        _log.error(f"Command '{ctx.command or ctx.message.content}' failed: {error}", exc_info=error)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        guild = member.guild
        session = self.guild_sessions.get(guild.id)

        if self.bot.user and member.id == self.bot.user.id:
            if before.channel and not after.channel and session:
                await session.bye(text="forced_disconnect")
            return

        if not session or not session.vc or not session.vc.channel:
            return

        bot_channel = session.vc.channel
        if before.channel != bot_channel and after.channel != bot_channel:
            return

        has_humans = any(not m.bot for m in bot_channel.members)
        if not has_humans:
            self._schedule_empty_disconnect(guild)
        else:
            self._cancel_empty_timer(guild.id)

    @commands.command(aliases=['q'])
    async def queue(self, ctx: commands.Context, *, query: str = "") -> None:
        if ctx.guild:
            if not await self.join(ctx):
                return
            if session := self.guild_sessions.get(ctx.guild.id):
                session.embed.record_channel_activity(ctx.channel if isinstance(ctx.channel, SENDABLE_CHANNEL_TYPES) else None)
                await session.music.enqueue(query)

    @commands.command(aliases=['p', 'pl'])
    async def play(self, ctx: commands.Context, *, query: str = "") -> None:
        if ctx.guild:
            if not await self.join(ctx):
                return
            if session := self.guild_sessions.get(ctx.guild.id):
                session.embed.record_channel_activity(ctx.channel if isinstance(ctx.channel, SENDABLE_CHANNEL_TYPES) else None)
                await session.music.play(query)

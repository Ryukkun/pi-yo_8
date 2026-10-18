import asyncio
import logging
from typing import Any

import discord
from discord.ext import tasks

from pi_yo_8.core.playlist import Playlist
from pi_yo_8.core.snapshot import PlaybackSnapshot, StatusSnapshot, TrackSnapshot
from pi_yo_8.engine.mixer import MultiTrackVoiceClient
from pi_yo_8.gui.controller import EmbedController
from pi_yo_8.services.player_service import PlayerService
from pi_yo_8.sources.status import StatusManager

_log = logging.getLogger(__name__)

class GuildSession:
    """
    Guildごとの接続セッション・音楽コントローラー・UI表示・タスク状態を管理するクラス
    """
    def __init__(self, guild: discord.Guild, bot: discord.Client, on_destroy: Any = None):
        if not isinstance(guild.voice_client, discord.VoiceClient):
            raise ValueError(f"Invalid voice client for guild {guild.name}")

        self.vc: discord.VoiceClient = guild.voice_client
        self.guild = guild
        self.bot = bot
        self.on_destroy = on_destroy
        self.client_user_id = bot.user.id if bot.user else -1
        self.empty_channel_loop_count = 0
        self.ytdlp_status_managers: list[StatusManager] = []

        self.multi_track_voice_client = MultiTrackVoiceClient(guild, self.vc, bot.loop)
        player_track = self.multi_track_voice_client.add_track(opus_mode=True)

        self.embed = EmbedController(self)
        self.music = PlayerService(
            guild.name,
            player_track,
            on_status_report=self.register_status_manager,
            on_track_change=self._on_track_change,
        )
        self.inactivity_check_loop.start()

    def _on_track_change(self) -> None:
        asyncio.create_task(self.embed.refresh_main_display())

    def get_snapshot(self) -> PlaybackSnapshot:
        track = self.music.player_track.track
        track_snap = None
        if track:
            track_snap = TrackSnapshot(
                title=track.title,
                web_url=track.web_url,
                duration=track.duration,
                thumbnail_url=track.thumbnail_url,
                uploader=track.uploader,
                uploader_url=track.uploader_url,
                view_count=track.view_count,
                upload_date=track.upload_date,
            )

        raw_head = self.music.queue.get_current_raw()
        pl_title = None
        pl_url = None
        if isinstance(raw_head, Playlist):
            pl_title = raw_head.title
            pl_url = raw_head.url

        status_snaps: list[StatusSnapshot] = []
        for sm in self.ytdlp_status_managers:
            recent_errs = [e.description for e in sm.get_errors(seconds_ago=20)]
            if sm.is_running or recent_errs:
                status_snaps.append(
                    StatusSnapshot(
                        name=sm.name,
                        url=sm.url,
                        type_name=sm._type.name,
                        is_running=sm.is_running,
                        recent_errors=recent_errs,
                    )
                )

        return PlaybackSnapshot(
            track=track_snap,
            timer=self.music.player_track.timer,
            duration=track.duration if track else None,
            is_paused=self.music.player_track.is_paused(),
            has_audio_data=self.music.player_track.has_audio_data(),
            is_playing_playlist=self.music.queue.is_playing_playlist(),
            playlist_title=pl_title,
            playlist_url=pl_url,
            loop=self.music.status.loop,
            loop_pl=self.music.status.loop_pl,
            random_pl=self.music.status.random_pl,
            speed=self.music.player_track.speed.get(),
            pitch=self.music.player_track.pitch.get(),
            statuses=status_snaps,
        )

    def register_status_manager(self, sm: StatusManager) -> None:
        self.ytdlp_status_managers.append(sm)
        try:
            loop = asyncio.get_running_loop()
            loop.call_later(30, lambda: self.ytdlp_status_managers.remove(sm) if sm in self.ytdlp_status_managers else None)
        except RuntimeError:
            pass

    async def bye(self, text: str = '切断') -> None:
        asyncio.create_task(self._bye(text))
        self.inactivity_check_loop.stop()

    async def _bye(self, text: str) -> None:
        self.multi_track_voice_client.kill()
        if self.on_destroy:
            self.on_destroy(self.guild.id)

        _log.info(f"{self.guild.name} : #{text}")
        await asyncio.sleep(0.02)
        try:
            await self.vc.disconnect()
        except Exception:
            pass

        while self.inactivity_check_loop.is_running():
            await asyncio.sleep(0.5)

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
    async def inactivity_check_loop(self) -> None:
        if not self.vc.channel:
            await self.bye('チャンネル未存在のため切断')
            return

        channel_members = self.vc.channel.members
        if self.client_user_id not in [m.id for m in channel_members]:
            await self.bye('強制切断検知')
        elif not any(not m.bot for m in channel_members):
            self.empty_channel_loop_count += 1
            if self.empty_channel_loop_count >= 2:
                await self.bye('誰もいなくなったため切断')
        else:
            self.empty_channel_loop_count = 0

        await self.embed.task_loop()

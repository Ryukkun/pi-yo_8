import logging
import time
from typing import TYPE_CHECKING, Any
from discord import ActionRow, Button, Embed, Message, NotFound, SelectMenu
from pi_yo_8.core.snapshot import PlaybackSnapshot
from pi_yo_8.core.url import UrlAnalyzer
from pi_yo_8.core.types import SendableChannels
from pi_yo_8.gui.utils import (
    EmbedTemplates,
    calculate_days_ago_text,
    format_large_number,
    format_seconds_to_time,
)
from pi_yo_8.gui.view import PlayerControlsView, send_play_option_message


if TYPE_CHECKING:
    from pi_yo_8.services.session import GuildSession

_log = logging.getLogger(__name__)

class EmbedController:
    def __init__(self, guild_session: "GuildSession") -> None:
        self.guild_session = guild_session
        self.latest_action_time = 0.0
        self.latest_action_channel: SendableChannels | None = None
        self.main_display: Message | None = None
        self.options_display: Message | None = None

    def record_channel_activity(self, channel: Any | None = None) -> None:
        self.latest_action_time = time.time()
        if isinstance(channel, SendableChannels):
            self.latest_action_channel = channel

    async def create_and_send_main_display(self) -> None:
        try:
            if self.latest_action_channel:
                embed = await self.build_main_embed()
                play_option = False
                if self.main_display:
                    try:
                        await self.main_display.delete()
                        if self.options_display:
                            await self.options_display.delete()
                            play_option = True
                    except NotFound:
                        pass

                self.main_display = await self.latest_action_channel.send(
                    embed=embed, view=PlayerControlsView(self.guild_session)
                )
                self.options_display = (
                    await send_play_option_message(self.latest_action_channel, self.guild_session)
                    if play_option
                    else None
                )
        except Exception:
            _log.info(f"Embed.create_and_send_main_display - {self.guild_session.guild.name}", exc_info=True)

    async def refresh_main_display(self) -> None:
        if not self.latest_action_channel:
            return

        if last_message := self.latest_action_channel.last_message:
            if self.guild_session.bot.user and self.guild_session.bot.user.id == last_message.author.id:
                if last_message.embeds:
                    if embed_color := last_message.embeds[0].colour:
                        if embed_color.value == EmbedTemplates.get_persistent_color().value and self.main_display:
                            if await self._update_main_display(self.main_display):
                                return

                        if embed_color.value == EmbedTemplates.get_player_color().value:
                            if await self._update_main_display(last_message):
                                return
        await self.create_and_send_main_display()

    async def _update_main_display(self, target_message: Message) -> bool:
        embed = await self.build_main_embed()
        view = PlayerControlsView(self.guild_session)
        change_view = False
        components = target_message.components

        if len(components) >= 3:
            if isinstance(components[0], ActionRow) and components[0].children and isinstance(components[0].children[0], SelectMenu):
                old_select = components[0].children[0]
                if [opt.to_dict() for opt in view.select_opt] != [opt.to_dict() for opt in old_select.options]:
                    change_view = True

            if isinstance(components[2], ActionRow) and len(components[2].children) >= 3 and isinstance(components[2].children[2], Button):
                old_pause_play = components[2].children[2]
                if view.pause_play.label != old_pause_play.label:
                    change_view = True

        try:
            if change_view:
                await target_message.edit(embed=embed, view=view)
            else:
                # API節約: Embed内容に変化がなければ送信をスキップ
                if target_message.embeds and target_message.embeds[0].to_dict() == embed.to_dict():
                    return True
                await target_message.edit(embed=embed)
            return True
        except NotFound:
            return False

    async def build_main_embed(self) -> Embed:
        snap = self.guild_session.get_snapshot()
        return self.render_embed_from_snapshot(snap)

    def render_embed_from_snapshot(self, snap: PlaybackSnapshot) -> Embed:
        if snap.track:
            embed = Embed(title=snap.track.title, url=snap.track.web_url, colour=EmbedTemplates.get_player_color())
            if snap.track.thumbnail_url:
                embed.set_thumbnail(url=snap.track.thumbnail_url)
            if snap.track.uploader:
                embed.set_author(name=snap.track.uploader, url=snap.track.uploader_url or None)

            descriptions = []
            if snap.track.view_count:
                descriptions.append(f'{format_large_number(snap.track.view_count)} 回再生')
            if snap.track.upload_date:
                descriptions.append(calculate_days_ago_text(snap.track.upload_date))
                descriptions.append(snap.track.upload_date)
            if descriptions:
                embed.description = '　'.join(descriptions) + "\n\u200B"

            if snap.is_playing_playlist and snap.playlist_title:
                playlist_title = snap.playlist_title
                playlist_url = snap.playlist_url or ""
                embed.add_field(
                    name="Playlist",
                    value=f"[{playlist_title}]({playlist_url})" if UrlAnalyzer(playlist_url).is_url else playlist_title,
                    inline=True,
                )
        else:
            embed = Embed(title='`_(:3」∠)_`', colour=EmbedTemplates.get_player_color())

        extracting_infos: list[str] = []
        for status in snap.statuses:
            if status.is_running:
                display_name = f"[{status.name}]({status.url})" if UrlAnalyzer(status.url).is_url else status.name
                type_name = status.type_name
                extracting_infos.append(f"{type_name}:{display_name}" if display_name else type_name)

        if extracting_infos:
            embed.add_field(name="解析中...", value="\n".join(extracting_infos), inline=True)

        if snap.track and snap.duration:
            bar_length = 28
            play_time = int(snap.timer)
            unit_time = snap.duration / bar_length
            progress_bar = ''
            progress_blocks = [' ', '▏', '▎', '▍', '▌', '▋', '▋', '▊', '▉', '█']
            for step in range(bar_length):
                time_offset = step * unit_time
                if time_offset <= play_time < (time_offset + unit_time):
                    level = int((play_time - time_offset) / unit_time * 9)
                    progress_bar += progress_blocks[min(level, 9)]
                elif time_offset <= play_time:
                    progress_bar += '█'
                else:
                    progress_bar += ' '
            formatted_play_time = format_seconds_to_time(play_time)
            formatted_duration = format_seconds_to_time(snap.duration)
            embed.add_field(
                name="\u200B",
                value=f'` {formatted_play_time} | {progress_bar} | {formatted_duration} `',
                inline=False,
            )

        for status in snap.statuses:
            if status.recent_errors:
                display_name = f"[{status.name}]({status.url})" if UrlAnalyzer(status.url).is_url else status.name
                name = f"{status.type_name}:{display_name}" if display_name else status.type_name
                embed.add_field(name=name, value="```" + "\n".join(status.recent_errors) + "```")

        return embed

    async def task_loop(self) -> None:
        try:
            now = time.time()
            snap = self.guild_session.get_snapshot()

            has_active_extraction = any(s.is_running for s in snap.statuses)
            is_active_playback = snap.has_audio_data and not snap.is_paused

            # 再生中でも解析中でもなければ定期編集しない（Discord API節約）
            if not is_active_playback and not has_active_extraction:
                return

            delay = now - self.latest_action_time
            # レートリミット回避: 5秒ごとの過剰なeditを緩和
            if delay < 30:
                if int(now) % 10 < 5:
                    await self.refresh_main_display()
            elif delay < 300:
                if int(now) % 15 < 5:
                    await self.refresh_main_display()
            else:
                if int(now) % 30 < 5:
                    await self.refresh_main_display()
        except Exception:
            _log.info(f"EmbedController.task_loop - {self.guild_session.guild.name}", exc_info=True)
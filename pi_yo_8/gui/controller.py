import logging
import time
from typing import TYPE_CHECKING, Any
from discord import ActionRow, Button, Embed, Message, NotFound, SelectMenu
from pi_yo_8.core.playlist import Playlist
from pi_yo_8.core.track import Track
from pi_yo_8.core.url import UrlAnalyzer
from pi_yo_8.gui.utils import (
    EmbedTemplates,
    calculate_days_ago_text,
    format_large_number,
    format_seconds_to_time,
)
from pi_yo_8.gui.view import PlayerControlsView, send_play_option_message
from pi_yo_8.type import SendableChannels

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
                await target_message.edit(embed=embed)
            return True
        except NotFound:
            return False

    async def build_main_embed(self) -> Embed:
        track = self.guild_session.music.player_track.track

        if track and isinstance(track, Track):
            embed = Embed(title=track.title, url=track.web_url, colour=EmbedTemplates.get_player_color())
            if track.thumbnail_url:
                embed.set_thumbnail(url=track.thumbnail_url)
            if track.uploader:
                embed.set_author(name=track.uploader, url=track.uploader_url or None)

            descriptions = []
            if track.view_count:
                descriptions.append(f'{format_large_number(track.view_count)} 回再生')
            if track.upload_date:
                descriptions.append(calculate_days_ago_text(track.upload_date))
                descriptions.append(track.upload_date)
            if descriptions:
                embed.description = '　'.join(descriptions) + "\n\u200B"

            # プレイリスト情報表示
            raw_queue_head = self.guild_session.music.queue.get_current_raw()
            if isinstance(raw_queue_head, Playlist):
                playlist_title = raw_queue_head.title
                playlist_url = raw_queue_head.url
                embed.add_field(
                    name="Playlist",
                    value=f"[{playlist_title}]({playlist_url})" if UrlAnalyzer(playlist_url).is_url else playlist_title,
                    inline=True,
                )
        else:
            embed = Embed(title='`_(:3」∠)_`', colour=EmbedTemplates.get_player_color())

        extracting_infos: list[str] = []
        for status_manager in self.guild_session.ytdlp_status_managers:
            if status_manager.is_running:
                display_name = f"[{status_manager.name}]({status_manager.url})" if UrlAnalyzer(status_manager.url).is_url else status_manager.name
                type_name = status_manager._type.name
                extracting_infos.append(f"{type_name}:{display_name}" if display_name else type_name)

        if extracting_infos:
            embed.add_field(name="解析中...", value="\n".join(extracting_infos), inline=True)

        if track and track.duration:
            bar_length = 28
            play_time = int(self.guild_session.music.player_track.timer)
            unit_time = track.duration / bar_length
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
            formatted_duration = format_seconds_to_time(track.duration)
            embed.add_field(
                name="\u200B",
                value=f'` {formatted_play_time} | {progress_bar} | {formatted_duration} `',
                inline=False,
            )

        for status_manager in self.guild_session.ytdlp_status_managers:
            if errors := status_manager.get_errors(seconds_ago=20):
                display_name = f"[{status_manager.name}]({status_manager.url})" if UrlAnalyzer(status_manager.url).is_url else status_manager.name
                name = f"{status_manager._type.name}:{display_name}" if display_name else status_manager._type.name
                embed.add_field(name=name, value="```" + "\n".join(e.description for e in errors) + "```")

        return embed

    async def task_loop(self) -> None:
        try:
            now = time.time()
            delay = now - self.latest_action_time
            if delay < 30:
                await self.refresh_main_display()
            elif delay < 300:
                if 0 <= (now % 10) < 5:
                    await self.refresh_main_display()
            else:
                if 0 <= (now % 20) < 5:
                    await self.refresh_main_display()
        except Exception:
            _log.info(f"EmbedController.task_loop - {self.guild_session.guild.name}", exc_info=True)
import logging
import time
from typing import TYPE_CHECKING, Any
from discord import ActionRow, Button, Embed, Message, NotFound, SelectMenu

from pi_yo_8.music_control.playlist import Playlist
from pi_yo_8.type import SendableChannels
from pi_yo_8.utils import UrlAnalyzer, run_check_storage
from pi_yo_8.gui.view import PlayerControlsView, send_play_option_message
from pi_yo_8.gui.utils import EmbedTemplates, format_large_number, calculate_days_ago_text, format_seconds_to_time
from pi_yo_8.yt_dlp.audio_data import YTDLPAudioData

if TYPE_CHECKING:
    from pi_yo_8.main import GuildSession


_log = logging.getLogger(__name__)



class EmbedController:
    def __init__(self, guild_session: "GuildSession") -> None:
        self.guild_session = guild_session
        self.latest_action_time = 0.0
        self.latest_action_channel: SendableChannels | None = None  # 最新のチャンネル
        self.main_display: Message | None = None  # 再生中のEmbed
        self.options_display: Message | None = None  # 再生中のオプションEmbed


    def record_channel_activity(self, channel: Any | None = None):
        self.latest_action_time = time.time()
        if isinstance(channel, SendableChannels):
            self.latest_action_channel = channel


    @run_check_storage()
    async def create_and_send_main_display(self):
        try:
            if self.latest_action_channel:
                # Get Embed
                embed = await self.build_main_embed()
                play_option = False
                # 古いEmbedを削除
                if self.main_display:
                    try:
                        await self.main_display.delete()
                        if self.options_display:
                            await self.options_display.delete()
                            play_option = True
                    except NotFound: pass

                # 新しいEmbed
                self.main_display = await self.latest_action_channel.send(embed=embed, view=PlayerControlsView(self.guild_session))
                self.options_display = await send_play_option_message(self.latest_action_channel, self.guild_session) if play_option else None

        except Exception as e:
            _log.info(f"Embed.create_and_send_main_display - {self.guild_session.guild.name}", exc_info=True)


    async def refresh_main_display(self):
        if self.create_and_send_main_display.is_running: return
        if not self.latest_action_channel: return

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


    async def _update_main_display(self, target_message: Message):
        embed = await self.build_main_embed()

        # viewを変更する必要があるか
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
            # メッセージが見つからなかったら 新しく作成
            print('見つかりませんでした！')


    async def build_main_embed(self):
        raw_audio = self.guild_session.music.player_track.audio_data
        audio_data = raw_audio if isinstance(raw_audio, YTDLPAudioData) else None

        if audio_data:
            embed = Embed(title=audio_data.title(), url=audio_data.web_url(), colour=EmbedTemplates.get_player_color())
            if audio_data.thumbnail:
                embed.set_thumbnail(url=audio_data.thumbnail)
            embed.set_author(name=audio_data.ch_name(), url=audio_data.ch_url(), icon_url=audio_data.ch_icon)
            descriptions = []
            if (view_count := audio_data.view_count()):
                descriptions.append(f'{format_large_number(view_count)} 回再生')
            if (upload_date_str := audio_data.upload_date()):
                descriptions.append(calculate_days_ago_text(upload_date_str))
                descriptions.append(upload_date_str)
            if descriptions:
                embed.description = '　'.join(descriptions) + "\n\u200B"

            if isinstance(audio_data.playlist, Playlist):
                playlist = audio_data.playlist
                embed.add_field(name="Playlist",
                                value=f"[{playlist.title}]({playlist.url})" if UrlAnalyzer(playlist.url).is_url else playlist.title,
                                inline=True)

        else:
            embed = Embed(title='`_(:3」∠)_`', colour=EmbedTemplates.get_player_color())


        extracting_infos: list[str] = []
        for status_manager in self.guild_session.ytdlp_status_managers:
            if status_manager.name:
                display_name = f"[{status_manager.name}]({status_manager.url})" if UrlAnalyzer(status_manager.url).is_url else status_manager.name
                name = f"{status_manager._type.name}:{display_name}"
            else:
                name = f"[{status_manager._type.name}]({status_manager.url})" if UrlAnalyzer(status_manager.url).is_url else status_manager._type.name
            if status_manager.is_running:
                extracting_infos.append(name)
        if extracting_infos:
            embed.add_field(name="解析中...", value="\n".join(extracting_infos), inline=True)


        if audio_data and audio_data.duration:
            # Progress Bar
            bar_length = 28
            play_time = int(self.guild_session.music.player_track.timer)
            unit_time = audio_data.duration / bar_length
            progress_bar = ''
            progress_blocks = [' ', '▏', '▎', '▍', '▌', '▋', '▋', '▊', '▉', '█']
            for step in range(bar_length):
                time_offset = step * unit_time
                if time_offset <= play_time < (time_offset + unit_time):
                    level = int((play_time - time_offset) / unit_time * 9)
                    progress_bar += progress_blocks[level]
                elif time_offset <= play_time:
                    progress_bar += '█'
                else:
                    progress_bar += ' '
            formatted_play_time = format_seconds_to_time(play_time)
            formatted_duration = format_seconds_to_time(audio_data.duration)
            embed.add_field(name="\u200B", value=f'` {formatted_play_time} | {progress_bar} | {formatted_duration} `', inline=False)


        for status_manager in self.guild_session.ytdlp_status_managers:
            if errors := status_manager.get_errors(seconds_ago=20):
                if status_manager.name:
                    display_name = f"[{status_manager.name}]({status_manager.url})" if UrlAnalyzer(status_manager.url).is_url else status_manager.name
                    name = f"{status_manager._type.name}:{display_name}"
                else:
                    name = f"[{status_manager._type.name}]({status_manager.url})" if UrlAnalyzer(status_manager.url).is_url else status_manager._type.name

                embed.add_field(name=name, value="```" + "\n".join(map(lambda e: e.description, errors)) + "```")


        return embed
    

    async def task_loop(self):
        '''
        GuildSessionより 5秒おきに実行
        '''
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
        except Exception as e:
            _log.info(f"EmbedController.task_loop - {self.guild_session.guild.name}", exc_info=True)
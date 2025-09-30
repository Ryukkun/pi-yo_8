import logging
import time
from typing import TYPE_CHECKING, Any
from discord import ActionRow, Button, Embed, Message, NotFound, SelectMenu

from pi_yo_8.music_control.playlist import Playlist
from pi_yo_8.type import SendableChannels
from pi_yo_8.utils import UrlAnalyzer, run_check_storage
from pi_yo_8.gui.view import CreateButton, playoptionmessage
from pi_yo_8.gui.utils import EmbedTemplates, int_analysis, date_difference, calc_time
from pi_yo_8.yt_dlp.audio_data import YTDLPAudioData

if TYPE_CHECKING:
    from pi_yo_8.main import DataInfo


_log = logging.getLogger(__name__)



class EmbedController:
    def __init__(self, info: "DataInfo") -> None:
        self.info = info
        self.lastest_action_time = 0.0
        self.lastest_action_ch: SendableChannels | None = None  # 最新のチャンネル
        self.main_display: Message | None = None  # 再生中のEmbed
        self.options_display: Message | None = None  # 再生中のオプションEmbed
        



    def update_action_time(self, channel: Any | None = None):
        self.lastest_action_time = time.time()
        if isinstance(channel, SendableChannels):
            self.lastest_action_ch = channel


    @run_check_storage()
    async def send_new_main_display(self):
        try:
            if self.lastest_action_ch:
                # Get Embed
                embed = await self.generate_main_display()
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
                self.main_display = await self.lastest_action_ch.send(embed=embed,view=CreateButton(self.info))
                self.options_display = await playoptionmessage(self.lastest_action_ch, self.info) if play_option else None

                #print(f"{guild.name} : #再生中の曲　<{g_opts[guild.id]['queue'][0][1]}>")
        except Exception as e:
            _log.info(f"Embed.send_new_main_display - {self.info.guild.name}", exc_info=True)


    async def update_main_display(self):
        if self.send_new_main_display.is_running: return
        if not self.lastest_action_ch: return

        if last_message := self.lastest_action_ch.last_message:
            if self.info.bot.user and self.info.bot.user.id == last_message.author.id:
                if last_message.embeds:
                    if em_color := last_message.embeds[0].colour:
                        if em_color.value == EmbedTemplates.dont_replace_color().value and self.main_display:
                            if await self._update_main_display(self.main_display):
                                return

                        if em_color.value == EmbedTemplates.player_color().value:
                            if await self._update_main_display(last_message):
                                return
        await self.send_new_main_display()


    async def _update_main_display(self, target_message:Message):
        embed = await self.generate_main_display()

        # viewを変更する必要があるか
        view = CreateButton(self.info)
        change_view = False
        coms = target_message.components
        if len(coms) >= 3:
            if isinstance(coms[0], ActionRow) and coms[0].children and isinstance(coms[0].children[0], SelectMenu):
                old_select = coms[0].children[0]
                if [opt.to_dict() for opt in view.select_opt] != [opt.to_dict() for opt in old_select.options]:
                    change_view = True
            
            if isinstance(coms[2], ActionRow) and len(coms[2].children) >= 3 and isinstance(coms[2].children[2], Button):
                old_pause_play = coms[2].children[2]
                if view.pause_play.label != old_pause_play.label:
                    change_view = True
                
        try:
            if change_view:
                await target_message.edit(embed= embed,view=view)
            else:
                await target_message.edit(embed= embed)
            return True
        except NotFound:
            # メッセージが見つからなかったら 新しく作成
            print('見つかりませんでした！')


    async def generate_main_display(self):
        _ = self.info.music.player_track.audio_data
        audio_data = _ if isinstance(_, YTDLPAudioData) else None

        if audio_data:
            embed=Embed(title=audio_data.title(), url=audio_data.web_url(), colour=EmbedTemplates.player_color())
            if audio_data.thumbnail:
                embed.set_thumbnail(url=audio_data.thumbnail)
            embed.set_author(name=audio_data.ch_name(), url=audio_data.ch_url(), icon_url=audio_data.ch_icon)
            descriptions = []
            if (view_count := audio_data.view_count()):
                descriptions.append(f'{int_analysis(view_count)} 回再生')
            if (up_date := audio_data.upload_date()):
                descriptions.append(date_difference(up_date))
                descriptions.append(audio_data.upload_date())
            if descriptions:
                embed.description = '　'.join(descriptions) + "\n\u200B"

            if isinstance(audio_data.playlist, Playlist):
                pl = audio_data.playlist
                embed.add_field(name="Playlist",
                                value=f"[{pl.title}]({pl.url})" if UrlAnalyzer(pl.url).is_url else pl.title,
                                inline=True)
                #embed.add_field(name="Index", value=pl.next_indexes[0] if pl.next_indexes else '? ;w; ?')

        else:
            embed=Embed(title='`_(:3」∠)_`', colour=EmbedTemplates.player_color())


        extracting_infos:list[str] = []
        for status_manager in self.info.ytdlp_status_managers:
            if status_manager.name:
                _name = f"[{status_manager.name}]({status_manager.url})" if UrlAnalyzer(status_manager.url).is_url else status_manager.name
                name = f"{status_manager._type.name}:{_name}"
            else:
                name = f"[{status_manager._type.name}]({status_manager.url})" if UrlAnalyzer(status_manager.url).is_url else status_manager._type.name
            if status_manager.is_running:
                extracting_infos.append(name)
        if extracting_infos:
            embed.add_field(name="解析中...", value="\n".join(extracting_infos), inline=True)


        if audio_data and audio_data.duration:
            # Progress Bar
            i_length = 28
            play_time = int(self.info.music.player_track.timer)
            unit_time = audio_data.duration / i_length
            Progress = ''
            text_list = [' ','▏','▎','▍','▌','▋','▋','▊','▉','█']
            for i in range(i_length):
                i = i * unit_time
                if i <= play_time < (i + unit_time):
                    level = int((play_time - i) / unit_time * 9)
                    Progress += text_list[level]
                elif i <= play_time:
                    Progress += '█'
                else:
                    Progress += ' '
            formatted_play_time = calc_time(play_time)
            formatted_duration = calc_time(audio_data.duration)
            embed.add_field(name="\u200B", value=f'` {formatted_play_time} | {Progress} | {formatted_duration} `', inline=False)


        for status_manager in self.info.ytdlp_status_managers:
            if status_manager.name:
                _name = f"[{status_manager.name}]({status_manager.url})" if UrlAnalyzer(status_manager.url).is_url else status_manager.name
                name = f"{status_manager._type.name}:{_name}"
            else:
                name = f"[{status_manager._type.name}]({status_manager.url})" if UrlAnalyzer(status_manager.url).is_url else status_manager._type.name

            if errors := status_manager.get_errors(seconds_ago=20):
                embed.add_field(name=name, value="```"+"\n".join(map(lambda e: e.description, errors))+"```")


        return embed
    

    async def task_loop(self):
        '''
        Infoより 5秒おきに実行
        '''
        try:
            now = time.time()
            delay = now - self.lastest_action_time
            if delay < 30:
                await self.update_main_display()
            elif delay < 300:
                if 0 <= (now % 10) < 5:
                    await self.update_main_display()
            else:
                if 0 <= (now % 20) < 5:
                    await self.update_main_display()
        except Exception as e:
            _log.info(f"EmbedController.task_loop - {self.info.guild.name}", exc_info=True)
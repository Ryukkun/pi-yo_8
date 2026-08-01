import asyncio
import discord
from typing import TYPE_CHECKING

from discord.interactions import Interaction

from pi_yo_8.gui.utils import EmbedTemplates
from pi_yo_8.type import SendableChannels


if TYPE_CHECKING:
    from pi_yo_8.main import GuildSession
    from pi_yo_8.music_control.controller import MusicQueue
    from pi_yo_8.yt_dlp.audio_data import YTDLPAudioData
    from pi_yo_8.voice_client import AudioTrack


# Button Views
class PlayerControlsView(discord.ui.View):
    def __init__(self, guild_session: "GuildSession"):
        super().__init__(timeout=None)
        self.guild_session = guild_session
        self.select_opt: list[discord.SelectOption] = []
        self.pause_play = PlayPauseButton(self.guild_session)
        self.add_item(self.pause_play)
        self.add_item(Forward10sButton(self.guild_session))
        self.add_item(NextTrackButton(self.guild_session))
        self.add_item(OptionsButton(self.guild_session))
        self.add_item(DisconnectButton(self.guild_session))
        self.add_item(QueueSelectMenu(self, self.guild_session.music.queue))
        self.add_item(ToggleStatusButton(self, '単曲 ループ', 'loop'))
        if self.guild_session.music.queue.is_playing_playlist():
            self.add_item(ToggleStatusButton(self, 'Playlist ループ', 'loop_pl'))
            self.add_item(ToggleStatusButton(self, 'シャッフル', 'random_pl'))
        else:
            self.add_item(ToggleStatusButton(self, 'Playlist ループ', 'loop_pl', True))
            self.add_item(ToggleStatusButton(self, 'シャッフル', 'random_pl', True))

    @discord.ui.button(label="<", row=2)
    async def prev_track_button(self, interaction: discord.Interaction, button):
        self.guild_session.embed.record_channel_activity()
        await interaction.response.defer()
        await self.guild_session.music.skip_tracks(-1)

    @discord.ui.button(label="10↩︎", row=2)
    async def rewind_10s_button(self, interaction: discord.Interaction, button):
        self.guild_session.embed.record_channel_activity()
        await interaction.response.defer()
        await self.guild_session.music.player_track.seek_by_seconds(-10)


class PlayPauseButton(discord.ui.Button):
    def __init__(self, guild_session: "GuildSession"):
        _label = '▶' if guild_session.music.player_track.is_paused() else 'II'
        super().__init__(label=_label, style=discord.ButtonStyle.blurple, row=2)
        self.guild_session = guild_session

    async def callback(self, interaction: Interaction):
        self.guild_session.embed.record_channel_activity()
        await interaction.response.defer()

        if self.guild_session.music.player_track.is_paused():
            self.guild_session.music.player_track.resume()
        elif self.guild_session.music.player_track.has_audio_data():
            self.guild_session.music.player_track.pause()


class Forward10sButton(discord.ui.Button):
    def __init__(self, guild_session: "GuildSession"):
        super().__init__(label="↪︎10", row=2)
        self.guild_session = guild_session

    async def callback(self, interaction: Interaction):
        self.guild_session.embed.record_channel_activity()
        await interaction.response.defer()
        await self.guild_session.music.player_track.seek_by_seconds(10)


class NextTrackButton(discord.ui.Button):
    def __init__(self, guild_session: "GuildSession"):
        super().__init__(label=">", row=2)
        self.guild_session = guild_session

    async def callback(self, interaction: Interaction):
        self.guild_session.embed.record_channel_activity()
        await interaction.response.defer()
        await self.guild_session.music.seek_or_skip(None)


class OptionsButton(discord.ui.Button):
    def __init__(self, guild_session: "GuildSession"):
        super().__init__(label="⚙️", row=3)
        self.guild_session = guild_session

    async def callback(self, interaction: Interaction):
        self.guild_session.embed.record_channel_activity()
        await interaction.response.defer()

        if message := self.guild_session.embed.options_display:
            if isinstance(message.channel, SendableChannels) and message.channel.last_message == message:
                return
            else:
                try:
                    await message.delete()
                except discord.NotFound:
                    pass
        
        if isinstance(interaction.channel, discord.abc.Messageable):
            self.guild_session.embed.options_display = await send_play_option_message(interaction.channel, self.guild_session)


class DisconnectButton(discord.ui.Button):
    def __init__(self, guild_session: "GuildSession"):
        super().__init__(label="切断", row=3, style=discord.ButtonStyle.red)
        self.guild_session = guild_session

    async def callback(self, interaction: Interaction):
        await interaction.response.defer()
        await self.guild_session.bye()


class ToggleStatusButton(discord.ui.Button):
    def __init__(self, parent: 'PlayerControlsView', label: str, status_name: str, disable: bool = False):
        self.view_parent = parent
        self.name = status_name
        self.disable = disable
        super().__init__(label=label, row=1, style=self.style_check(), disabled=disable)

    def style_check(self):
        if self.disable:
            return discord.ButtonStyle.gray
        elif self.view_parent.guild_session.music.status.__dict__[self.name]:
            return discord.ButtonStyle.green
        else:
            return discord.ButtonStyle.red
    
    async def callback(self, interaction: discord.Interaction):
        status = self.view_parent.guild_session.music.status
        status.set(**{self.name: not status.__dict__[self.name]})
        self.style = self.style_check()
        self.view_parent.guild_session.embed.record_channel_activity()
        await interaction.response.edit_message(view=self.view_parent)


class QueueSelectMenu(discord.ui.Select):
    def __init__(self, parent: 'PlayerControlsView', queue: "MusicQueue") -> None:
        self.view_parent = parent
        select_opt = []
        prev_items = queue.get_prev_items(4)
        next_items = queue.get_next_items(25 - len(prev_items))
        for i in range(-len(prev_items), len(next_items)):
            entry = prev_items[i] if i < 0 else next_items[i]
            title = entry.title()[0:100] if len(entry.title()) >= 100 else entry.title()
            select_opt.append(discord.SelectOption(label=title, value=str(i), default=(i == 0)))

        if not select_opt:
            select_opt.append(discord.SelectOption(label='動画がないよぉ～ん', value='0', default=False))
        parent.select_opt = select_opt
        super().__init__(placeholder='キュー表示', options=select_opt, row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.values[0] == '': return

        self.view_parent.guild_session.embed.record_channel_activity()
        await self.view_parent.guild_session.music.skip_tracks(int(self.values[0]))


async def send_play_option_message(channel: discord.abc.Messageable, guild_session: "GuildSession") -> discord.Message:
    return await channel.send(
        embed=create_play_config_embed(guild_session.music.player_track),
        view=PlayConfigView(guild_session)
    )


def create_play_config_embed(audio_track: "AudioTrack"):
    embed = discord.Embed(colour=EmbedTemplates.get_persistent_color())
    embed.add_field(name='テンポ (x0.1 ~ x3.0)', value=f'x{round(audio_track.speed.get(), 2)}', inline=True)
    embed.add_field(name='キー', value=f'{audio_track.pitch.get()}', inline=True)
    return embed


class PlayConfigView(discord.ui.View):
    def __init__(self, guild_session: "GuildSession"):
        super().__init__(timeout=None)
        self.guild_session = guild_session
        self.player_track = guild_session.music.player_track

    async def edit_message(self, interaction: discord.Interaction):
        if interaction.message:
            await interaction.message.edit(embed=create_play_config_embed(self.player_track))

    async def edit_speed(self, interaction: discord.Interaction, delta: float):
        await interaction.response.defer()
        res = await self.player_track.speed.add(delta)
        self.guild_session.embed.record_channel_activity()
        if res:
            await self.edit_message(interaction)

    async def edit_pitch(self, interaction: discord.Interaction, delta: int):
        await interaction.response.defer()
        res = await self.player_track.pitch.add(delta)
        self.guild_session.embed.record_channel_activity()
        if res:
            await self.edit_message(interaction)

    @discord.ui.button(label="- 0.5", row=0)
    async def speed_m5(self, interaction: discord.Interaction, button):
        await self.edit_speed(interaction, -0.5)

    @discord.ui.button(label="- 0.1", row=0)
    async def speed_m1(self, interaction: discord.Interaction, button):
        await self.edit_speed(interaction, -0.1)

    @discord.ui.button(label="テンポリセット", row=0, style=discord.ButtonStyle.blurple)
    async def speed_reset(self, interaction: discord.Interaction, button):
        await interaction.response.defer()
        res = await self.player_track.speed.set(1.0)
        if res:
            await self.edit_message(interaction)

    @discord.ui.button(label="+ 0.1", row=0)
    async def speed_p1(self, interaction: discord.Interaction, button):
        await self.edit_speed(interaction, 0.1)

    @discord.ui.button(label="+ 0.5", row=0)
    async def speed_p5(self, interaction: discord.Interaction, button):
        await self.edit_speed(interaction, 0.5)

    @discord.ui.button(label="- 2", row=1)
    async def pitch_m2(self, interaction: discord.Interaction, button):
        await self.edit_pitch(interaction, -2)

    @discord.ui.button(label="- 1", row=1)
    async def pitch_m1(self, interaction: discord.Interaction, button):
        await self.edit_pitch(interaction, -1)

    @discord.ui.button(label="キー　リセット", row=1, style=discord.ButtonStyle.blurple)
    async def pitch_reset(self, interaction: discord.Interaction, button):
        await interaction.response.defer()
        res = await self.player_track.pitch.set(0)
        if res:
            await self.edit_message(interaction)

    @discord.ui.button(label="+ 1", row=1)
    async def pitch_p1(self, interaction: discord.Interaction, button):
        await self.edit_pitch(interaction, 1)

    @discord.ui.button(label="+ 2", row=1)
    async def pitch_p2(self, interaction: discord.Interaction, button):
        await self.edit_pitch(interaction, 2)

    @discord.ui.button(label="↺", row=2, style=discord.ButtonStyle.red)
    async def reload(self, interaction: discord.Interaction, button):
        self.guild_session.embed.record_channel_activity()
        await interaction.response.edit_message(embed=create_play_config_embed(self.player_track))

    @discord.ui.button(label="delete", row=2, style=discord.ButtonStyle.red)
    async def delete(self, interaction: discord.Interaction, button):
        self.guild_session.embed.record_channel_activity()
        await interaction.response.defer()
        if interaction.message:
            await interaction.message.delete()
        self.guild_session.embed.options_display = None




# class LyricView(discord.ui.View):
#     def __init__(self, songs:List[GeniusLyric]):
#         self.songs = songs
#         super().__init__(timeout=None)
#         self.select = LyricSelect(self)
#         self.add_item(self.select)

#     @discord.ui.button(label='Delete', style=discord.ButtonStyle.red, row=1)
#     async def def_button0(self, interaction:discord.Interaction, button):
#         await interaction.response.defer()
#         await interaction.message.delete()

# class LyricSelect(discord.ui.Select):
#     def __init__(self, parent:'LyricView', i=0):
#         self.parent = parent
#         if 25 < len(parent.songs):
#             self.songs = parent.songs[:25]
#         else:
#             self.songs = parent.songs
#         self.my_options = [discord.SelectOption(label=_.title, value=i) for i,_ in enumerate(self.songs)]
#         options = self.my_options.copy()
#         options[i].default = True
#         super().__init__(placeholder='曲リスト', options=options)

#     async def callback(self, interaction: discord.Interaction):
#         res = int(self.values[0])
#         lyric = await self.songs[res].get_lyric()
#         self.options = self.my_options.copy()
#         self.parent.remove_item(self.parent.select)
#         select = LyricSelect(self.parent, i=res)
#         self.parent.select = select
#         self.parent.add_item(select)
#         #super().__init__(placeholder='曲リスト', options=options)
#         await interaction.response.edit_message(
#             embed= LyricEmbed(lyric),
#             view= self.parent
#         )


# def LyricEmbed(description):
#     if not description:
#         description = 'None'
#     return discord.Embed(description=description, color=EmBase.dont_replace_color())
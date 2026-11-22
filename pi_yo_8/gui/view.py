from typing import TYPE_CHECKING

import discord
from discord import Interaction

from pi_yo_8.core.playlist import Playlist
from pi_yo_8.core.types import SENDABLE_CHANNEL_TYPES
from pi_yo_8.gui.utils import EmbedTemplates

if TYPE_CHECKING:
    from pi_yo_8.core.queue import PlayQueue
    from pi_yo_8.engine.track_stream import AudioTrack
    from pi_yo_8.services.session import GuildSession


class PlayerControlsView(discord.ui.View):
    def __init__(self, guild_session: "GuildSession") -> None:
        super().__init__(timeout=None)
        self.guild_session = guild_session
        self.history_select_opt: list[discord.SelectOption] = []
        self.select_opt: list[discord.SelectOption] = []
        self.pause_play = PlayPauseButton(self.guild_session)
        self.add_item(self.pause_play)
        self.add_item(Forward10sButton(self.guild_session))
        self.add_item(NextTrackButton(self.guild_session))
        self.add_item(OptionsButton(self.guild_session))
        self.add_item(DisconnectButton(self.guild_session))
        self.add_item(HistorySelectMenu(self, self.guild_session.music.queue))
        self.add_item(QueueSelectMenu(self, self.guild_session.music.queue))
        self.add_item(ToggleStatusButton(self, '単曲 ループ', 'loop'))
        if self.guild_session.music.queue.is_playing_playlist():
            self.add_item(ToggleStatusButton(self, 'Playlist ループ', 'loop_pl'))
            self.add_item(ToggleStatusButton(self, 'シャッフル', 'random_pl'))
        else:
            self.add_item(ToggleStatusButton(self, 'Playlist ループ', 'loop_pl', True))
            self.add_item(ToggleStatusButton(self, 'シャッフル', 'random_pl', True))

    @discord.ui.button(label="<", row=3)
    async def prev_track_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.guild_session.embed.record_channel_activity()
        await interaction.response.defer()
        await self.guild_session.music.skip_tracks(-1)

    @discord.ui.button(label="10↩︎", row=3)
    async def rewind_10s_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.guild_session.embed.record_channel_activity()
        await interaction.response.defer()
        await self.guild_session.music.player_track.seek_by_seconds(-10)
        await self.guild_session.embed.refresh_main_display()


class PlayPauseButton(discord.ui.Button):
    def __init__(self, guild_session: "GuildSession") -> None:
        _label = '▶' if guild_session.music.player_track.is_paused() else 'II'
        super().__init__(label=_label, style=discord.ButtonStyle.blurple, row=3)
        self.guild_session = guild_session

    async def callback(self, interaction: Interaction) -> None:
        self.guild_session.embed.record_channel_activity()
        await interaction.response.defer()

        if self.guild_session.music.player_track.is_paused():
            self.guild_session.music.player_track.resume()
        elif self.guild_session.music.player_track.has_audio_data():
            self.guild_session.music.player_track.pause()
        await self.guild_session.embed.refresh_main_display()


class Forward10sButton(discord.ui.Button):
    def __init__(self, guild_session: "GuildSession") -> None:
        super().__init__(label="↪︎10", row=3)
        self.guild_session = guild_session

    async def callback(self, interaction: Interaction) -> None:
        self.guild_session.embed.record_channel_activity()
        await interaction.response.defer()
        await self.guild_session.music.player_track.seek_by_seconds(10)
        await self.guild_session.embed.refresh_main_display()


class NextTrackButton(discord.ui.Button):
    def __init__(self, guild_session: "GuildSession") -> None:
        super().__init__(label=">", row=3)
        self.guild_session = guild_session

    async def callback(self, interaction: Interaction) -> None:
        self.guild_session.embed.record_channel_activity()
        await interaction.response.defer()
        await self.guild_session.music.seek_or_skip(None)


class OptionsButton(discord.ui.Button):
    def __init__(self, guild_session: "GuildSession") -> None:
        super().__init__(label="⚙️", row=4)
        self.guild_session = guild_session

    async def callback(self, interaction: Interaction) -> None:
        self.guild_session.embed.record_channel_activity()
        await interaction.response.defer()

        if message := self.guild_session.embed.options_display:
            if isinstance(message.channel, SENDABLE_CHANNEL_TYPES) and message.channel.last_message == message:
                return
            try:
                await message.delete()
            except discord.NotFound:
                pass

        if isinstance(interaction.channel, discord.abc.Messageable):
            self.guild_session.embed.options_display = await send_play_option_message(interaction.channel, self.guild_session)


class DisconnectButton(discord.ui.Button):
    def __init__(self, guild_session: "GuildSession") -> None:
        super().__init__(label="切断", row=4, style=discord.ButtonStyle.red)
        self.guild_session = guild_session

    async def callback(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        await self.guild_session.bye()


class ToggleStatusButton(discord.ui.Button):
    def __init__(self, parent: 'PlayerControlsView', label: str, status_name: str, disable: bool = False) -> None:
        self.view_parent = parent
        self.name = status_name
        self.disable = disable
        super().__init__(label=label, row=2, style=self.style_check(), disabled=disable)

    def style_check(self) -> discord.ButtonStyle:
        if self.disable:
            return discord.ButtonStyle.gray
        val = getattr(self.view_parent.guild_session.music.status, self.name, False)
        return discord.ButtonStyle.green if val else discord.ButtonStyle.red

    async def callback(self, interaction: discord.Interaction) -> None:
        status = self.view_parent.guild_session.music.status
        current_val = getattr(status, self.name, False)
        status.set(**{self.name: not current_val})
        self.style = self.style_check()
        self.view_parent.guild_session.embed.record_channel_activity()
        await interaction.response.edit_message(view=self.view_parent)


class HistorySelectMenu(discord.ui.Select):
    def __init__(self, parent: 'PlayerControlsView', queue: "PlayQueue") -> None:
        self.view_parent = parent
        items = queue.get_history_menu_items(max_past=5, max_current_pl=20)
        select_opt = [
            discord.SelectOption(label=label, value=value, default=False)
            for label, value in items
        ]
        disabled = False
        if not select_opt:
            select_opt.append(discord.SelectOption(label='履歴はないよぉ～ん', value='none', default=False))
            disabled = True
        parent.history_select_opt = select_opt
        super().__init__(placeholder='履歴', options=select_opt, row=0, disabled=disabled)

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        if not self.values or self.values[0] in ('', 'none'):
            return

        self.view_parent.guild_session.embed.record_channel_activity()
        await self.view_parent.guild_session.music.select_history(self.values[0])


class QueueSelectMenu(discord.ui.Select):
    def __init__(self, parent: 'PlayerControlsView', queue: "PlayQueue") -> None:
        self.view_parent = parent
        select_opt: list[discord.SelectOption] = []
        max_next = 25
        raw_next_items = queue.get_next_items(max_next)
        exclude_ids = {id(x) for x in raw_next_items}
        upcoming_items = queue.get_upcoming_queue_items(2, exclude_ids=exclude_ids)
        next_items = raw_next_items[: max(0, max_next - len(upcoming_items))]
        for i, entry in enumerate(next_items):
            entry_title = getattr(entry, "title", None)
            if callable(entry_title):
                entry_title = entry_title()
            video_title = str(entry_title or "No Title")
            playlist_title = getattr(entry, "playlist_title", None)
            if playlist_title:
                pl_prefix = playlist_title if len(playlist_title) <= 15 else f"{playlist_title[:14]}…"
                label = f"{pl_prefix}  │  {video_title}"[:100]
            else:
                label = video_title[:100]
            select_opt.append(discord.SelectOption(label=label, value=str(i), default=(i == 0)))

        for q_idx, item in upcoming_items:
            item_title = getattr(item, "title", None)
            if callable(item_title):
                item_title = item_title()
            title_str = str(item_title or "No Title")
            prefix = "次のPlaylist  │ " if isinstance(item, Playlist) else "次の単曲  │ "
            label = f"{prefix} {title_str}"[:100]
            select_opt.append(discord.SelectOption(label=label, value=f"q:{q_idx}", default=False))

        if not select_opt:
            select_opt.append(discord.SelectOption(label='動画がないよぉ～ん', value='0', default=False))
        parent.select_opt = select_opt
        super().__init__(placeholder='キュー表示', options=select_opt, row=1)

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        if not self.values or self.values[0] == '':
            return

        self.view_parent.guild_session.embed.record_channel_activity()
        val = self.values[0]
        if val.startswith(("q:", "pl:")):
            await self.view_parent.guild_session.music.skip_to_queue_index(int(val.split(":", 1)[1]))
        else:
            await self.view_parent.guild_session.music.skip_tracks(int(val))


async def send_play_option_message(channel: discord.abc.Messageable, guild_session: "GuildSession") -> discord.Message:
    return await channel.send(
        embed=create_play_config_embed(guild_session.music.player_track),
        view=PlayConfigView(guild_session),
    )


def create_play_config_embed(audio_track: "AudioTrack") -> discord.Embed:
    embed = discord.Embed(colour=EmbedTemplates.get_persistent_color())
    embed.add_field(name='テンポ (x0.1 ~ x3.0)', value=f'x{round(audio_track.speed.get(), 2)}', inline=True)
    embed.add_field(name='キー', value=f'{audio_track.pitch.get()}', inline=True)
    return embed


class PlayConfigView(discord.ui.View):
    def __init__(self, guild_session: "GuildSession") -> None:
        super().__init__(timeout=None)
        self.guild_session = guild_session
        self.player_track = guild_session.music.player_track

    async def edit_message(self, interaction: discord.Interaction) -> None:
        if interaction.message:
            await interaction.message.edit(embed=create_play_config_embed(self.player_track))

    async def edit_speed(self, interaction: discord.Interaction, delta: float) -> None:
        await interaction.response.defer()
        res = await self.player_track.speed.add(delta)
        self.guild_session.embed.record_channel_activity()
        if res:
            await self.edit_message(interaction)

    async def edit_pitch(self, interaction: discord.Interaction, delta: int) -> None:
        await interaction.response.defer()
        res = await self.player_track.pitch.add(delta)
        self.guild_session.embed.record_channel_activity()
        if res:
            await self.edit_message(interaction)

    @discord.ui.button(label="- 0.5", row=0)
    async def speed_m5(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.edit_speed(interaction, -0.5)

    @discord.ui.button(label="- 0.1", row=0)
    async def speed_m1(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.edit_speed(interaction, -0.1)

    @discord.ui.button(label="テンポリセット", row=0, style=discord.ButtonStyle.blurple)
    async def speed_reset(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer()
        res = await self.player_track.speed.set(1.0)
        if res:
            await self.edit_message(interaction)

    @discord.ui.button(label="+ 0.1", row=0)
    async def speed_p1(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.edit_speed(interaction, 0.1)

    @discord.ui.button(label="+ 0.5", row=0)
    async def speed_p5(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.edit_speed(interaction, 0.5)

    @discord.ui.button(label="- 2", row=1)
    async def pitch_m2(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.edit_pitch(interaction, -2)

    @discord.ui.button(label="- 1", row=1)
    async def pitch_m1(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.edit_pitch(interaction, -1)

    @discord.ui.button(label="キー　リセット", row=1, style=discord.ButtonStyle.blurple)
    async def pitch_reset(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer()
        res = await self.player_track.pitch.set(0)
        if res:
            await self.edit_message(interaction)

    @discord.ui.button(label="+ 1", row=1)
    async def pitch_p1(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.edit_pitch(interaction, 1)

    @discord.ui.button(label="+ 2", row=1)
    async def pitch_p2(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.edit_pitch(interaction, 2)

    @discord.ui.button(label="↺", row=2, style=discord.ButtonStyle.red)
    async def reload(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.guild_session.embed.record_channel_activity()
        await interaction.response.edit_message(embed=create_play_config_embed(self.player_track))

    @discord.ui.button(label="delete", row=2, style=discord.ButtonStyle.red)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.guild_session.embed.record_channel_activity()
        await interaction.response.defer()
        if interaction.message:
            try:
                await interaction.message.delete()
            except discord.NotFound:
                pass
        self.guild_session.embed.options_display = None

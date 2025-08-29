import asyncio
import discord
from typing import Any, List, TYPE_CHECKING

from discord.interactions import Interaction

from pi_yo_8.gui import EmbedTemplates


if TYPE_CHECKING:
    from pi_yo_8.main import DataInfo
    from pi_yo_8.music_control import MusicQueue
    from pi_yo_8.extractor.yt_dlp import YTDLPAudioData
    from pi_yo_8.voice_client import AudioTrack


# Button
class CreateButton(discord.ui.View):
    def __init__(self, info:DataInfo):
        super().__init__(timeout=None)
        self.info = info
        self.select_opt:list[discord.SelectOption] = None
        self.pause_play = Button2(self.info)
        self.add_item(self.pause_play)
        self.add_item(Button3(self.info))
        self.add_item(Button4(self.info))
        self.add_item(Button5(self.info))
        self.add_item(Button7(self.info))
        self.add_item(CreateSelect(self, (self.info.music.queue)))
        self.add_item(CreateStatusButton(self, '単曲 ループ', 'loop'))
        if self.info.music.queue.is_playing_playlist():
            self.add_item(CreateStatusButton(self, 'Playlist ループ', 'loop_pl'))
            self.add_item(CreateStatusButton(self, 'シャッフル', 'random_pl'))
        else:
            self.add_item(CreateStatusButton(self, 'Playlist ループ', 'loop_pl', True))
            self.add_item(CreateStatusButton(self, 'シャッフル', 'random_pl', True))



    @discord.ui.button(label="<",row=2)
    async def def_button0(self, interaction:discord.Interaction, button):
        self.info.embed.update_action_time()
        asyncio.get_event_loop().create_task(interaction.response.defer())
        await self.info.music.skip_music(-1)

    @discord.ui.button(label="10↩︎",row=2)
    async def def_button1(self, interaction:discord.Interaction, button):
        self.info.embed.update_action_time()
        asyncio.get_event_loop().create_task(interaction.response.defer())
        self.info.music.player_track.skip_time(-10*50)


class Button2(discord.ui.Button):
    def __init__(self, info:DataInfo):
        _label = '▶' if info.music.player_track.is_paused() else 'II'
        super().__init__(label=_label,style=discord.ButtonStyle.blurple,row=2)
        self.info = info

    async def callback(self, interaction: Interaction):
        self.info.embed.update_action_time()
        asyncio.get_event_loop().create_task(interaction.response.defer())

        if self.info.music.player_track.is_paused():
            self.info.music.player_track.resume()
        elif self.info.music.player_track.is_playing():
            self.info.music.player_track.pause()


class Button3(discord.ui.Button):
    def __init__(self, info:DataInfo):
        super().__init__(label="↪︎10",row=2)
        self.info = info

    async def callback(self, interaction: Interaction):
        self.info.embed.update_action_time()
        asyncio.get_event_loop().create_task(interaction.response.defer())
        self.info.music.player_track.skip_time(10*50)

class Button4(discord.ui.Button):
    def __init__(self, info:DataInfo):
        super().__init__(label=">",row=2)
        self.info = info

    async def callback(self, interaction: Interaction):
        self.info.embed.update_action_time()
        asyncio.get_event_loop().create_task(interaction.response.defer())
        await self.info.music.skip(None)


class Button5(discord.ui.Button):
    def __init__(self, info:DataInfo):
        super().__init__(label="⚙️",row=3)
        self.info = info

    async def callback(self, interaction: Interaction):
        self.info.embed.update_action_time()
        self.info.embed.update_action_time()
        asyncio.get_event_loop().create_task(interaction.response.defer())
        if message := self.info.embed.options_display:
            if message.channel.last_message == message:
                return
            else:
                try:
                    await message.delete()
                except discord.NotFound:
                    pass

        self.info.embed.options_display = await playoptionmessage(interaction.channel, self.info)

    # @discord.ui.button(label="歌詞", row=3)
    # async def def_button6(self, interaction:discord.Interaction, button):
    #     self.Parent._update_action()

    #     if title := self.Parent.Mvc._SAD.title:
    #         songs = await GeniusLyric.from_q(title)
    #         if songs:
    #             text = await songs[0].get_lyric()
    #             await interaction.response.send_message(
    #                 embed= LyricEmbed(text),
    #                 view= LyricView(songs),
    #                 ephemeral= False
    #                 )
    #             return
    #     await interaction.response.send_message(
    #         embed= LyricEmbed('歌詞の取得に失敗しました'),
    #         ephemeral= False,
    #         delete_after=10,
    #         )
        

class Button7(discord.ui.Button):
    def __init__(self, info:DataInfo):
        super().__init__(label="切断",row=3, style=discord.ButtonStyle.red)
        self.info = info

    async def callback(self, interaction: Interaction):
        await interaction.response.defer()
        await self.info.bye()


class CreateStatusButton(discord.ui.Button):
    def __init__(self, parent:'CreateButton', label:str, status_name:str, disable:bool=False):
        self.view_parent = parent
        self.name = status_name
        self.disable = disable
        super().__init__(label=label, row=1, style=self.style_check(), disabled=disable)

    def style_check(self):
        if self.disable:
            return discord.ButtonStyle.gray
        elif self.view_parent.info.music.status.__dict__[self.name]:
            return discord.ButtonStyle.green
        else:
            return discord.ButtonStyle.red
    
    async def callback(self, interaction: discord.Interaction):
        status = self.view_parent.info.music.status.__dict__
        status[self.name] = not status[self.name]
        self.style = self.style_check()
        self.view_parent.info.embed._update_action()
        await interaction.response.edit_message(view=self.view_parent)




class CreateSelect(discord.ui.Select):
    def __init__(self, parent:'CreateButton', queue:MusicQueue) -> None:
        self.view_parent = parent
        select_opt = []
        _audio: YTDLPAudioData
        #print(args)
        for i, _audio in enumerate(queue):
            title = _audio.title()
            if i >= 25:
                break
            if len(title) >= 100:
                title = title[0:100]
            select_opt.append(discord.SelectOption(label=title,value=str(i),default=(select_opt == [])))

        if not select_opt:
            select_opt.append(discord.SelectOption(label='動画がないよぉ～ん',value='None',default=False))
        parent.select_opt = select_opt
        super().__init__(placeholder='キュー表示', options=select_opt, row=0)


    async def callback(self, interaction: discord.Interaction):
        #await interaction.response.send_message(f'{interaction.user.name}は{self.values[0]}を選択しました')
        asyncio.get_event_loop().create_task(interaction.response.defer())
        if self.values[0] == 'None': return

        self.view_parent.info.embed.update_action_time()
        await self.view_parent.info.music.skip_music(int(self.values[0]))
        #print(f'{interaction.user.name}は{self.values[0]}を選択しました')


async def playoptionmessage(channel:discord.abc.Messageable, info:DataInfo) -> discord.Message:
    return await channel.send(
        embed= PlayConfigEmbed(info.music.player_track),
        view= PlayConfigView(info)
        )


def PlayConfigEmbed(audio_track:AudioTrack):
    embed = discord.Embed(colour=EmbedTemplates.dont_replace_color())
    embed.add_field(name='テンポ (x0.1 ~ x3.0)', value=f'x{round(audio_track.speed.get,2)}', inline=True)
    embed.add_field(name='キー', value=f'{audio_track.pitch.get}', inline=True)
    return embed



class PlayConfigView(discord.ui.View):
    def __init__(self, info:DataInfo):
        super().__init__(timeout=None)
        self.info = info
        self.player_track = info.music.player_track

    async def edit_message(self, interaction:discord.Interaction):
        await interaction.message.edit(embed=PlayConfigEmbed(self.player_track))

    async def edit_speed(self, interaction:discord.Interaction, num:float):
        asyncio.get_event_loop().create_task(interaction.response.defer())
        res = await self.player_track.speed.add(num)
        self.info.embed.update_action_time()
        if res:
            await self.edit_message(interaction)


    async def edit_pitch(self, interaction:discord.Interaction, num:int):
        asyncio.get_event_loop().create_task(interaction.response.defer())
        res = await self.player_track.pitch.add(num)
        self.info.embed.update_action_time()
        if res:
            await self.edit_message(interaction)


    @discord.ui.button(label="- 0.5", row=0)
    async def speed_m5(self, interaction:discord.Interaction, button):
        await self.edit_speed(interaction, -0.5)


    @discord.ui.button(label="- 0.1", row=0)
    async def speed_m1(self, interaction:discord.Interaction, button):
        await self.edit_speed(interaction, -0.1)
        

    @discord.ui.button(label="テンポリセット", row=0, style=discord.ButtonStyle.blurple)
    async def speed_reset(self, interaction:discord.Interaction, button):
        asyncio.get_event_loop().create_task(interaction.response.defer())
        res = await self.player_track.speed.set(1.0)
        if res:
            await self.edit_message(interaction)


    @discord.ui.button(label="+ 0.1", row=0)
    async def speed_p1(self, interaction:discord.Interaction, button):
        await self.edit_speed(interaction, 0.1)


    @discord.ui.button(label="+ 0.5", row=0)
    async def speed_p5(self, interaction:discord.Interaction, button):
        await self.edit_speed(interaction, 0.5)


    @discord.ui.button(label="- 2", row=1)
    async def pitch_m2(self, interaction:discord.Interaction, button):
        await self.edit_pitch(interaction, -2)


    @discord.ui.button(label="- 1", row=1)
    async def pitch_m1(self, interaction:discord.Interaction, button):
        await self.edit_pitch(interaction, -1)


    @discord.ui.button(label="キー　リセット", row=1, style=discord.ButtonStyle.blurple)
    async def pitch_reset(self, interaction:discord.Interaction, button):
        asyncio.get_event_loop().create_task(interaction.response.defer())
        res = await self.player_track.pitch.set(0)
        if res:
            await self.edit_message(interaction)


    @discord.ui.button(label="+ 1", row=1)
    async def pitch_p1(self, interaction:discord.Interaction, button):
        await self.edit_pitch(interaction, 1)


    @discord.ui.button(label="+ 2", row=1)
    async def pitch_p2(self, interaction:discord.Interaction, button):
        await self.edit_pitch(interaction, 2)


    @discord.ui.button(label="↺", row=2, style=discord.ButtonStyle.red)
    async def reload(self, interaction:discord.Interaction, button):
        self.info.embed.update_action_time()
        await interaction.response.edit_message(embed=PlayConfigEmbed(self.player_track))


    @discord.ui.button(label="delete", row=2, style=discord.ButtonStyle.red)
    async def delete(self, interaction:discord.Interaction, button):
        self.info.embed.update_action_time()
        await interaction.response.defer()
        await interaction.message.delete()
        self.info.embed.options_display = None



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
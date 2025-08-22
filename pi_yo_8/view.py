import asyncio
import discord
from typing import Any, List

from discord.interactions import Interaction

from pi_yo_8.audio_data import StreamAudioData as SAD
from pi_yo_8.embeds import EmBase
from pi_yo_8.voice_client import AudioTrack
#from .lyricsgenius.lyrics import GeniusLyric


# Button
class CreateButton(discord.ui.View):
    def __init__(self, Parent):
        super().__init__(timeout=None)
        try:
            from .music_control._music_controller import MusicController
            self.Parent:MusicController
        except Exception: pass
        self.Parent = Parent
        self.select_opt:list[discord.SelectOption] = None
        self.pause_play = Button2(self)
        self.add_item(self.pause_play)
        self.add_item(Button3(self))
        self.add_item(Button4(self))
        self.add_item(Button5(self))
        self.add_item(Button7(self))
        self.add_item(CreateSelect(self, (self.Parent.queue)))
        self.add_item(CreateStatusButton(self, '単曲 ループ', 'loop'))
        if self.Parent.PL:
            self.add_item(CreateStatusButton(self, 'Playlist ループ', 'loop_pl'))
            self.add_item(CreateStatusButton(self, 'シャッフル', 'random_pl'))
        else:
            self.add_item(CreateStatusButton(self, 'Playlist ループ', 'loop_pl', True))
            self.add_item(CreateStatusButton(self, 'シャッフル', 'random_pl', True))



    @discord.ui.button(label="<",row=2)
    async def def_button0(self, interaction:discord.Interaction, button):
        Parent = self.Parent
        Parent._update_action()
        Parent.loop.create_task(interaction.response.defer())
        await Parent.skip_music(-1)

    @discord.ui.button(label="10↩︎",row=2)
    async def def_button1(self, interaction:discord.Interaction, button):
        Parent = self.Parent
        Parent._update_action()
        Parent.loop.create_task(interaction.response.defer())
        Parent.Mvc.skip_time(-10*50)
            

class Button2(discord.ui.Button):
    def __init__(self, parent:CreateButton):
        _label = '▶' if parent.Parent.Mvc.is_paused() else 'II'
        super().__init__(label=_label,style=discord.ButtonStyle.blurple,row=2)
        self.parent = parent.Parent

    async def callback(self, interaction: Interaction):
        parent = self.parent
        parent._update_action()
        parent.loop.create_task(interaction.response.defer())

        if parent.Mvc.is_paused():
            parent.resume()
        elif parent.Mvc.is_playing():
            parent.pause()  


class Button3(discord.ui.Button):
    def __init__(self, parent:CreateButton):
        super().__init__(label="↪︎10",row=2)
        self.parent = parent

    async def callback(self, interaction: Interaction):
        Parent = self.parent.Parent
        Parent._update_action()
        Parent.loop.create_task(interaction.response.defer())
        Parent.Mvc.skip_time(10*50)

class Button4(discord.ui.Button):
    def __init__(self, parent:CreateButton):
        super().__init__(label=">",row=2)
        self.parent = parent

    async def callback(self, interaction: Interaction):
        Parent = self.parent.Parent
        Parent._update_action()
        Parent.loop.create_task(interaction.response.defer())
        await Parent.skip(None)


class Button5(discord.ui.Button):
    def __init__(self, parent:CreateButton):
        super().__init__(label="⚙️",row=3)
        self.parent = parent

    async def callback(self, interaction: Interaction):
        parent = self.parent.Parent
        parent._update_action()
        parent.loop.create_task(interaction.response.defer())
        if message := parent.embed_play_options:
            if message.channel.last_message == message:
                return
            else:
                try:
                    await message.delete()
                except discord.NotFound:
                    pass
                
        parent.embed_play_options = await playoptionmessage(interaction.channel, parent)

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
    def __init__(self, parent:CreateButton):
        super().__init__(label="切断",row=3, style=discord.ButtonStyle.red)
        self.parent = parent

    async def callback(self, interaction: Interaction):
        await interaction.response.defer()
        await self.parent.Parent.Info.bye()


class CreateStatusButton(discord.ui.Button):
    def __init__(self, parent:'CreateButton', label:str, status_name:str, disable:bool=False):
        self.parent = parent
        self.name = status_name
        self.disable = disable
        super().__init__(label=label, row=1, style=self.style_check(), disabled=disable)

    def style_check(self):
        if self.disable:
            return discord.ButtonStyle.gray
        elif self.parent.Parent.status[self.name]:
            return discord.ButtonStyle.green
        else:
            return discord.ButtonStyle.red
    
    async def callback(self, interaction: discord.Interaction):
        status = self.parent.Parent.status
        status[self.name] = not status[self.name]
        self.style = self.style_check()
        self.parent.Parent._update_action()
        await interaction.response.edit_message(view=self.parent)




class CreateSelect(discord.ui.Select):
    def __init__(self, parent:'CreateButton', args) -> None:
        self.loop = asyncio.get_event_loop()
        self.parent = parent
        self.parent2 = parent.Parent
        select_opt = []
        _audio: SAD
        #print(args)
        for i, _audio in enumerate(args):
            title = _audio.title
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
        self.loop.create_task(interaction.response.defer())
        if self.values[0] == 'None': return

        music = self.parent2
        music._update_action()
        await music.skip_music(int(self.values[0]))
        #print(f'{interaction.user.name}は{self.values[0]}を選択しました')


async def playoptionmessage(channel:discord.TextChannel, music) -> discord.Message:
    return await channel.send(
        embed= PlayConfigEmbed(music.Mvc),
        view= PlayConfigView(music)
        )


def PlayConfigEmbed(Mvc:AudioTrack):
    embed = discord.Embed(colour=EmBase.dont_replace_color())
    embed.add_field(name='テンポ (x0.1 ~ x3.0)', value=f'x{round(Mvc.speed.get,2)}', inline=True)
    embed.add_field(name='キー', value=f'{Mvc.pitch.get}', inline=True)
    return embed



class PlayConfigView(discord.ui.View):
    def __init__(self, parent):
        try:
            from .music_control._music_controller import MusicController
            self.parent:MusicController
        except Exception: pass

        super().__init__(timeout=None)
        self.parent = parent
        self.loop = self.parent.loop
        self.Mvc = self.parent.Mvc
        self.speed = self.Mvc.speed
        self.pitch = self.Mvc.pitch


    async def edit_message(self, interaction:discord.Interaction):
        await interaction.message.edit(embed=PlayConfigEmbed(self.Mvc))

    async def edit_speed(self, interaction:discord.Interaction, num:float):
        self.loop.create_task(interaction.response.defer())
        res = await self.speed.add(num)
        self.parent._update_action()
        if res:
            await self.edit_message(interaction)


    async def edit_pitch(self, interaction:discord.Interaction, num:int):
        self.loop.create_task(interaction.response.defer())
        res = await self.pitch.add(num)
        self.parent._update_action()
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
        self.loop.create_task(interaction.response.defer())
        res = await self.speed.set(1.0)
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
        self.loop.create_task(interaction.response.defer())
        res = await self.pitch.set(0)
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
        self.parent._update_action()
        await interaction.response.edit_message(embed=PlayConfigEmbed(self.Mvc))


    @discord.ui.button(label="delete", row=2, style=discord.ButtonStyle.red)
    async def delete(self, interaction:discord.Interaction, button):
        self.parent._update_action()
        await interaction.response.defer()
        await interaction.message.delete()
        self.parent.embed_play_options = None



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
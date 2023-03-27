import asyncio
import time
from discord import ui, Interaction, SelectOption ,ButtonStyle, Embed

from .audio_source import StreamAudioData as SAD
from .embeds import EmBase
from .voice_client import _AudioTrack



# Button
class CreateButton(ui.View):
    def __init__(self, Parent):
        super().__init__(timeout=None)
        try:
            from .music import MusicController
            self.Parent:MusicController
        except Exception: pass
        self.Parent = Parent
        self.select_opt:list[SelectOption] = None
        self.add_item(CreateSelect(self, (self.Parent.Queue + self.Parent.Next_PL['PL'])))
        self.add_item(CreateStatusButton(self, '単曲ループ', 'loop'))
        if self.Parent.PL:
            self.add_item(CreateStatusButton(self, 'Playlistループ', 'loop_pl'))
            self.add_item(CreateStatusButton(self, 'シャッフル', 'random_pl'))
        else:
            self.add_item(CreateStatusButton(self, 'Playlistループ', 'loop_pl', True))
            self.add_item(CreateStatusButton(self, 'シャッフル', 'random_pl', True))


    @ui.button(label="<",row=1)
    async def def_button0(self, interaction:Interaction, button):
        Parent = self.Parent
        Parent._update_action()
        Parent.CLoop.create_task(interaction.response.defer())

        if not Parent.Rewind: return
        AudioData = Parent.Rewind[-1]
        Parent.Queue.insert(0,AudioData)
        del Parent.Rewind[-1]
        if Parent.PL:
            if type(AudioData.index) == int:
                Parent.Index_PL = AudioData.index

        await Parent.play_loop(None,0)
        if Parent.Mvc.is_paused():
            Parent.Mvc.resume()

    @ui.button(label="10↩︎",row=1)
    async def def_button1(self, interaction:Interaction, button):
        Parent = self.Parent
        Parent._update_action()
        Parent.CLoop.create_task(interaction.response.defer())
        Parent.Mvc.skip_time(-10*50)

    @ui.button(label="⏯",style=ButtonStyle.blurple,row=1)
    async def def_button2(self, interaction:Interaction, button):
        Parent = self.Parent
        Parent._update_action()
        Parent.CLoop.create_task(interaction.response.defer())

        if Parent.Mvc.is_paused():
            print(f'{Parent.gn} : #resume')
            Parent.Mvc.resume()
        elif Parent.Mvc.is_playing():
            print(f'{Parent.gn} : #stop')
            Parent.Mvc.pause()
            await Parent.update_embed()

    @ui.button(label="↪︎10",row=1)
    async def def_button3(self, interaction:Interaction, button):
        Parent = self.Parent
        Parent._update_action()
        Parent.CLoop.create_task(interaction.response.defer())
        Parent.Mvc.skip_time(10*50)

    @ui.button(label=">",row=1)
    async def def_button4(self, interaction:Interaction, button):
        Parent = self.Parent
        Parent._update_action()
        Parent.CLoop.create_task(interaction.response.defer())
        await Parent.skip(None)

    @ui.button(label="⚙️", row=2)
    async def def_button5(self, interaction:Interaction, button):
        self.Parent._update_action()
        await interaction.response.send_message(
            embed= PlayConfigEmbed(self.Parent.Mvc),
            view= PlayConfigView(self.Parent),
            ephemeral= False
            )
        
    @ui.button(label="切断", row=2, style=ButtonStyle.red)
    async def def_button6(self, interaction:Interaction, button):
        await interaction.response.defer()
        await self.Parent.Info._bye()



class CreateStatusButton(ui.Button):
    def __init__(self, parent:'CreateButton', label:str, status_name:str, disable:bool=False):
        self.parent = parent
        self.name = status_name
        self.disable = disable
        super().__init__(label=label, row=3, style=self.style_check(), disabled=disable)

    def style_check(self):
        if self.disable:
            return ButtonStyle.gray
        elif self.parent.Parent.status[self.name]:
            return ButtonStyle.green
        else:
            return ButtonStyle.red
    
    async def callback(self, interaction: Interaction):
        status = self.parent.Parent.status
        status[self.name] = not status[self.name]
        self.style = self.style_check()
        self.parent.Parent._update_action()
        await interaction.response.edit_message(view=self.parent)




class CreateSelect(ui.Select):
    def __init__(self, parent:'CreateButton', args) -> None:
        self.loop = asyncio.get_event_loop()
        self.parent = parent
        self.parent2 = parent.Parent
        select_opt = []
        _audio: SAD
        #print(args)
        for i, _audio in enumerate(args):
            title = _audio.Title
            if i >= 25:
                break
            if len(title) >= 100:
                title = title[0:100]
            select_opt.append(SelectOption(label=title,value=str(i),default=(select_opt == [])))

        parent.select_opt = select_opt
        super().__init__(placeholder='キュー表示', options=select_opt, row=0)


    async def callback(self, interaction: Interaction):
        #await interaction.response.send_message(f'{interaction.user.name}は{self.values[0]}を選択しました')
        self.loop.create_task(interaction.response.defer())
        music = self.parent2
        music._update_action()
        for i in range(int(self.values[0])):
            if music.Queue:
                music.Rewind.append(music.Queue[0])
                del music.Queue[0]
            elif music.Next_PL['PL']:
                music.Rewind.append(music.Next_PL['PL'])
                del music.Next_PL['PL'][0]
        await music.play_loop(None,0)
        #print(f'{interaction.user.name}は{self.values[0]}を選択しました')


def PlayConfigEmbed(Mvc:_AudioTrack):
    embed = Embed(colour=EmBase.dont_replace_color())
    embed.add_field(name='テンポ (x0.1 ~ x3.0)', value=f'x{round(Mvc.speed.get,2)}', inline=True)
    embed.add_field(name='キー', value=f'{Mvc.pitch.get}', inline=True)
    return embed



class PlayConfigView(ui.View):
    def __init__(self, parent):
        try:
            from .music import MusicController
            self.parent:MusicController
        except Exception: pass

        super().__init__(timeout=None)
        self.parent = parent
        self.loop = self.parent.CLoop
        self.Mvc = self.parent.Mvc
        self.speed = self.Mvc.speed
        self.pitch = self.Mvc.pitch


    async def edit_message(self, interaction:Interaction):
        await interaction.message.edit(embed=PlayConfigEmbed(self.Mvc))

    async def edit_speed(self, interaction:Interaction, num:float):
        self.loop.create_task(interaction.response.defer())
        res = await self.speed.add(num)
        self.parent._update_action()
        if res:
            await self.edit_message(interaction)


    async def edit_pitch(self, interaction:Interaction, num:int):
        self.loop.create_task(interaction.response.defer())
        res = await self.pitch.add(num)
        self.parent._update_action()
        if res:
            await self.edit_message(interaction)


    @ui.button(label="- 0.5", row=0)
    async def speed_m5(self, interaction:Interaction, button):
        await self.edit_speed(interaction, -0.5)


    @ui.button(label="- 0.1", row=0)
    async def speed_m1(self, interaction:Interaction, button):
        await self.edit_speed(interaction, -0.1)
        

    @ui.button(label="テンポリセット", row=0, style=ButtonStyle.blurple)
    async def speed_reset(self, interaction:Interaction, button):
        self.loop.create_task(interaction.response.defer())
        res = await self.speed.set(1.0)
        if res:
            await self.edit_message(interaction)


    @ui.button(label="+ 0.1", row=0)
    async def speed_p1(self, interaction:Interaction, button):
        await self.edit_speed(interaction, 0.1)


    @ui.button(label="+ 0.5", row=0)
    async def speed_p5(self, interaction:Interaction, button):
        await self.edit_speed(interaction, 0.5)


    @ui.button(label="- 2", row=1)
    async def pitch_m2(self, interaction:Interaction, button):
        await self.edit_pitch(interaction, -2)


    @ui.button(label="- 1", row=1)
    async def pitch_m1(self, interaction:Interaction, button):
        await self.edit_pitch(interaction, -1)


    @ui.button(label="キー　リセット", row=1, style=ButtonStyle.blurple)
    async def pitch_reset(self, interaction:Interaction, button):
        self.loop.create_task(interaction.response.defer())
        res = await self.pitch.set(0)
        if res:
            await self.edit_message(interaction)


    @ui.button(label="+ 1", row=1)
    async def pitch_p1(self, interaction:Interaction, button):
        await self.edit_pitch(interaction, 1)


    @ui.button(label="+ 2", row=1)
    async def pitch_p2(self, interaction:Interaction, button):
        await self.edit_pitch(interaction, 2)


    @ui.button(label="↺", row=2, style=ButtonStyle.red)
    async def reload(self, interaction:Interaction, button):
        self.parent._update_action()
        await interaction.response.edit_message(embed=PlayConfigEmbed(self.Mvc))


    @ui.button(label="delete", row=2, style=ButtonStyle.red)
    async def delete(self, interaction:Interaction, button):
        self.parent._update_action()
        await interaction.response.defer()
        await interaction.message.delete()
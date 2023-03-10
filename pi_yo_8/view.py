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
        self.add_item(CreateSelect(self, Parent, (Parent.Queue + Parent.Next_PL['PL'])))


    @ui.button(label="<",row=1)
    async def def_button0(self, interaction:Interaction, button):
        Parent = self.Parent
        Parent.last_action = time.time()
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
        Parent.last_action = time.time()
        Parent.CLoop.create_task(interaction.response.defer())
        Parent.Mvc.skip_time(-10*50)

    @ui.button(label="⏯",style=ButtonStyle.blurple,row=1)
    async def def_button2(self, interaction:Interaction, button):
        Parent = self.Parent
        Parent.last_action = time.time()
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
        Parent.last_action = time.time()
        Parent.CLoop.create_task(interaction.response.defer())
        Parent.Mvc.skip_time(10*50)

    @ui.button(label=">",row=1)
    async def def_button4(self, interaction:Interaction, button):
        Parent = self.Parent
        Parent.CLoop.create_task(interaction.response.defer())
        await Parent._skip(None)

    @ui.button(label="⚙️",row=2)
    async def def_button5(self, interaction:Interaction, button):
        parent = self.Parent
        await interaction.response.send_message(
            embed= PlayConfigEmbed(parent.Mvc),
            view= PlayConfigSpeedView(parent),
            ephemeral= False
            )
        


class CreateSelect(ui.Select):
    def __init__(self, parent1, parent2, args) -> None:
        self.loop = asyncio.get_event_loop()
        try: self.parent1:'CreateButton'
        except Exception: pass
        self.parent = parent2
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

        parent1.select_opt = select_opt
        super().__init__(placeholder='キュー表示', options=select_opt, row=0)


    async def callback(self, interaction: Interaction):
        #await interaction.response.send_message(f'{interaction.user.name}は{self.values[0]}を選択しました')
        self.loop.create_task(interaction.response.defer())
        self.parent.last_action = time.time()
        for i in range(int(self.values[0])):
            if self.parent.Queue:
                self.parent.Rewind.append(self.parent.Queue[0])
                del self.parent.Queue[0]
            elif self.parent.Next_PL['PL']:
                self.parent.Rewind.append(self.parent.Next_PL['PL'])
                del self.parent.Next_PL['PL'][0]
        await self.parent.play_loop(None,0)
        #print(f'{interaction.user.name}は{self.values[0]}を選択しました')


def PlayConfigEmbed(Mvc:_AudioTrack):
    embed = Embed(colour=EmBase.dont_replace_color())
    embed.add_field(name='再生速度 (0.01 - 100)', value=f'x{round(Mvc.speed,2)}', inline=True)
    embed.add_field(name='ピッチ (-12 ~ 12)', value=f'x{Mvc.pitch}', inline=True)
    return embed


class PlayConfigSelect(ui.Select):
    def __init__(self, parent, select:int=0) -> None:
        self.parent = parent
        select_opt:list[SelectOption] = []
        select_opt.append(SelectOption(label='スピード', value=0))
        select_opt.append(SelectOption(label='ピッチ', value=1))
        select_opt[select].default = True
        super().__init__(placeholder='設定', options=select_opt, row=0)

    async def callback(self, interaction: Interaction):
        await interaction.response.defer()
        value = int(self.values[0])
        if value == 0:
            await interaction.message.edit(view=PlayConfigSpeedView(self.parent))
        elif value == 1:
            await interaction.message.edit(view=PlayConfigPitchView(self.parent))

class PlayConfigSpeedView(ui.View):
    def __init__(self, parent):
        try:
            from .music import MusicController
            self.parent:MusicController
        except Exception: pass

        super().__init__(timeout=None)
        self.add_item(PlayConfigSelect(parent, select=0))
        self.parent = parent
        self.loop = self.parent.CLoop
        self.Mvc = self.parent.Mvc

    
    @ui.button(label="-0.1", row=1)
    async def speed_m(self, interaction:Interaction, button):
        self.loop.create_task(interaction.response.defer())
        speed = self.parent.Mvc.speed - 0.1
        if 0.01 < speed < 100:
            self.parent.Mvc.speed = speed
            self.loop.create_task(self.parent.Mvc.update_asouce_sec())
            await interaction.message.edit(embed=PlayConfigEmbed(self.Mvc))
        

    @ui.button(label="スピードリセット", row=1, style=ButtonStyle.blurple)
    async def speed_reset(self, interaction:Interaction, button):
        self.loop.create_task(interaction.response.defer())
        if self.parent.Mvc.speed != 1.0:
            self.parent.Mvc.speed = 1.0
            self.loop.create_task(self.parent.Mvc.update_asouce_sec())
            await interaction.message.edit(embed=PlayConfigEmbed(self.Mvc))


    @ui.button(label="+0.1", row=1)
    async def speed_p(self, interaction:Interaction, button):
        self.loop.create_task(interaction.response.defer())
        speed = self.parent.Mvc.speed + 0.1
        if 0.01 < speed < 100:
            self.parent.Mvc.speed = speed
            self.loop.create_task(self.parent.Mvc.update_asouce_sec())
            await interaction.message.edit(embed=PlayConfigEmbed(self.Mvc))


    @ui.button(label="delete", row=1, style=ButtonStyle.red)
    async def delete(self, interaction:Interaction, button):
        await interaction.response.defer()
        await interaction.message.delete()
        


class PlayConfigPitchView(ui.View):
    def __init__(self, parent):
        try:
            from .music import MusicController
            self.parent:MusicController
        except Exception: pass

        super().__init__(timeout=None)
        self.add_item(PlayConfigSelect(parent, select=1))
        self.parent = parent
        self.loop = self.parent.CLoop
        self.Mvc = self.parent.Mvc


    @ui.button(label="半音下げる", row=1)
    async def pitch_m(self, interaction:Interaction, button):
        self.loop.create_task(interaction.response.defer())
        pitch = self.parent.Mvc.pitch - 1
        if -12 <= pitch <= 12:
            self.parent.Mvc.pitch = pitch
            self.loop.create_task(self.parent.Mvc.update_asouce_sec())
            await interaction.message.edit(embed=PlayConfigEmbed(self.Mvc))


    @ui.button(label="ピッチ リセット", row=1, style=ButtonStyle.blurple)
    async def pitch_reset(self, interaction:Interaction, button):
        self.loop.create_task(interaction.response.defer())
        if self.parent.Mvc.pitch != 0:
            self.parent.Mvc.pitch = 0
            self.loop.create_task(self.parent.Mvc.update_asouce_sec())
            await interaction.message.edit(embed=PlayConfigEmbed(self.Mvc))


    @ui.button(label="半音上げる", row=1)
    async def pitch_p(self, interaction:Interaction, button):
        self.loop.create_task(interaction.response.defer())
        pitch = self.parent.Mvc.pitch + 1
        if -12 <= pitch <= 12:
            self.parent.Mvc.pitch = pitch
            self.loop.create_task(self.parent.Mvc.update_asouce_sec())
            await interaction.message.edit(embed=PlayConfigEmbed(self.Mvc))


    @ui.button(label="delete", row=1, style=ButtonStyle.red)
    async def delete(self, interaction:Interaction, button):
        await interaction.response.defer()
        await interaction.message.delete()
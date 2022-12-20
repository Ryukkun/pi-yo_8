import asyncio
import time
from discord import ui, Interaction, SelectOption ,ButtonStyle

from .audio_source import StreamAudioData as SAD
if __name__ == '__main__':
    from .music import MusicController


# Button
class CreateButton(ui.View):
    def __init__(self, Parent):
        super().__init__(timeout=None)
        try: self.Parent:MusicController
        except Exception: pass
        self.Parent = Parent
        select_opt = None
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



class CreateSelect(ui.Select):
    def __init__(self, parent1, parent2, args) -> None:
        self.loop = asyncio.get_event_loop()
        try: self.parent:MusicController
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
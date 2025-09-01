import re
import time
import tabulate
import asyncio
import logging
import copy
from typing import Any, Callable, List,  TYPE_CHECKING
from discord import Embed
from discord.ext.commands import Context
from dataclasses import dataclass


from pi_yo_8.extractor.yt_dlp import YTDLPAudioData
from pi_yo_8.music_control import Playlist
from pi_yo_8.music_control._playlist import GeneratorPlaylist
from pi_yo_8.utils import YT_DLP, UrlAnalyzer

if TYPE_CHECKING:
    from pi_yo_8.main import DataInfo


re_URL_YT = re.compile(r'https://((www.|)youtube.com|youtu.be)/')
re_URL_Video = re.compile(r'https://((www.|)youtube.com/watch\?v=|(youtu.be/))(.+)')
re_URL_PL = re.compile(r'https://(www.|)youtube.com/playlist\?list=')
re_skip = re.compile(r'^((-|)\d+)([hms])$')
re_skip_set_h = re.compile(r'^(\d+)[:;,](\d+)[:;,](\d+)$')
re_skip_set_m = re.compile(r'^(\d+)[:;,](\d+)$')


re_video = re.compile(r'video/(.+);')
re_audio = re.compile(r'audio/(.+);')
re_codecs = re.compile(r'codecs="(.+)"')
re_space = re.compile(r'\)` +?\|')
re_space2 = re.compile(r'(( |-)\|$|^\|( |-))')
re_space3 = re.compile(r'^\|( |-)+?\|')


_log = logging.getLogger(__name__)



@dataclass
class Status:
    loop: bool = False
    loop_pl: bool = False
    random_pl: bool = False
    callback: Callable[..., Any] | None = None

    def set(self, loop: bool | None = None, loop_pl: bool | None = None, random_pl: bool | None = None):
        old = copy.copy(self)
        if loop != None: self.loop = loop
        if loop_pl != None: self.loop_pl = loop_pl
        if random_pl != None: self.random_pl = random_pl

        if self.callback and self != old:
            self.callback(old=old, new=copy.copy(self))



class MusicQueue:
    def __init__(self):
        self.play_history:List[YTDLPAudioData | Playlist] = []
        self.play_queue:List[YTDLPAudioData | Playlist] = []


    def next(self, count:int=1, ignore_playlist:bool=False) -> bool:
        if not self.play_queue:
            return False

        if isinstance(self.play_queue[0], Playlist) and not ignore_playlist:
            if self.play_queue[0].next(count):
                return True
            else:
                count = 1

        while 0 < count and self.play_queue:
            count -= 1
            self.play_history.append(self.play_queue.pop(0))
            
        while count < 0 and self.play_history:
            count += 1
            self.play_queue.insert(0, self.play_history.pop(-1))

        return bool(self.play_queue)


    async def get_item0(self):
        if not self.play_queue:
            return None
        item = self.play_queue[0]
        if isinstance(item, Playlist):
            item = await item.get_now_entry()
        return item
    

    def is_playing_playlist(self):
        if not self.play_queue:
            return False
        item = self.play_queue[0]
        return isinstance(item, Playlist)
    

    def get_next_items(self, count:int = 25) -> List[YTDLPAudioData]:
        if not self.play_queue:
            return []
        items = []
        for queue_index in range(count):
            item = self.play_queue[queue_index]
            if isinstance(item, Playlist):
                for entry in [item.entries[i] for i in item.next_indexes]:
                    items.append(entry)
                    if count <= len(items): break
                if isinstance(item, GeneratorPlaylist) and not item.decompres_task.done():
                    return items
            else:
                items.append(item)
            if count <= len(items): break
        return items


class MusicController():
    def __init__(self, info:DataInfo):
        self.info = info
        self.player_track = info.MA.add_track(RNum=30 ,opus=True)
        self.guild = info.guild
        self.queue:MusicQueue = MusicQueue()
        self.status = Status()
        self.last_status = copy.copy(self.status)



    async def def_queue(self, ctx:Context, args):
        self.info.embed.update_action_time(ctx.channel)
        _log.info(f"{self.guild.name} : Command:queue {args}")
        # 一時停止していた場合再生 開始
        if args:
            arg = ' '.join(args)
        else:
            self.player_track.resume()
            return

        result = await self._analysis_input(arg)
        if not result: return

        #Queueに登録
        self.queue.play_queue.append(result)

        # 再生されるまでループ
        if not self.player_track.is_playing():
            await self.play_loop(None,0)
        self.player_track.resume()



    async def play(self, ctx:Context, args):
        self.info.embed.update_action_time(ctx.channel)
        _log.info(f"{self.guild.name} : Command:play {' '.join(args)}")
        # 一時停止していた場合再生 開始
        if args:
            arg = ' '.join(args)
        else:
            self.player_track.resume()
            return

        res = await self._analysis_input(arg)
        if not res: return

        if self.queue.play_queue:
            self.queue.next(ignore_playlist=True)
        self.queue.play_queue.insert(0,res)

        if isinstance(res, Playlist):
            self.status = res.status
            self.last_status = copy.copy(self.status)

        # 再生されるまでループ
        await self.play_loop(None,0)
        self.player_track.resume()



    async def _analysis_input(self, arg:str) -> Playlist | YTDLPAudioData | None:
        analysis = UrlAnalyzer(arg)

        with YT_DLP.get() as ydl:
            if analysis.is_yt and analysis.list_id:
                if pl := await ydl.extract_yt_playlist_info(analysis.list_id):
                    if analysis.video_id:
                        pl.status.set(loop=False, loop_pl=True, random_pl=False)
                        await pl.set_next_index_from_videoID(analysis.video_id)
                    else:
                        pl.status.set(loop=False, loop_pl=True, random_pl=True)
                return pl

            result = await ydl.extract_info(arg)
        if isinstance(result, Playlist):
            result.status.set(loop=False, loop_pl=True, random_pl=False)
        return result
    


    async def skip(self, sec_str:str | None):
        if self.guild.voice_client:
            self.info.embed.update_action_time()
            if sec_str:
                try:sec = int(sec_str)
                except Exception:
                    sec = sec_str.lower()
                    if res := re_skip.match(sec):
                        sec = int(res.group(1))
                        suf = res.group(3)
                        if suf == 'h':
                            sec = sec * 3600
                        elif suf == 'm':
                            sec = sec * 60

                    elif res := re_skip_set_h.match(sec):
                        sec = int(res.group(3))
                        sec += int(res.group(2)) * 60
                        sec += int(res.group(1)) * 3600
                        self.player_track.skip_time((sec * 50) - int(self.player_track.timer))
                        return

                    elif res := re_skip_set_m.match(sec):
                        sec = int(res.group(2))
                        sec += int(res.group(1)) * 60
                        self.player_track.skip_time((sec * 50) - int(self.player_track.timer))
                        return

                self.player_track.skip_time(int(sec) * 50)

            else:
                await self.skip_music()



    async def skip_music(self, count:int=1):
        if count == 0: return

        res:bool = self.queue.next(count)
        if not res: return
        _log.info(f'{self.guild.name} : #{abs(count)}曲{"前へ prev" if count < 0 else "次へ skip"}')

        await self.play_loop()
        if self.player_track.is_paused():
            self.player_track.resume()



    def resume(self):
        _log.info(f"{self.guild.name} : #resume")
        self.player_track.resume()

    def pause(self):
        _log.info(f"{self.guild.name} : #stop")
        self.player_track.pause()


#---------------------------------------------------------------------------------------
#   Download
#---------------------------------------------------------------------------------------
    @classmethod
    async def download(self, arg:str):

        # Download Embed
        url = UrlAnalyzer(arg)
        if not audio_data: return

        if audio_data.YT:
            embed=Embed(title=audio_data.title, url=audio_data.web_url, colour=EmBase.main_color())
            embed.set_thumbnail(url=f'https://img.youtube.com/vi/{audio_data.video_id}/mqdefault.jpg')
            embed.set_author(name=audio_data.ch_name, url=audio_data.ch_url, icon_url=audio_data.ch_icon)
            
        else:
            embed=Embed(title=audio_data.web_url, url=audio_data.web_url, colour=EmBase.main_color())

        if audio_data.st_sec:
            Duration = calc_time(audio_data.st_sec)
            embed.add_field(name="Length", value=Duration, inline=True)

            
        __list = []
        if audio_data.formats:
            for F in audio_data.formats:

                _dl = f'[`download`]({F["url"]})`'

                if F.get('width'):
                    _res = f"{F['width']}x{F['height']}"
                elif F.get('resolution'):
                    _res = F.get('resolution')
                else: 
                    _res = ''

                ext = F.get('ext','')
                acodec = F.get('acodec','')
                vcodec = F.get('vcodec','')
                abr = F.get('abr','?k')
                protocol = F.get('protocol','')

                if res := re_codecs.search(F.get('mimeType','')):
                    codec = res.group(1).split(', ')
                    _type = F.get('mimeType')
                    _type = _type.replace(f' {res.group(0)}','')

                    if res := re_video.match(_type):
                        ext = res.group(1)
                        vcodec = codec[0]
                        if len(codec) == 2:
                            acodec = codec[1]
                    
                    elif res := re_audio.match(_type):
                        ext = res.group(1)
                        _res = 'audio'
                        acodec = codec[0]
                        abr = f"{F['bitrate']//10/100}k"

                if '3gpp' in ext or 'm3u8' in protocol:
                    continue

                __list.append([_dl,ext,_res,vcodec,acodec,abr])

            headers = ['','EXT','RES','Video','Audio','ABR']
            table = tabulate.tabulate(tabular_data=__list, headers=headers, tablefmt='github')
            table = re_space.sub(')`|',table)
            table = table.split('\n')
            table[0] = re_space2.sub('',re_space3.sub('[`--------`](https://github.com/Ryukkun/pi-yo_8)`|',table[0]))
            table[1] = re_space2.sub('',re_space3.sub('[`--------`](https://github.com/Ryukkun/pi-yo_8)`|',table[1]))

            _embeds = [embed]
            while table:
                __table = ''
                embed = Embed(colour=EmBase.main_color())
                while len(__table) <= 4000:
                    if __table: 
                        del table[0]
                    if len(table) == 0:
                        _table = __table
                        break
                    _table = __table
                    temp = re_space2.sub('',table[0])
                    __table += f'{temp}`\n'

                embed.description = _table
                _embeds.append(embed)
                embed = None

            return _embeds



        else:
            embed=Embed(title=audio_data.web_url, url=audio_data.web_url, colour=EmBase.main_color())
            embed_list = [embed]
            embed=Embed(title='Download', url=audio_data.st_url, colour=EmBase.main_color())
            embed_list.append(embed)

        return embed_list
            


#---------------------------------------------------------------------------------------
#   再生 Loop
#---------------------------------------------------------------------------------------
    async def play_loop(self, played=None, did_time=0):
        """
        再生後に実行される
        """

        # あなたは用済みよ
        if not self.guild.voice_client: return
        loop = asyncio.get_event_loop()

        # Queue削除
        if self.queue:
            if self.status['loop'] == False and self.queue[0].stream_url == played or (time.time() - did_time) <= 0.2:
                self.queue.next()

        # 再生
        if audio_data := await self.queue.get_item0():
            played_time = time.time()
            _log.info(f"{self.guild.name} : Play {audio_data.web_url()}  volume:{audio_data.volume}  [Now len: {str(len(self.queue.play_queue))}]")

            await self.player_track.play(audio_data,after=lambda : loop.create_task(self.play_loop(audio_data.stream_url,played_time)))


    # async def task_loop(self):
    #     '''
    #     Infoより 5秒おきに実行
    #     '''

    #     try:
    #         # PlayList再生時に 次の動画を取得する
    #         if self.PL and self.status['random_pl'] != self.last_status['random_pl']:
    #             self.last_status = self.status.copy()
    #             del self.queue[1:]
    #             self._load_next_pl()
    #     except Exception as e:
    #         print(e)
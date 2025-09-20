from collections import deque
import re
import time
import tabulate
import asyncio
import logging
import copy
from typing import List,  TYPE_CHECKING
from discord import Embed
from discord.ext.commands import Context



from pi_yo_8.yt_dlp.manager import YTDLPManager
from pi_yo_8.gui.utils import EmbedTemplates, calc_time
from pi_yo_8.music_control.playlist import Playlist, LazyPlaylist
from pi_yo_8.music_control.utils import Status
from pi_yo_8.utils import UrlAnalyzer
from pi_yo_8.yt_dlp.unit import YTDLP_GENERAL_PARAMS
from pi_yo_8.yt_dlp.audio_data import YTDLPAudioData

if TYPE_CHECKING:
    from pi_yo_8.main import DataInfo


re_skip = re.compile(r'^((-|)\d+)([hms])$')
re_skip_set_h = re.compile(r'^(\d+)[:;,](\d+)[:;,](\d+)$')
re_skip_set_m = re.compile(r'^(\d+)[:;,](\d+)$')


re_space = re.compile(r'\)` +?\|')
re_space2 = re.compile(r'(( |-)\|$|^\|( |-))')
re_space3 = re.compile(r'^\|( |-)+?\|')


_log = logging.getLogger(__name__)





class MusicQueue:
    def __init__(self):
        self.play_history:deque["YTDLPAudioData | Playlist"] = deque()
        self.play_queue:deque["YTDLPAudioData | Playlist"] = deque()


    async def next(self, count:int=1, ignore_playlist:bool=False) -> bool:
        """音楽キューを進める

        Parameters
        ----------
        count : int
            飛ばす曲の個数 負の数も対応, by default 1
        ignore_playlist : bool
            プレイリストを無視して飛ばすか, by default False

        Returns
        -------
        bool
            続きの曲があるか
        """
        #次へ
        while 0 < count and self.play_queue:
            # プレイリスト再生中の場合
            if isinstance(self.play_queue[0], Playlist) and not ignore_playlist:
                count = await self.play_queue[0].next(count)
                if count == 0:
                    break
            self.play_history.append(self.play_queue.popleft())
            count -= 1   
            
        #前へ
        while count < 0:
            if self.play_queue and isinstance(self.play_queue[0], Playlist):
                count = - await self.play_queue[0].rewind(abs(count))
                if count == 0:
                    break

            if self.play_history:
                count += 1
                self.play_queue.appendleft(self.play_history.pop())
            else:
                break

        return bool(self.play_queue)


    async def get_item0(self) -> YTDLPAudioData | None:
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
    
    def get_prev_items(self, count:int = 25) -> "deque[YTDLPAudioData]":
        return_items:"deque[YTDLPAudioData]" = deque()
        prev_items = self.play_history.copy()
        if self.play_queue and isinstance(self.play_queue[0], Playlist):
            prev_items.append(self.play_queue[0])
        
        for item in reversed(prev_items):
            if isinstance(item, Playlist):
                for entry in reversed([item.entries[i] for i in item.play_history]):
                    return_items.appendleft(entry)
                    if count <= len(return_items):
                        return return_items
            else:
                return_items.appendleft(item)
                if count <= len(return_items):
                    break
        return return_items


    def get_next_items(self, count:int = 25) -> "list[YTDLPAudioData]":
        if not self.play_queue:
            return []
        items = []
        for queue_index in range(min(count, len(self.play_queue))):
            item = self.play_queue[queue_index]
            if isinstance(item, Playlist):
                for entry in [item.entries[i] for i in item.next_indexes]:
                    items.append(entry)
                    if count <= len(items): break
                if isinstance(item, LazyPlaylist) and not item.decompres_task.done():
                    return items
            else:
                items.append(item)
            if count <= len(items): break
        return items


class MusicController():
    def __init__(self, info:"DataInfo"):
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
            await self._skip_music(ignore_playlist=True)
        self.queue.play_queue.appendleft(res)

        if isinstance(res, Playlist):
            self.status = res.status
            self.last_status = copy.copy(self.status)

        # 再生されるまでループ
        await self.play_loop(None,0)
        self.player_track.resume()


    @staticmethod
    async def _analysis_input(arg:str) -> "Playlist | YTDLPAudioData | None":
        print("extract:", arg)
        info_generator = YTDLPManager.YT_DLP.get(YTDLP_GENERAL_PARAMS).extract_raw_info(arg)
        if info := await anext(info_generator, None):
            if info.get("playlist"):
                analysis = UrlAnalyzer(arg)
                res = LazyPlaylist(info, info_generator)

                if analysis.is_yt and analysis.list_id:
                    if analysis.video_id:
                        await res.set_next_index_from_videoID(analysis.video_id)
                    else:
                        res.status.set(loop=False, loop_pl=True, random_pl=True)
                print("extract playlist:", arg)
                return res

            if info.get("formats") and info.get("url"):
                print("extract video", arg)
                res = YTDLPAudioData(info)
                res.load_ch_icon.create_task()
                return res
                
        print("extract None:", arg)
        return None


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
                        self.player_track.skip_time((sec) - int(self.player_track.timer))
                        return

                    elif res := re_skip_set_m.match(sec):
                        sec = int(res.group(2))
                        sec += int(res.group(1)) * 60
                        self.player_track.skip_time((sec) - int(self.player_track.timer))
                        return

                self.player_track.skip_time(int(sec))

            else:
                await self.skip_music()



    async def _skip_music(self, count:int=1, ignore_playlist:bool=False) -> bool:
        '''
        Parameters
        ----------
        count : int
            countの数だけ曲をスキップ
        ignore_playlist : bool
            プレイリストを無視するかどうか

        Returns
        -------
        bool
            次の曲があるか
        '''
        if count == 0:
            return bool(self.queue.play_queue)
        res:bool = await self.queue.next(count, ignore_playlist)
        if res:
            data = self.queue.play_queue[0]
            if isinstance(data, LazyPlaylist):
                data.status.set(self.status.loop, self.status.loop_pl, self.status.random_pl)
                self.status = data.status
        return res



    async def skip_music(self, count:int=1):
        if count == 0: return

        res:bool = await self._skip_music(count)
        if not res: return
        data = self.queue.play_queue[0]
        if isinstance(data, LazyPlaylist):
            data.status.set(self.status.loop, self.status.loop_pl, self.status.random_pl)
            self.status = data.status
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
    @staticmethod
    async def download(arg:str) -> list[Embed] | None:
        # Download Embed
        url = UrlAnalyzer(arg)
        result = await MusicController._analysis_input(arg)
        if result is None:
            return
        audio_data = result.entries[0] if isinstance(result, Playlist) else result
        await audio_data.check_streaming_data.run()
        if not await audio_data.is_available():
            return

        embed=Embed(title=audio_data.title(), url=audio_data.web_url(), colour=EmbedTemplates.main_color())
        embed.set_thumbnail(url=await audio_data.load_thumbnail.run())
        embed.set_author(name=audio_data.ch_name(), url=audio_data.ch_url(), icon_url=await audio_data.load_ch_icon.run())
            
        if audio_data.duration:
            Duration = calc_time(audio_data.duration)
            embed.add_field(name="Length", value=Duration, inline=True)

            
        __list = []
        for f in audio_data.formats():

            _dl_string = f'[`download`]({f["url"]})`'

            if f.get('width'):
                _res = f"{f['width']}x{f['height']}"
            elif f.get('resolution'):
                _res = f.get('resolution')
            else: 
                _res = ''

            ext = f.get('ext','')
            acodec = f.get('acodec','')
            vcodec = f.get('vcodec','')
            abr = f"{f.get('abr','?')}k"
            protocol = f.get('protocol','')


            if '3gpp' in ext:
                continue

            __list.append([_dl_string,ext,protocol,_res,acodec,abr])

        headers = ['','EXT','Protocol','RES','Audio','ABR']
        table = tabulate.tabulate(tabular_data=__list, headers=headers, tablefmt='github')
        table = re_space.sub(')`|',table)
        table = table.split('\n')
        table[0] = re_space2.sub('',re_space3.sub('[`--------`](https://github.com/Ryukkun/pi-yo_8)`|',table[0]))
        table[1] = re_space2.sub('',re_space3.sub('[`--------`](https://github.com/Ryukkun/pi-yo_8)`|',table[1]))

        _embeds = [embed]
        while table:
            __table = ''
            embed = Embed(colour=EmbedTemplates.main_color())
            while table:
                temp = re_space2.sub('', table[0])
                if len(__table) + len(temp) + 5 > 4096:
                    break
                __table += f'{temp}`\n'
                table.pop(0)
                
            embed.description = __table
            _embeds.append(embed)

        return _embeds



        
            # embed=Embed(title=audio_data.web_url, url=audio_data.web_url, colour=EmbedTemplates.main_color())
            # embed_list = [embed]
            # embed=Embed(title='Download', url=audio_data.st_url, colour=EmbedTemplates.main_color())
            # embed_list.append(embed)

        return embed_list
            


#---------------------------------------------------------------------------------------
#   再生 Loop
#---------------------------------------------------------------------------------------
    async def play_loop(self, played=None, did_time=0.0):
        """
        再生後に実行される
        """

        if not self.guild.voice_client: return
        loop = asyncio.get_event_loop()

        # Queue削除
        audio_data = await self.queue.get_item0()
        if audio_data:
            if self.status.loop == False and audio_data.stream_url == played or (time.time() - did_time) <= 0.2:
                await self._skip_music()


        # 再生
        if audio_data := await self.queue.get_item0():
            played_time = time.time()
            _log.info(f"{self.guild.name} : Play {audio_data.web_url()}  volume:{audio_data.get_volume()}  [Now len: {str(len(self.queue.play_queue))}]")

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
from collections import deque
import re
import time
import tabulate
import asyncio
import logging
import copy
from typing import TYPE_CHECKING
from discord import Embed
from discord.ext.commands import Context



from pi_yo_8.yt_dlp.manager import YTDLPManager
from pi_yo_8.gui.utils import EmbedTemplates, format_seconds_to_time
from pi_yo_8.music_control.playlist import Playlist, LazyPlaylist
from pi_yo_8.music_control.utils import Status
from pi_yo_8.utils import UrlAnalyzer
from pi_yo_8.yt_dlp.status_manager import YTDLPInfoType
from pi_yo_8.yt_dlp.unit import YTDLP_GENERAL_PARAMS
from pi_yo_8.yt_dlp.audio_data import YTDLPAudioData

if TYPE_CHECKING:
    from pi_yo_8.main import GuildSession


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


    async def get_current_item(self) -> YTDLPAudioData | None:
        if not self.play_queue:
            return None
        item = self.play_queue[0]
        if isinstance(item, Playlist):
            item = await item.get_current_entry()
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
                if isinstance(item, LazyPlaylist) and not item.decompress_task.done():
                    return items
            else:
                items.append(item)
            if count <= len(items): break
        return items


class MusicController():
    def __init__(self, guild_session: "GuildSession"):
        self.guild_session = guild_session
        self.player_track = guild_session.multi_track_voice_client.add_track(opus=True)
        self.guild = guild_session.guild
        self.queue: MusicQueue = MusicQueue()
        self.status = Status()
        self.last_status = copy.copy(self.status)



    async def enqueue(self, ctx: Context, args):
        _log.info(f"{self.guild.name} : Command:queue {args}")
        # 一時停止していた場合再生 開始
        if args:
            arg = ' '.join(args)
        else:
            self.player_track.resume()
            return

        result = await self._parse_and_extract_source(arg, self.guild_session)
        if not result: return

        # Queueに登録
        self.queue.play_queue.append(result)

        # 再生されるまでループ
        if not self.player_track.has_audio_data():
            await self.play_loop(None, 0)
        self.player_track.resume()



    async def play(self, ctx: Context, args):
        _log.info(f"{self.guild.name} : Command:play {' '.join(args)}")
        # 一時停止していた場合再生 開始
        if args:
            arg = ' '.join(args)
        else:
            self.player_track.resume()
            return

        res = await self._parse_and_extract_source(arg, self.guild_session)
        if not res: return

        if self.queue.play_queue:
            await self._advance_and_update_status(ignore_playlist=True)
        self.queue.play_queue.appendleft(res)

        if isinstance(res, Playlist):
            self.status = res.status
            self.last_status = copy.copy(self.status)

        # 再生されるまでループ
        await self.play_loop(None, 0)
        self.player_track.resume()


    @staticmethod
    async def _parse_and_extract_source(arg: str, guild_session: "GuildSession | None") -> "Playlist | YTDLPAudioData | None":
        print("extract:", arg)
        info_generator, status_manager = YTDLPManager.YT_DLP.get(YTDLP_GENERAL_PARAMS).extract_raw_info(arg, guild_session)
        if info := await anext(info_generator, None):
            if info.get("playlist"):
                analysis = UrlAnalyzer(arg)
                res = LazyPlaylist(info, info_generator, guild_session)
                status_manager._type = YTDLPInfoType.PLAYLIST
                status_manager.name = res.title

                if analysis.is_yt and analysis.list_id:
                    if analysis.video_id:
                        await res.set_next_index_by_video_id(analysis.video_id)
                    else:
                        res.status.set(loop=False, loop_pl=True, random_pl=True)
                print("extract playlist:", arg)
                return res

            if info.get("formats") and info.get("url"):
                print("extract video", arg)
                res = YTDLPAudioData(info, guild_session, None)
                status_manager._type = YTDLPInfoType.VIDEO
                status_manager.name = res.title()
                return res
                
        print("extract None:", arg)
        return None


    async def seek_or_skip(self, skip_input: str | None):
        if self.guild.voice_client:
            if not skip_input:
                await self.skip_tracks()
                return

            try:
                sec = int(skip_input)
            except Exception:
                sec_str_lower = skip_input.lower()
                if res := re_skip.match(sec_str_lower):
                    sec = int(res.group(1))
                    unit_suffix = res.group(3)
                    if unit_suffix == 'h':
                        sec = sec * 3600
                    elif unit_suffix == 'm':
                        sec = sec * 60
                elif res := re_skip_set_h.match(sec_str_lower):
                    sec = int(res.group(3))
                    sec += int(res.group(2)) * 60
                    sec += int(res.group(1)) * 3600
                    sec -= int(self.player_track.timer)
                elif res := re_skip_set_m.match(sec_str_lower):
                    sec = int(res.group(2))
                    sec += int(res.group(1)) * 60
                    sec -= int(self.player_track.timer)
                else: 
                    return
            await self.player_track.seek_by_seconds(sec)


    async def _advance_and_update_status(self, count: int = 1, ignore_playlist: bool = False) -> bool:
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
        res: bool = await self.queue.next(count, ignore_playlist)
        if res:
            data = self.queue.play_queue[0]
            if isinstance(data, LazyPlaylist):
                data.status.set(self.status.loop, self.status.loop_pl, self.status.random_pl)
                self.status = data.status
        return res



    async def skip_tracks(self, count: int = 1):
        if count == 0: return

        res: bool = await self._advance_and_update_status(count)
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
    async def download(arg: str) -> list[Embed] | None:
        # Download Embed
        result = await MusicController._parse_and_extract_source(arg, None)
        if result is None:
            return
        audio_data = result.entries[0] if isinstance(result, Playlist) else result
        await audio_data.check_streaming_data.run()
        if not await audio_data.is_available():
            return

        embed = Embed(title=audio_data.title(), url=audio_data.web_url(), colour=EmbedTemplates.get_main_color())
        embed.set_thumbnail(url=await audio_data.load_thumbnail.run())
        embed.set_author(name=audio_data.ch_name(), url=audio_data.ch_url(), icon_url=await audio_data.load_ch_icon.run())
            
        if audio_data.duration:
            duration_str = format_seconds_to_time(audio_data.duration)
            embed.add_field(name="Length", value=duration_str, inline=True)

            
        table_rows = []
        for f in audio_data.formats():

            download_link = f'[`download`]({f["url"]})`'

            if f.get('width'):
                resolution = f"{f['width']}x{f['height']}"
            elif f.get('resolution'):
                resolution = str(f.get('resolution'))
            else: 
                resolution = ''

            ext = f.get('ext', '')
            acodec = f.get('acodec', '')
            abr = f"{f.get('abr', '?')}k"
            protocol = f.get('protocol', '')


            if '3gpp' in ext:
                continue

            table_rows.append([download_link, ext, protocol, resolution, acodec, abr])

        headers = ['', 'EXT', 'Protocol', 'RES', 'Audio', 'ABR']
        table = tabulate.tabulate(tabular_data=table_rows, headers=headers, tablefmt='github')
        table = re_space.sub(')`|', table)
        table_lines = table.split('\n')
        table_lines[0] = re_space2.sub('', re_space3.sub('[`--------`](https://github.com/Ryukkun/pi-yo_8)`|', table_lines[0]))
        table_lines[1] = re_space2.sub('', re_space3.sub('[`--------`](https://github.com/Ryukkun/pi-yo_8)`|', table_lines[1]))

        embed_list = [embed]
        while table_lines:
            table_content = ''
            embed = Embed(colour=EmbedTemplates.get_main_color())
            while table_lines:
                temp = re_space2.sub('', table_lines[0])
                if len(table_content) + len(temp) + 5 > 4096:
                    break
                table_content += f'{temp}`\n'
                table_lines.pop(0)
                
            embed.description = table_content
            embed_list.append(embed)

        return embed_list
            


#---------------------------------------------------------------------------------------
#   再生 Loop
#---------------------------------------------------------------------------------------
    async def play_loop(self, played=None, played_at_timestamp=0.0):
        """
        再生後に実行される
        """

        if not self.guild.voice_client: return
        loop = asyncio.get_event_loop()

        # Queue削除
        audio_data = await self.queue.get_current_item()
        if audio_data:
            if not self.status.loop and audio_data.stream_url == played or (time.time() - played_at_timestamp) <= 0.2:
                await self._advance_and_update_status()


        # 再生
        if audio_data := await self.queue.get_current_item():
            played_time = time.time()
            _log.info(f"{self.guild.name} : Play {audio_data.web_url()}  volume:{audio_data.get_volume()}  [Now len: {str(len(self.queue.play_queue))}]")

            await self.player_track.play(audio_data, after=lambda: asyncio.run_coroutine_threadsafe(self.play_loop(audio_data.stream_url, played_time), loop))


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
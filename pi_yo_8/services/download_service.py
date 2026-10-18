import re

import tabulate
from discord import Embed

from pi_yo_8.gui.utils import EmbedTemplates, format_seconds_to_time
from pi_yo_8.sources.lazy_playlist import LazyPlaylist, ensure_track_playable
from pi_yo_8.sources.resolver import TrackResolver

re_space = re.compile(r'\)` +?\|')
re_space2 = re.compile(r'(( |-)\|$|^\|( |-))')
re_space3 = re.compile(r'^\|( |-)+?\|')

class DownloadService:
    @staticmethod
    async def create_download_embeds(query: str) -> list[Embed] | None:
        result, _ = await TrackResolver.resolve(query)
        if not result:
            return None

        track = result.entries[0] if isinstance(result, LazyPlaylist) else result
        if not await ensure_track_playable(track):
            return None

        raw = track.raw_info
        embed = Embed(title=track.title, url=track.web_url, colour=EmbedTemplates.get_main_color())
        if track.thumbnail_url:
            embed.set_thumbnail(url=track.thumbnail_url)
        if track.uploader:
            embed.set_author(name=track.uploader, url=track.uploader_url or None)

        if track.duration:
            embed.add_field(name="Length", value=format_seconds_to_time(track.duration), inline=True)

        table_rows = []
        for f in raw.get("formats", []):
            dl_link = f'[`download`]({f.get("url")})`'
            if f.get('width'):
                res = f"{f['width']}x{f['height']}"
            elif f.get('resolution'):
                res = str(f.get('resolution'))
            else:
                res = ''

            ext = f.get('ext', '')
            if '3gpp' in ext:
                continue

            acodec = f.get('acodec', '')
            abr = f"{f.get('abr', '?')}k"
            proto = f.get('protocol', '')
            table_rows.append([dl_link, ext, proto, res, acodec, abr])

        headers = ['', 'EXT', 'Protocol', 'RES', 'Audio', 'ABR']
        table = tabulate.tabulate(tabular_data=table_rows, headers=headers, tablefmt='github')
        table = re_space.sub(')`|', table)
        lines = table.split('\n')
        lines[0] = re_space2.sub('', re_space3.sub('[`--------`](https://github.com/Ryukkun/pi-yo_8)`|', lines[0]))
        lines[1] = re_space2.sub('', re_space3.sub('[`--------`](https://github.com/Ryukkun/pi-yo_8)`|', lines[1]))

        embed_list = [embed]
        while lines:
            content = ''
            page_embed = Embed(colour=EmbedTemplates.get_main_color())
            while lines:
                temp = re_space2.sub('', lines[0])
                if len(content) + len(temp) + 5 > 4096:
                    break
                content += f'{temp}`\n'
                lines.pop(0)
            page_embed.description = content
            embed_list.append(page_embed)

        return embed_list

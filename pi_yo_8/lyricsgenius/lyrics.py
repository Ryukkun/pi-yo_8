import aiohttp
import re

from typing import List
from bs4 import BeautifulSoup

from config import genius_token as token

'''

MIT License

Copyright (c) 2020 John W. Miller

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

一部コード利用
'''
re_lyric_class = re.compile("^lyrics$|Lyrics__Root")
api_header = {'Authorization': f'Bearer {token}'}

class GeniusLyric:
    def __init__(self, title, author, web_url) -> None:
        self.title = title
        self.author = author
        self.web_url = web_url
        self.lyric = None

    @classmethod
    async def from_q(cls, q) ->List['GeniusLyric']:
        # 取得 非同期化
        params = {'q':q}
        async with aiohttp.ClientSession(headers=api_header) as session:
            async with session.get(url='https://api.genius.com/search', params= params) as resp:
                res_json = await resp.json()
        items = res_json.get('response', {}).get('hits', [])
        cls_list = []
        for _ in items:
            _ = _['result']
            cls_list.append(
                cls(title=_['title'],
                    author=_['artist_names'],
                    web_url=f'https://genius.com{_["api_path"]}'
                    )
                )
        return cls_list

    
    # async def lyric(self, song_url=None, song_id=None, q=None):
    #     if song_url:
    #         pass
    #     elif song_id:
    #         pass
    #     elif q:
    #         q = urllib.parse.quote(q)
    #     else:
    #         raise Exception('ちょっと！ 何か指定してよね！')
        

    async def get_lyric(self):
        if self.lyric:
            return self.lyric

        # 取得 非同期化
        async with aiohttp.ClientSession() as session:
            async with session.get(url=self.web_url) as resp:
                html = await resp.text()
        html = BeautifulSoup(
            html.replace('<br/>', '\n'),
            "html.parser"
        )

        # Determine the class of the div
        div = html.find("div", class_=re_lyric_class)
        if div is None:
            print("Couldn't find the lyrics section.\n"
                    "Song URL: {}".format(self.web_url))
            return

        self.lyric = div.get_text()

        # Remove [Verse], [Bridge], etc.
        self.lyric = re.sub(r'(\[.*?\])*', '', self.lyric)
        self.lyric = re.sub(r'^.+?\n', '', self.lyric)
        self.lyric = re.sub(r'(\d+|)Embed$', '', self.lyric)
        #self.lyric = re.sub('\n{2}', '\n', lyrics)  # Gaps between verses
        #self.lyrics = lyrics.strip("\n")
        return self.lyric
    

if __name__ == '__main__':
    async def test():
        res = await GeniusLyric.from_q('轍 japanese')
        print(await res[0].get_lyric())
    import asyncio
    asyncio.run(test())
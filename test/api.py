import asyncio
import aiohttp
import pprint
from pytube.innertube import InnerTube


async def m1():
    youtube_api = 'https://www.googleapis.com/youtube/v3'
    params = {'key':"AIzaSyC4y3-kV00FZ0unvsfEBp7ODyKIjYjxATI", 'part':'contentDetails,status,snippet', 'playlistId':"PLB02wINShjkBKnLfufaEPnCupGO-SK6e4", 'maxResults':'1'}
    url = youtube_api + '/playlistItems'
    async with aiohttp.ClientSession() as session:
        async with session.get(url=url, params=params) as resp:
            text = await resp.json()
            print(text)

async def api_playlist(_id:str):
    """
    YoutubeAPIを使用しプレイリストの情報を取得する
    """
    params = {'key':config.youtube_key, 'part':'contentDetails,status,snippet', 'playlistId':_id, 'maxResults':'50'}
    url = youtube_api + '/playlistItems'
    res: list[StreamAudioData] = []
    i = 0
    loop = True
    async with aiohttp.ClientSession() as session:
        while i <= 1:
            async with session.get(url=url, params=params) as resp:
                text = await resp.json()
                if not text['items']:
                    raise Exception('解析不可能なplaylist')
                total = text['pageInfo']['totalResults']

                for _ in text['items']:
                    i += 1
                    if _['status']['privacyStatus'].lower() == 'private':
                        continue
                    upload_date = _['contentDetails']['videoPublishedAt'][:10].replace('-','/')
                    video_id = _['contentDetails']['videoId']
                    title = _['snippet']['title']
                    res.append(YoutubeAudioData(video_id, upload_date=upload_date, video_id=video_id, title=title))
                    if total == i:
                        break

                if text.get('nextPageToken'):
                    params['pageToken'] = text['nextPageToken']
                else:
                    break


'''
This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or
distribute this software, either in source code form or as a compiled
binary, for any purpose, commercial or non-commercial, and by any
means.

In jurisdictions that recognize copyright laws, the author or authors
of this software dedicate any and all copyright interest in the
software to the public domain. We make this dedication for the benefit
of the public at large and to the detriment of our heirs and
successors. We intend this dedication to be an overt act of
relinquishment in perpetuity of all present and future rights to this
software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

from https://github.com/pytube/pytube/blob/master/LICENSE
'''



import aiohttp
import json

from urllib import parse
from pytube.innertube import InnerTube as old_InnerTube


class InnerTube2(old_InnerTube):
    async def _call_api(self, endpoint, query, data):
        """Make a request to a given endpoint with the provided query parameters and data."""
        # Remove the API key if oauth is being used.
        endpoint_url = f'{endpoint}?{parse.urlencode(query)}'
        headers = {
            'Content-Type': 'application/json',
        }

        return await _execute_request(
            endpoint_url,
            headers=headers,
            data=data
        )
    

    async def player(self, video_id):
        """Make a request to the player endpoint.
        :param str video_id:
            The video id to get player info for.
        :rtype: dict
        :returns:
            Raw player info results.
        """
        endpoint = f'{self.base_url}/player'
        query = {
            'videoId': video_id,
        }
        query.update(self.base_params)
        return await self._call_api(endpoint, query, self.base_data)
    


async def _execute_request(
    url,
    headers=None,
    data=None
):
    base_headers = {"User-Agent": "Mozilla/5.0", "accept-language": "en-US,en"}
    if headers:
        base_headers.update(headers)
    if data:
        # encode data for request
        if not isinstance(data, bytes):
            data = bytes(json.dumps(data), encoding="utf-8")

    async with aiohttp.ClientSession(headers=base_headers) as session:
        async with session.post(url=url, data=data) as resp:
            return await resp.json()

if __name__ == "__main__":
    asyncio.run(m2())
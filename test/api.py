import asyncio
import aiohttp
import pprint
from . import config

youtube_api = 'https://www.googleapis.com/youtube/v3'

async def m1():
    params = {'key':config.youtube_key, 'part':'contentDetails,status,snippet', 'playlistId':"PLB02wINShjkBKnLfufaEPnCupGO-SK6e4", 'maxResults':'1'}
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
    res: list[str] = []
    i = 0
    total = 1
    async with aiohttp.ClientSession() as session:
        while i < total:
            async with session.get(url=url, params=params) as resp:
                text = await resp.json()
                if not text['items']:
                    raise Exception('解析不可能なplaylist')
                total = text['pageInfo']['totalResults']

                print(len(text["items"]))
                for _ in text['items']:
                    i += 1
                    if _['status']['privacyStatus'].lower() == 'private':
                        continue
                    title = _['snippet']['title']
                    res.append(title)
                    if total == i:
                        break

                if text.get('nextPageToken'):
                    params['pageToken'] = text['nextPageToken']
                else:
                    break
    print(res)



if __name__ == "__main__":
    asyncio.run(api_playlist("PLB02wINShjkBKnLfufaEPnCupGO-SK6e4"))
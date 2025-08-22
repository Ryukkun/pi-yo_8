import aiohttp
from pi_yo_8 import config
from pi_yo_8.audio_data import YoutubeAudioData
from pi_yo_8.utils import YoutubeUtil
from pi_yo_8.voice_client import StreamAudioData
from pi_yo_8.extractor.yt_dlp import YTDLPExtractor


class YoutubeAPIExtractor:
    BASE_URL = 'https://www.googleapis.com/youtube/v3'

    @staticmethod
    async def get_channel_icon(ch_id: str) -> str:
        params = {'key':config.youtube_key, 'part':'snippet', 'id':ch_id}
        url = YoutubeAPIExtractor.BASE_URL + '/channels'
        async with aiohttp.ClientSession() as session:
            async with session.get(url=url, params=params) as resp:
                text = await resp.json()
        return text['items'][0]['snippet']['thumbnails']['medium']['url']
    

    @staticmethod
    async def api_playlist(_id:str) -> list['StreamAudioData']:
        """
        YoutubeAPIを使用しプレイリストの情報を取得する
        yt_dlpより早い
        """
        params = {'key':config.youtube_key, 'part':'contentDetails,status,snippet', 'playlistId':_id, 'maxResults':'0'}
        url = YoutubeAPIExtractor.BASE_URL + '/playlistItems'
        res: list[StreamAudioData] = []
        total = 0
        i = 0
        async with aiohttp.ClientSession() as session:
            async with session.get(url=url, params=params) as resp:
                text = await resp.json()
                total = text['pageInfo']['totalResults']
                params['maxResults'] = '50'

            while i < total:
                async with session.get(url=url, params=params) as resp:
                    text = await resp.json()
                    if not text['items']:
                        raise Exception('解析不可能なplaylist')

                    for item in text['items']:
                        i += 1
                        if item['status']['privacyStatus'].lower() == 'private':
                            continue
                        upload_date = item['contentDetails']['videoPublishedAt'][:10].replace('-','/')
                        video_id = item['contentDetails']['videoId']
                        title = item['snippet']['title']
                        res.append(YoutubeAudioData(video_id, YoutubeUtil.get_web_url(video_id), title, upload_date=upload_date, video_id=video_id, title=title))
                        if total == i:
                            break

                    if text.get('nextPageToken'):
                        params['pageToken'] = text['nextPageToken']
                    else:
                        break
        return res

    @classmethod
    async def api_get_viewcounts(video_id:str) -> tuple[str, int, int]:        
        params = {'key':config.youtube_key, 'part':'statistics,snippet', 'id':video_id}
        url = YoutubeAPIExtractor.BASE_URL + '/videos'
        async with aiohttp.ClientSession() as session:
            async with session.get(url=url, params=params) as resp:
                text = await resp.json()
        text = text.get('items',[{}])[0]
        sta = text.get('statistics',{})
        upload_date = text.get('snippet',{}).get('publishedAt')
        upload_date = upload_date[:10].replace('-','/')
        view_count = sta.get('viewCount')
        like_count = sta.get('likeCount')
        return upload_date, view_count, like_count


    @staticmethod
    async def api_search_video(arg:str) -> 'StreamAudioData':
        params = {'key':config.youtube_key, 'part':'id', 'q':arg, 'maxResults':'1'}
        url = YoutubeAPIExtractor.BASE_URL + '/search'
        async with aiohttp.ClientSession() as session:
            async with session.get(url=url, params=params) as resp:
                text = await resp.json()

        video_id = text['items'][0]['id']['videoId']
        return await YTDLPExtractor.load_video(video_id)


    @staticmethod
    async def api_search_playlist(arg:str) -> list['StreamAudioData']:
        #arg = urllib.parse.quote(arg)
        params = {'key':config.youtube_key, 'part':'id,snippet', 'q':arg, 'maxResults':'50', 'type':'video'}
        url = YoutubeAPIExtractor.BASE_URL + '/search'
        async with aiohttp.ClientSession() as session:
            async with session.get(url=url, params=params) as resp:
                text = await resp.json()

        return [
            YoutubeAudioData(_['id']['videoId'],
                 video_id=_['id']['videoId'],
                 title=_['snippet']['title']
                 )
            for _ in text['items']
                ]
import json
import pprint
import yt_dlp
from yt_dlp.utils import orderedSet
from yt_dlp.extractor.youtube._tab import YoutubeTabIE, YoutubeTabBaseInfoExtractor
import time

from yt_dlp.extractor.youtube import YoutubeIE as OldYoutubeIE
from yt_dlp.utils import traverse_obj

class YoutubeIE(OldYoutubeIE):
    """
    Loudnessの値を取得するために、YoutubeIEを拡張
    YoutubeDLをインスタンス化した後に、add_info_extractor()でこのクラスを追加することで有効化される
    """
    def _initial_extract(self, url, smuggled_data, webpage_url, webpage_client, video_id):
        """
        音声データをwebpage_ytcfgに追記
        """
        webpage, webpage_ytcfg, initial_data, is_premium_subscriber, player_responses, player_url = super()._initial_extract(url, smuggled_data, webpage_url, webpage_client, video_id)
        player_configs = traverse_obj(player_responses, (..., "playerConfig"), expected_type=dict)
        
        def find(_:dict):
            return _.get("audioConfig", None)
        
        volume = None
        if isinstance(player_configs, dict):
            volume = find(player_configs)
        elif isinstance(player_configs, list):
            for pc in player_configs:
                volume = find(pc)
                if volume:
                    break

        if volume:
            webpage_ytcfg['volume_data'] = volume
        return webpage, webpage_ytcfg, initial_data, is_premium_subscriber, player_responses, player_url


    def extract_comments(self, *args, **kwargs):
        """
        このメソッドの戻り値はInfo（YoutubeDL.extract_info()の戻り値）のKey["__post_extractor"]に保存される
        """
        volume:dict = args[0].pop("volume_data", None)
        ret = super().extract_comments(*args, **kwargs)
        if volume:
            if ret is None:
                ret = {}
            ret["volume_data"] = volume
        return ret


    def _real_extract(self, url):
        """
        info["volume_data"] <= info["__post_extractor"]["volume_data"]
        """
        info = super()._real_extract(url)
        if isinstance(info, dict) and "__post_extractor" in info and info['__post_extractor']:
            volume = info['__post_extractor'].pop('volume_data', {})
            if volume:
                info['volume_data'] = volume
            
            if not info['__post_extractor']:
                info['__post_extractor'] = None
        return info


#yt_dlp.YoutubeDL({'quiet':True}).extract_info('https://www.youtube.com/watch?v=AqI97zHMoQw&list=PLB02wINShjkBKnLfufaEPnCupGO-SK6e4', download=False)
arg = 'https://www.youtube.com/playlist?list=PLB02wINShjkBKnLfufaEPnCupGO-SK6e4'

def m2():
    url = 'https://music.youtube.com/watch?v=BI9Ue6JwJic&si=xn0a20gOvS3dGuDR'
    now = time.perf_counter()
    with yt_dlp.YoutubeDL({'quiet':False, 'format':'bestaudio/worst', 'noplaylist':True, 'hls_prefer_native':False}) as ydl:
        ydl.add_info_extractor(YoutubeIE())
        print(time.perf_counter() - now)
        now = time.perf_counter()
        vdic = ydl.extract_info(url, False, process=True)

    print(time.perf_counter() - now)
    with open("./video_info.json", "w", encoding="utf-8") as f:
        json.dump(vdic, f, ensure_ascii=False, indent=2)


def main():
    key = 'YoutubeTab'
    ytd = yt_dlp.YoutubeDL()
    ie = ytd._ies[key]
    if not ie.suitable(arg):
        return
    ie:YoutubeTabIE  = ytd.get_info_extractor(key)
    ie_result= ie.extract(arg)
    allEntry = yt_dlp.utils.PlaylistEntries(ytd, ie_result)
    test = allEntry[0]
    i = 0
    for e in ie_result["entries"]:
        print(f"{i} : {e['title']}")
        i += 1
    # entries = orderedSet(allEntry, lazy=True)
    # _, entries = tuple(zip(*list(entries))) or ([], [])
    #print(entries)

from yt_dlp.extractor import gen_extractor_classes
def supported_url(ydl:yt_dlp.YoutubeDL, url: str) -> None:
    for ie in gen_extractor_classes():
        if ie.suitable(url):
            print(ie.__class__.__name__)
            return



def extract():
    # lazy_playlist なんか動かんくて残念
    arg = "https://www.youtube.com/watch?v=cQKGUgOfD8U&list=PLB02wINShjkBKnLfufaEPnCupGO-SK6e4&index=4"
    #arg = "https://www.youtube.com/playlist?&list=PLB02wINShjkBKnLfufaEPnCupGO-SK6e4&index=4"
    #arg = "https://www.nicovideo.jp/mylist/21130988"
    arg = "https://youtu.be/x06wB8UDxMI?si=yEw3s0RAISEH4Iu4"
    arg = "https://www.nicovideo.jp/watch/sm36999938"
    arg = "https://www.youtube.com/watch?v=Y1Nip-y0BcQ&list=PLYITQsyLyAGkqp1e18fF22RbsisWzXazN" #再生不可能なものが入っている
    #arg = "ytsearch50:ディぺっしゅモード"
    #arg = "ytsearch50:ジブリBGM playlist"
    #arg = "じぶりBGM playlist"
    arg = "https://www.youtube.com/channel/UCGmO0S4S-AunjRdmxA6TQYg" # Channel
    now = time.perf_counter()

    _ = yt_dlp.YoutubeDL({"default_search":"ytsearch30", 'format':'bestaudio/worst', 'extract_flat': "in_playlist", 'skip_download': True})
    supported_url(_, arg)
    print(time.perf_counter() - now)
    __ = _.extract_info(arg, download=False, process=False)
    print(time.perf_counter() - now)
    print(__)
    with open("./test/video_info.json", "w", encoding="utf-8") as f:
        json.dump(__, f, ensure_ascii=False, indent=2)



if __name__ == "__main__":
    extract()
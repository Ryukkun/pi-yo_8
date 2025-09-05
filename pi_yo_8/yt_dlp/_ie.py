from typing import Any
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


    def extract_comments(self, *args, **kwargs): # type: ignore
        """
        このメソッドの戻り値はInfo（YoutubeDL.extract_info()の戻り値）のKey["__post_extractor"]に保存される
        """
        volume = args[0].pop("volume_data", None)
        ret = [super().extract_comments(*args, **kwargs)]
        if volume:
            ret.append(volume)
        return ret


    def _real_extract(self, url):
        """
        info["volume_data"] <= info["__post_extractor"]["volume_data"]
        """
        info:dict[str, list[Any]] = super()._real_extract(url)
        if isinstance(info, dict) and "__post_extractor" in info and len(info['__post_extractor']) == 2:
            _ = info['__post_extractor'][0]
            info['volume_data'] = info['__post_extractor'][1]
            info['__post_extractor'] = _
        return info
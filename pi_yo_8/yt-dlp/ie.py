from yt_dlp.extractor.youtube import YoutubeIE as OldYoutubeIE
from yt_dlp.utils import traverse_obj

class YoutubeIE(OldYoutubeIE):
    def _initial_extract(self, url, smuggled_data, webpage_url, webpage_client, video_id):
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
        volume:dict = args[0].pop("volume_data", None)
        ret = super().extract_comments(*args, **kwargs)
        if ret is None:
            ret = {}
        ret["volume_data"] = volume
        return ret


    def _real_extract(self, url):
        info = super()._real_extract(url)
        if isinstance(info, dict) and "__post_extractor" in info and info['__post_extractor']:
            volume = info['__post_extractor'].pop('volume_data', {})
            if volume:
                info['volume_data'] = volume
            
            if not info['__post_extractor']:
                info['__post_extractor'] = None
        return info
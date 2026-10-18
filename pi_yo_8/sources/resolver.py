from pi_yo_8.core.track import Track
from pi_yo_8.core.url import UrlAnalyzer
from pi_yo_8.sources.extractor import YTDLP_GENERAL_PARAMS
from pi_yo_8.sources.lazy_playlist import LazyPlaylist
from pi_yo_8.sources.manager import YTDLPManager
from pi_yo_8.sources.mapper import map_info_to_track
from pi_yo_8.sources.status import StatusManager, YTDLPInfoType


class TrackResolver:
    @staticmethod
    async def resolve(query_or_url: str) -> tuple[Track | LazyPlaylist | None, StatusManager | None]:
        extractor = YTDLPManager.YT_DLP.get(YTDLP_GENERAL_PARAMS)
        gen, status_manager = extractor.extract_raw_info(query_or_url)

        async for info in gen:
            if info.get("playlist"):
                analysis = UrlAnalyzer(query_or_url)
                playlist = LazyPlaylist(info, gen)
                status_manager._type = YTDLPInfoType.PLAYLIST
                status_manager.name = playlist.title

                if analysis.is_yt and analysis.list_id:
                    if analysis.video_id:
                        playlist.set_next_index_by_id(analysis.video_id)
                    else:
                        playlist.status.set(loop=False, loop_pl=True, random_pl=True)
                return playlist, status_manager

            if info.get("formats") and info.get("url"):
                track = map_info_to_track(info)
                status_manager._type = YTDLPInfoType.VIDEO
                status_manager.name = track.title
                return track, status_manager

        return None, status_manager

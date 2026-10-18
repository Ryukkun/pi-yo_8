import logging

from collections.abc import Callable
from pi_yo_8.core.track import Track
from pi_yo_8.core.url import UrlAnalyzer
from pi_yo_8.sources.extractor import YTDLP_GENERAL_PARAMS
from pi_yo_8.sources.lazy_playlist import LazyPlaylist
from pi_yo_8.sources.manager import YTDLPManager
from pi_yo_8.sources.mapper import map_info_to_track
from pi_yo_8.sources.status import StatusManager, YTDLPInfoType

_log = logging.getLogger(__name__)


class TrackResolver:
    @staticmethod
    async def resolve(
        query_or_url: str,
        on_status: Callable[[StatusManager], None] | None = None,
    ) -> tuple[Track | LazyPlaylist | None, StatusManager | None]:
        _log.info(f"Resolving query: '{query_or_url}'")
        extractor = YTDLPManager.get_extractor(YTDLP_GENERAL_PARAMS)
        gen, status_manager = extractor.extract_raw_info(query_or_url)
        if on_status:
            on_status(status_manager)

        async for info in gen:
            if info.get("playlist"):
                analysis = UrlAnalyzer(query_or_url)
                playlist = LazyPlaylist(info, gen, on_status=on_status)
                status_manager._type = YTDLPInfoType.PLAYLIST
                status_manager.name = playlist.title
                if on_status:
                    on_status(status_manager)
                _log.info(f"Resolved playlist: '{playlist.title}' (entries: {len(playlist.entries)})")

                if analysis.is_yt and analysis.list_id:
                    if analysis.video_id:
                        await playlist.set_next_index_by_video_id(analysis.video_id)
                    else:
                        playlist.status.set(loop=False, loop_pl=True, random_pl=True)
                return playlist, status_manager

            track = map_info_to_track(info)
            status_manager._type = YTDLPInfoType.VIDEO
            status_manager.name = track.title
            if on_status:
                on_status(status_manager)
            _log.info(f"Resolved single track: '{track.title}' (stream_ready: {track.is_stream_ready()})")
            return track, status_manager

        _log.warning(f"Could not resolve any tracks for query: '{query_or_url}'")
        return None, status_manager


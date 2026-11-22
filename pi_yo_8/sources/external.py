import json
import logging
from collections.abc import Callable
from typing import Any

import aiohttp
from bs4 import BeautifulSoup

from pi_yo_8.core.track import Track
from pi_yo_8.core.url import UrlAnalyzer
from pi_yo_8.sources.lazy_playlist import LazyPlaylist
from pi_yo_8.sources.status import ErrorMessage, ErrorType, StatusManager, YTDLPInfoType

_log = logging.getLogger(__name__)

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
}


def _format_apple_artwork(artwork: dict[str, Any] | None, size: int = 600) -> str | None:
    if not isinstance(artwork, dict):
        return None
    url_tpl = artwork.get("dictionary", {}).get("url")
    if not isinstance(url_tpl, str) or not url_tpl:
        return None
    return (
        url_tpl.replace("{w}", str(size))
        .replace("{h}", str(size))
        .replace("{c}", "bb")
        .replace("{f}", "jpg")
    )


def _extract_spotify_cover_url(entity: dict[str, Any]) -> str | None:
    cover_art = entity.get("coverArt")
    if isinstance(cover_art, dict):
        sources = cover_art.get("sources")
        if isinstance(sources, list) and sources:
            for src in sources:
                if isinstance(src, dict) and (url := src.get("url")):
                    return str(url)
    return None


def _build_external_track(
    *,
    track_id: str | None,
    title: str,
    artist: str | None,
    web_url: str,
    duration_sec: float | None,
    thumbnail_url: str | None,
    source: str,
    playlist_title: str | None = None,
) -> Track:
    clean_title = title.strip() or "No Title"
    clean_artist = artist.replace("\xa0", " ").strip() if artist else ""
    search_query = f"{clean_artist} - {clean_title}" if clean_artist else clean_title
    return Track(
        id=track_id,
        title=clean_title,
        web_url=web_url,
        duration=duration_sec,
        uploader=clean_artist or None,
        thumbnail_url=thumbnail_url,
        playlist_title=playlist_title,
        raw_info={
            "search_query": search_query,
            "external_source": source,
        },
    )


def parse_spotify_embed_html(
    html: str, source_url: str
) -> Track | tuple[str, str, list[Track]] | None:
    """Spotify Embed ページの HTML (__NEXT_DATA__) から楽曲またはプレイリストを抽出する"""
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", {"id": "__NEXT_DATA__"})
    if not script or not script.string:
        return None

    data = json.loads(script.string)
    entity = (
        data.get("props", {})
        .get("pageProps", {})
        .get("state", {})
        .get("data", {})
        .get("entity", {})
    )
    if not isinstance(entity, dict) or not entity:
        return None

    entity_type = entity.get("type")
    thumbnail_url = _extract_spotify_cover_url(entity)

    if entity_type == "track":
        title = str(entity.get("name") or entity.get("title") or "No Title")
        artists_raw = entity.get("artists") or []
        artists = [str(a.get("name")) for a in artists_raw if isinstance(a, dict) and a.get("name")]
        artist_str = ", ".join(artists)
        duration_ms = entity.get("duration")
        duration_sec = float(duration_ms) / 1000.0 if isinstance(duration_ms, (int, float)) else None
        track_id = str(entity.get("id")) if entity.get("id") else None
        return _build_external_track(
            track_id=track_id,
            title=title,
            artist=artist_str,
            web_url=source_url,
            duration_sec=duration_sec,
            thumbnail_url=thumbnail_url,
            source="spotify",
        )

    if entity_type in ("playlist", "album", "artist"):
        pl_title = str(entity.get("name") or entity.get("title") or "Spotify")
        pl_subtitle = str(entity.get("subtitle") or "")
        track_list = entity.get("trackList") or []
        tracks: list[Track] = []
        for item in track_list:
            if not isinstance(item, dict):
                continue
            t_title = str(item.get("title") or "No Title")
            t_artist = str(item.get("subtitle") or "").replace("\xa0", " ").strip()
            if not t_artist:
                if entity_type == "album" and pl_subtitle:
                    t_artist = pl_subtitle
                elif entity_type == "artist":
                    t_artist = pl_title

            t_uri = str(item.get("uri") or "")
            t_id = t_uri.split(":")[-1] if ":" in t_uri else (str(item["uid"]) if item.get("uid") else None)
            t_web_url = f"https://open.spotify.com/track/{t_id}" if t_id else source_url
            t_dur_ms = item.get("duration")
            t_dur_sec = float(t_dur_ms) / 1000.0 if isinstance(t_dur_ms, (int, float)) else None

            tracks.append(
                _build_external_track(
                    track_id=t_id,
                    title=t_title,
                    artist=t_artist,
                    web_url=t_web_url,
                    duration_sec=t_dur_sec,
                    thumbnail_url=thumbnail_url,
                    source="spotify",
                    playlist_title=pl_title,
                )
            )
        if tracks:
            return pl_title, source_url, tracks

    return None


def _extract_subtitle_artists(item: dict[str, Any]) -> str:
    links = item.get("subtitleLinks")
    if isinstance(links, list):
        names = [str(link.get("title")) for link in links if isinstance(link, dict) and link.get("title")]
        if names:
            return ", ".join(names)
    return ""


def parse_apple_music_html(
    html: str, source_url: str, song_id: str | None = None
) -> Track | tuple[str, str, list[Track]] | None:
    """Apple Music ページの HTML (serialized-server-data) から楽曲またはプレイリストを抽出する"""
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", {"id": "serialized-server-data"})
    if not script or not script.string:
        return None

    data = json.loads(script.string)
    data_list = data.get("data")
    if not isinstance(data_list, list) or not data_list:
        return None

    d0 = data_list[0].get("data", {})
    sections = d0.get("sections") or []

    # 単曲直リンクページ (/song/...) または ミュージックビデオ (/music-video/...) の判定
    for section in sections:
        kind = section.get("itemKind")
        items = section.get("items") or []
        if kind == "songDetailHeader" and items:
            item0 = items[0]
            title = str(item0.get("title") or "No Title")
            artist = str(item0.get("artists") or "")
            if not artist:
                for s in sections:
                    if (
                        s.get("itemKind") == "songDetailItemLockup"
                        and s.get("items")
                        and (found_artist := s["items"][0].get("artistName"))
                    ):
                        artist = str(found_artist)
                        break
            cd = item0.get("contentDescriptor") or {}
            track_id = cd.get("identifiers", {}).get("storeAdamID")
            web_url = cd.get("url") or source_url
            thumb = _format_apple_artwork(item0.get("artwork"))
            return _build_external_track(
                track_id=str(track_id) if track_id else None,
                title=title,
                artist=artist,
                web_url=str(web_url),
                duration_sec=None,
                thumbnail_url=thumb,
                source="apple_music",
            )
        if kind == "tvMovieDetailHeaderLockup" and items:
            item0 = items[0]
            title = str(item0.get("title") or "No Title")
            artist = _extract_subtitle_artists(item0)
            cd = item0.get("contentDescriptor") or {}
            track_id = cd.get("identifiers", {}).get("storeAdamID")
            web_url = cd.get("url") or source_url
            thumb = _format_apple_artwork(item0.get("artwork"))
            return _build_external_track(
                track_id=str(track_id) if track_id else None,
                title=title,
                artist=artist,
                web_url=str(web_url),
                duration_sec=None,
                thumbnail_url=thumb,
                source="apple_music",
            )

    # アーティストページ (/artist/...) の判定
    artist_name: str | None = None
    artist_thumb: str | None = None
    artist_tracks: list[Track] = []
    for section in sections:
        kind = section.get("itemKind")
        items = section.get("items") or []
        if kind == "artistDetailHeader" and items:
            header = items[0]
            artist_name = str(header.get("title") or "Artist")
            artist_thumb = _format_apple_artwork(
                header.get("artwork") or header.get("circleArtwork") or header.get("fallbackArtwork")
            )
        elif kind == "artistFeaturedContentAndTracks" and items and artist_name:
            raw_tracks = items[0].get("tracks") or []
            for t in raw_tracks:
                if not isinstance(t, dict):
                    continue
                t_title = str(t.get("title") or "No Title")
                t_dur_ms = t.get("duration")
                t_dur_sec = float(t_dur_ms) / 1000.0 if isinstance(t_dur_ms, (int, float)) else None
                cd = t.get("contentDescriptor") or {}
                t_id = cd.get("identifiers", {}).get("storeAdamID") or t.get("id")
                t_id_str = str(t_id) if t_id is not None else None
                t_url = str(cd.get("url") or source_url)
                t_thumb = _format_apple_artwork(t.get("artwork")) or artist_thumb
                artist_tracks.append(
                    _build_external_track(
                        track_id=t_id_str,
                        title=t_title,
                        artist=artist_name,
                        web_url=t_url,
                        duration_sec=t_dur_sec,
                        thumbnail_url=t_thumb,
                        source="apple_music",
                        playlist_title=artist_name,
                    )
                )
    if artist_name and artist_tracks:
        return artist_name, source_url, artist_tracks

    # プレイリスト / アルバム / see-all トップソングページ
    seo_title = str(d0.get("seoData", {}).get("pageTitle") or "").replace("\xa0", " ")
    fallback_title = seo_title.removesuffix("- Apple Music").strip() if seo_title else "Apple Music"
    pl_title = fallback_title or "Apple Music"
    pl_artist = ""
    pl_thumb: str | None = None
    tracks: list[Track] = []

    for section in sections:
        kind = section.get("itemKind")
        items = section.get("items") or []
        if kind == "containerDetailHeaderLockup" and items:
            header = items[0]
            pl_title = str(header.get("title") or pl_title)
            pl_artist = _extract_subtitle_artists(header)
            pl_thumb = _format_apple_artwork(header.get("artwork"))
        elif kind == "trackLockup" and items:
            for item in items:
                if not isinstance(item, dict):
                    continue
                t_title = str(item.get("title") or "No Title")
                t_artist = str(item.get("artistName") or "") or _extract_subtitle_artists(item) or pl_artist
                t_dur_ms = item.get("duration")
                t_dur_sec = float(t_dur_ms) / 1000.0 if isinstance(t_dur_ms, (int, float)) else None
                cd = item.get("contentDescriptor") or {}
                t_id = cd.get("identifiers", {}).get("storeAdamID") or item.get("id")
                t_id_str = str(t_id) if t_id is not None else None
                t_url = str(cd.get("url") or source_url)
                t_thumb = _format_apple_artwork(item.get("artwork")) or pl_thumb
                tracks.append(
                    _build_external_track(
                        track_id=t_id_str,
                        title=t_title,
                        artist=t_artist,
                        web_url=t_url,
                        duration_sec=t_dur_sec,
                        thumbnail_url=t_thumb,
                        source="apple_music",
                        playlist_title=pl_title,
                    )
                )

    if not tracks:
        return None

    # アルバムURLに ?i={song_id} が付いている場合は単曲として扱う
    if song_id:
        for track in tracks:
            if track.id == song_id:
                track.playlist_title = None
                return track

    return pl_title, source_url, tracks


async def _fetch_page(url: str) -> tuple[str, str]:
    timeout = aiohttp.ClientTimeout(total=15)
    async with (
        aiohttp.ClientSession(headers=_DEFAULT_HEADERS, timeout=timeout) as session,
        session.get(url, allow_redirects=True) as resp,
    ):
        resp.raise_for_status()
        html = await resp.text()
        return str(resp.url), html


class ExternalMusicResolver:
    """Spotify / Apple Music の URL からメタデータを抽出して Track / LazyPlaylist を生成する"""

    @staticmethod
    async def resolve(
        url: str,
        analysis: UrlAnalyzer,
        on_status: Callable[[StatusManager], None] | None = None,
    ) -> tuple[Track | LazyPlaylist | None, StatusManager]:
        status_manager = StatusManager(url)
        if on_status:
            on_status(status_manager)

        try:
            parsed: Track | tuple[str, str, list[Track]] | None = None

            if analysis.is_spotify:
                target_analysis = analysis
                canonical_url = url
                if analysis.is_spotify_short or not (analysis.spotify_type and analysis.spotify_id):
                    resolved_url, _ = await _fetch_page(url)
                    canonical_url = resolved_url
                    target_analysis = UrlAnalyzer(resolved_url)

                if target_analysis.spotify_type and target_analysis.spotify_id:
                    embed_url = (
                        f"https://open.spotify.com/embed/{target_analysis.spotify_type}/{target_analysis.spotify_id}"
                    )
                    _, html = await _fetch_page(embed_url)
                    parsed = parse_spotify_embed_html(html, canonical_url)

            elif analysis.is_apple_music:
                final_url, html = await _fetch_page(url)
                final_analysis = UrlAnalyzer(final_url)
                parsed = parse_apple_music_html(
                    html,
                    final_url,
                    song_id=analysis.apple_song_id or final_analysis.apple_song_id,
                )

            if isinstance(parsed, Track):
                status_manager.info_type = YTDLPInfoType.VIDEO
                status_manager.name = parsed.title
                _log.info(f"Resolved external track: '{parsed.title}' ({parsed.uploader})")
                return parsed, status_manager

            if isinstance(parsed, tuple):
                pl_title, pl_url, tracks = parsed
                playlist = LazyPlaylist.from_tracks(pl_title, pl_url, tracks, on_status=on_status)
                status_manager.info_type = YTDLPInfoType.PLAYLIST
                status_manager.name = playlist.title
                _log.info(f"Resolved external playlist: '{playlist.title}' (entries: {len(playlist.entries)})")
                return playlist, status_manager

            status_manager.append_error(
                ErrorMessage(ErrorType.ERROR, "プレイリストまたは楽曲情報を取得できませんでした。")
            )
            _log.warning(f"Could not parse external music URL: '{url}'")
            return None, status_manager

        except Exception as e:
            _log.error(f"Failed to resolve external music URL '{url}': {e}", exc_info=True)
            status_manager.append_error(ErrorMessage(ErrorType.ERROR, str(e), type(e).__name__))
            return None, status_manager
        finally:
            status_manager.is_running = False
            if on_status:
                on_status(status_manager)

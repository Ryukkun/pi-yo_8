import json
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from pi_yo_8.core.track import Track
from pi_yo_8.core.url import UrlAnalyzer
from pi_yo_8.sources.external import parse_apple_music_html, parse_spotify_embed_html
from pi_yo_8.sources.extractor import YTDLP_SEARCH_PARAMS
from pi_yo_8.sources.lazy_playlist import LazyPlaylist, _do_extract_stream
from pi_yo_8.sources.status import StatusManager


def _wrap_spotify_html(entity: dict[str, Any]) -> str:
    payload = {"props": {"pageProps": {"state": {"data": {"entity": entity}}}}}
    return f'<html><head><script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script></head></html>'


def _wrap_apple_html(sections: list[dict[str, Any]]) -> str:
    payload = {"data": [{"data": {"sections": sections}}]}
    return f'<html><head><script id="serialized-server-data" type="application/json">{json.dumps(payload)}</script></head></html>'


def test_url_analyzer_spotify():
    pl = UrlAnalyzer("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=abc")
    assert pl.is_spotify
    assert not pl.is_spotify_short
    assert not pl.is_yt
    assert not pl.is_apple_music
    assert pl.spotify_type == "playlist"
    assert pl.spotify_id == "37i9dQZF1DXcBWIGoYBM5M"

    intl_track = UrlAnalyzer("https://open.spotify.com/intl-ja/track/4cOdK2wGLETKBW3PvgPWqT")
    assert intl_track.is_spotify
    assert intl_track.spotify_type == "track"
    assert intl_track.spotify_id == "4cOdK2wGLETKBW3PvgPWqT"

    album = UrlAnalyzer("https://open.spotify.com/album/4aawyAB9vmqN3uQ7FjRGTy")
    assert album.is_spotify
    assert album.spotify_type == "album"
    assert album.spotify_id == "4aawyAB9vmqN3uQ7FjRGTy"

    short = UrlAnalyzer("https://spotify.link/abc123XYZ")
    assert short.is_spotify
    assert short.is_spotify_short
    assert short.spotify_id is None


def test_url_analyzer_apple_music():
    pl = UrlAnalyzer("https://music.apple.com/jp/playlist/todays-hits/pl.f4d106fed2bd41149aaacabb233eb5eb")
    assert pl.is_apple_music
    assert not pl.is_spotify
    assert not pl.is_yt
    assert pl.apple_type == "playlist"
    assert pl.apple_id == "pl.f4d106fed2bd41149aaacabb233eb5eb"
    assert pl.apple_song_id is None

    album_song = UrlAnalyzer("https://music.apple.com/jp/album/stupid-song/1889992111?i=1889992115")
    assert album_song.is_apple_music
    assert album_song.apple_type == "album"
    assert album_song.apple_id == "1889992111"
    assert album_song.apple_song_id == "1889992115"

    direct_song = UrlAnalyzer("https://music.apple.com/us/song/never-gonna-give-you-up/155992233")
    assert direct_song.is_apple_music
    assert direct_song.apple_type == "song"
    assert direct_song.apple_id == "155992233"


def test_parse_spotify_track():
    html = _wrap_spotify_html(
        {
            "type": "track",
            "id": "4cOdK2wGLETKBW3PvgPWqT",
            "name": "Never Gonna Give You Up",
            "artists": [{"name": "Rick Astley"}],
            "duration": 213000,
        }
    )
    res = parse_spotify_embed_html(html, "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT")
    assert isinstance(res, Track)
    assert res.id == "4cOdK2wGLETKBW3PvgPWqT"
    assert res.title == "Never Gonna Give You Up"
    assert res.uploader == "Rick Astley"
    assert res.duration == 213.0
    assert res.raw_info["search_query"] == "Rick Astley - Never Gonna Give You Up"


def test_parse_spotify_playlist_and_album():
    html = _wrap_spotify_html(
        {
            "type": "playlist",
            "name": "Today's Top Hits",
            "subtitle": "Spotify",
            "coverArt": {"sources": [{"url": "https://i.scdn.co/image/cover123"}]},
            "trackList": [
                {
                    "uri": "spotify:track:111",
                    "title": "Song One",
                    "subtitle": "Artist A,\xa0Artist B",
                    "duration": 180000,
                },
                {
                    "uri": "spotify:track:222",
                    "title": "Song Two",
                    "subtitle": "Artist C",
                    "duration": 200500,
                },
            ],
        }
    )
    res = parse_spotify_embed_html(html, "https://open.spotify.com/playlist/abc")
    assert isinstance(res, tuple)
    title, url, tracks = res
    assert title == "Today's Top Hits"
    assert url == "https://open.spotify.com/playlist/abc"
    assert len(tracks) == 2
    assert tracks[0].uploader == "Artist A, Artist B"
    assert tracks[0].thumbnail_url == "https://i.scdn.co/image/cover123"
    assert tracks[0].web_url == "https://open.spotify.com/track/111"
    assert tracks[0].raw_info["search_query"] == "Artist A, Artist B - Song One"
    assert tracks[1].duration == 200.5


def test_parse_apple_music_playlist_and_album_song():
    sections = [
        {
            "itemKind": "containerDetailHeaderLockup",
            "items": [
                {
                    "title": "Test Album",
                    "subtitleLinks": [{"title": "Main Artist"}],
                    "artwork": {"dictionary": {"url": "https://example.com/{w}x{h}bb.{f}"}},
                }
            ],
        },
        {
            "itemKind": "trackLockup",
            "items": [
                {
                    "title": "Track 1",
                    "artistName": "Artist 1",
                    "duration": 195000,
                    "contentDescriptor": {
                        "identifiers": {"storeAdamID": "1001"},
                        "url": "https://music.apple.com/jp/album/track-1/999?i=1001",
                    },
                },
                {
                    "title": "Track 2",
                    "artistName": None,
                    "duration": 210000,
                    "contentDescriptor": {
                        "identifiers": {"storeAdamID": "1002"},
                        "url": "https://music.apple.com/jp/album/track-2/999?i=1002",
                    },
                },
            ],
        },
    ]
    html = _wrap_apple_html(sections)

    # アルバム全体として取得
    album_res = parse_apple_music_html(html, "https://music.apple.com/jp/album/test/999")
    assert isinstance(album_res, tuple)
    pl_title, _, tracks = album_res
    assert pl_title == "Test Album"
    assert len(tracks) == 2
    assert tracks[0].thumbnail_url == "https://example.com/600x600bb.jpg"
    assert tracks[1].uploader == "Main Artist"
    assert tracks[1].raw_info["search_query"] == "Main Artist - Track 2"

    # ?i=1002 指定で単曲抽出
    single_res = parse_apple_music_html(html, "https://music.apple.com/jp/album/test/999?i=1002", song_id="1002")
    assert isinstance(single_res, Track)
    assert single_res.id == "1002"
    assert single_res.title == "Track 2"


def test_parse_apple_music_direct_song():
    sections = [
        {
            "itemKind": "songDetailHeader",
            "items": [
                {
                    "title": "Direct Song",
                    "artists": "Direct Artist",
                    "artwork": {"dictionary": {"url": "https://example.com/{w}x{h}bb.{f}"}},
                    "contentDescriptor": {
                        "identifiers": {"storeAdamID": "5555"},
                        "url": "https://music.apple.com/jp/album/direct-song/4444?i=5555",
                    },
                }
            ],
        }
    ]
    html = _wrap_apple_html(sections)
    res = parse_apple_music_html(html, "https://music.apple.com/jp/song/direct-song/5555")
    assert isinstance(res, Track)
    assert res.id == "5555"
    assert res.title == "Direct Song"
    assert res.uploader == "Direct Artist"
    assert res.thumbnail_url == "https://example.com/600x600bb.jpg"
    assert res.raw_info["search_query"] == "Direct Artist - Direct Song"


@pytest.mark.asyncio
async def test_lazy_playlist_from_tracks_and_extract_external():
    t1 = Track(
        id="sp1",
        title="Original Spotify Title",
        web_url="https://open.spotify.com/track/sp1",
        duration=200.0,
        uploader="Original Artist",
        thumbnail_url=None,
        raw_info={"search_query": "Original Artist - Original Spotify Title", "external_source": "spotify"},
    )
    pl = LazyPlaylist.from_tracks("My Playlist", "https://open.spotify.com/playlist/xyz", [t1])
    assert pl.decompress_task.done()
    assert len(pl.entries) == 1
    await pl.update_next_indexes()
    assert len(pl.next_indexes) == 25
    assert pl.next_indexes[0] == 0

    async def fake_gen() -> AsyncGenerator[dict[str, Any]]:
        yield {
            "id": "yt123",
            "title": "YouTube Video Title",
            "webpage_url": "https://www.youtube.com/watch?v=yt123",
            "url": "https://rr1---sn.googlevideo.com/videoplayback",
            "formats": [{"url": "https://rr1---sn.googlevideo.com/videoplayback", "acodec": "opus"}],
            "thumbnails": [{"url": "https://i.ytimg.com/vi/yt123/hqdefault.jpg"}],
            "uploader": "YouTube Uploader",
            "duration": 205,
        }

    mock_extractor = MagicMock()
    mock_extractor.extract_raw_info.return_value = (fake_gen(), StatusManager("ytsearch1:Original Artist - Original Spotify Title"))

    with patch("pi_yo_8.sources.lazy_playlist.YTDLPManager.get_extractor", return_value=mock_extractor) as mock_get_ext:
        ok = await _do_extract_stream(t1)

    assert ok is True
    mock_get_ext.assert_called_once_with(YTDLP_SEARCH_PARAMS)
    mock_extractor.extract_raw_info.assert_called_once_with("ytsearch1:Original Artist - Original Spotify Title")
    assert t1.is_stream_ready()
    # 元のSpotifyメタデータは保持され、欠損サムネイルのみ補完される
    assert t1.title == "Original Spotify Title"
    assert t1.uploader == "Original Artist"
    assert t1.web_url == "https://open.spotify.com/track/sp1"
    assert t1.duration == 200.0
    assert t1.thumbnail_url == "https://i.ytimg.com/vi/yt123/hqdefault.jpg"

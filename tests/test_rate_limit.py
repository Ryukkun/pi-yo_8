from unittest.mock import MagicMock, patch

import pytest

from pi_yo_8.core.track import Track
from pi_yo_8.services.player_service import PlayerService
from pi_yo_8.sources.extractor import YTDLPExtractor, YTDLPRateLimiter
from pi_yo_8.sources.lazy_playlist import LazyPlaylist
from pi_yo_8.sources.status import ErrorType, StatusManager


def test_rate_limiter_allows_within_window_and_blocks_over_limit():
    now = 100.0
    limiter = YTDLPRateLimiter(
        max_requests=3,
        window_seconds=10.0,
        cooldown_seconds=5.0,
        clock=lambda: now,
    )

    assert limiter.allow_request() == (True, 0.0)
    now += 1.0
    assert limiter.allow_request() == (True, 0.0)
    now += 1.0
    assert limiter.allow_request() == (True, 0.0)

    # 4回目で閾値超過 -> クールダウン開始
    allowed, retry_after = limiter.allow_request()
    assert allowed is False
    assert retry_after == pytest.approx(5.0)

    # クールダウン中はNG
    now += 3.0
    allowed, retry_after = limiter.allow_request()
    assert allowed is False
    assert retry_after == pytest.approx(2.0)

    # クールダウン終了後は再び許可
    now += 2.0
    assert limiter.allow_request() == (True, 0.0)


def test_rate_limiter_sliding_window_expires_old_requests():
    now = 100.0
    limiter = YTDLPRateLimiter(
        max_requests=2,
        window_seconds=10.0,
        cooldown_seconds=5.0,
        clock=lambda: now,
    )

    assert limiter.allow_request()[0] is True
    now += 6.0
    assert limiter.allow_request()[0] is True

    # 10秒経過して最初のリクエストがウィンドウ外に出たので許可される
    now += 5.0
    assert limiter.allow_request()[0] is True


@pytest.mark.asyncio
async def test_extractor_returns_rate_limit_error_without_sending_to_process():
    now = 0.0
    limiter = YTDLPRateLimiter(max_requests=1, window_seconds=10.0, cooldown_seconds=8.0, clock=lambda: now)

    with patch.object(YTDLPExtractor, "_start_process", return_value=None):
        extractor = YTDLPExtractor({}, rate_limiter=limiter)
        extractor.connection = MagicMock()
        extractor.connection.poll.return_value = False
        extractor.process = MagicMock()
        extractor.process.is_alive.return_value = True

        # 1回目は許可され、パイプへ送信される
        gen1, sm1 = extractor.extract_raw_info("https://www.youtube.com/watch?v=test1")
        assert sm1.is_rate_limited is False
        extractor.connection.send.assert_called_once_with("https://www.youtube.com/watch?v=test1")
        extractor.connection.poll.return_value = True
        extractor.connection.recv.return_value = ""
        await gen1.aclose()

        # 2回目はレート制限でNG: パイプへ送信されず、エラーが記録される
        extractor.connection.send.reset_mock()
        gen2, sm2 = extractor.extract_raw_info("https://www.youtube.com/watch?v=test2")
        assert extractor.is_running is False
        assert sm2.is_running is False
        assert sm2.is_rate_limited is True
        extractor.connection.send.assert_not_called()

        items = [item async for item in gen2]
        assert items == []
        errors = sm2.get_errors()
        assert len(errors) == 1
        assert errors[0].type == ErrorType.ERROR
        assert errors[0].name == "RateLimitError"


@pytest.mark.asyncio
async def test_lazy_playlist_stops_without_skipping_when_rate_limited():
    async def empty_gen():
        if False:
            yield {}

    first_entry = {
        "id": "vid1",
        "title": "Song 1",
        "url": "https://www.youtube.com/watch?v=vid1",
        "duration": 180,
        "playlist_title": "Test Playlist",
        "playlist_webpage_url": "https://www.youtube.com/playlist?list=PL1",
    }
    pl = LazyPlaylist(first_entry, empty_gen())
    await pl.decompress_task
    pl.entries.append(Track(id="vid2", title="Song 2", web_url="https://www.youtube.com/watch?v=vid2"))
    pl.status.set(loop_pl=False)
    await pl.update_next_indexes()
    assert list(pl.next_indexes) == [0, 1]

    async def fake_rate_limited_gen():
        if False:
            yield {}

    sm = StatusManager("https://www.youtube.com/watch?v=vid1")
    sm.is_running = False
    sm.is_rate_limited = True

    mock_extractor = MagicMock()
    mock_extractor.extract_raw_info.return_value = (fake_rate_limited_gen(), sm)

    with patch("pi_yo_8.sources.lazy_playlist.YTDLPManager.get_extractor", return_value=mock_extractor):
        track = await pl.get_current_track()

    assert track is None
    assert pl.entries[0].rate_limited is True
    # スキップがキャンセルされ、現在位置が0のまま維持される
    assert list(pl.next_indexes) == [0, 1]
    assert len(pl.play_history) == 0


@pytest.mark.asyncio
async def test_player_service_stops_playback_without_skipping_on_rate_limit():
    mock_audio = MagicMock()
    mock_audio.has_audio_data.return_value = False
    service = PlayerService("TestGuild", mock_audio)

    t1 = Track(id="vid1", title="Song 1", web_url="https://www.youtube.com/watch?v=vid1")
    t2 = Track(id="vid2", title="Song 2", web_url="https://www.youtube.com/watch?v=vid2")
    service.queue.play_queue.extend([t1, t2])

    async def fake_rate_limited_gen():
        if False:
            yield {}

    sm = StatusManager(t1.web_url)
    sm.is_running = False
    sm.is_rate_limited = True

    mock_extractor = MagicMock()
    mock_extractor.extract_raw_info.return_value = (fake_rate_limited_gen(), sm)

    with (
        patch("pi_yo_8.sources.lazy_playlist.YTDLPManager.get_extractor", return_value=mock_extractor),
        patch.object(service, "skip_tracks", wraps=service.skip_tracks) as skip_spy,
    ):
        await service.play_loop()

    assert t1.rate_limited is True
    skip_spy.assert_not_called()
    assert list(service.queue.play_queue) == [t1, t2]
    mock_audio.play.assert_not_called()
    mock_audio.pause.assert_called_once()

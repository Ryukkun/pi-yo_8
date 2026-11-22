import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pi_yo_8.engine.mixer import MultiTrackVoiceClient
from pi_yo_8.services.player_service import PlayerService
from pi_yo_8.sources.lazy_playlist import LazyPlaylist
from pi_yo_8.sources.resolver import TrackResolver
from pi_yo_8.sources.status import StatusManager


@pytest.mark.asyncio
async def test_seek_or_skip_parsing():
    mock_audio = MagicMock()
    mock_audio.timer = 30.0
    mock_audio.seek_by_seconds = AsyncMock()

    service = PlayerService("TestGuild", mock_audio)

    # Relative seconds: "10"
    await service.seek_or_skip("10")
    mock_audio.seek_by_seconds.assert_called_with(10)

    # Relative unit: "5m" -> 300s
    await service.seek_or_skip("5m")
    mock_audio.seek_by_seconds.assert_called_with(300)

    # Relative negative unit: "-30s" -> -30s
    await service.seek_or_skip("-30s")
    mock_audio.seek_by_seconds.assert_called_with(-30)

    # Absolute time: "1:00" -> 60s total, timer is 30s -> seek 30s
    await service.seek_or_skip("1:00")
    mock_audio.seek_by_seconds.assert_called_with(30)

    # Absolute time: "1:00:00" -> 3600s total, timer is 30s -> seek 3570s
    await service.seek_or_skip("1:00:00")
    mock_audio.seek_by_seconds.assert_called_with(3570)


@pytest.mark.asyncio
async def test_enqueue_search_playlist_does_not_loop():
    mock_audio = MagicMock()
    mock_audio.has_audio_data.return_value = False

    async def empty_gen():
        if False:
            yield {}

    first_entry = {
        "id": "vid1",
        "title": "Song 1",
        "url": "https://www.youtube.com/watch?v=vid1",
        "duration": 180,
        "playlist_title": "iyowa",
        "playlist_webpage_url": "ytsearch30:iyowa",
    }
    pl = LazyPlaylist(first_entry, empty_gen())
    await pl.decompress_task

    service = PlayerService("TestGuild", mock_audio)
    service.play_loop = AsyncMock()

    with patch.object(TrackResolver, "resolve", AsyncMock(return_value=(pl, None))):
        await service.enqueue("iyowa")

    assert pl.status.loop_pl is False
    assert service.status is pl.status
    assert service.status.loop_pl is False


@pytest.mark.asyncio
async def test_resolver_skips_channel_entry_at_head():
    async def fake_gen():
        yield {
            "_type": "url",
            "ie_key": "YoutubeTab",
            "url": "https://www.youtube.com/channel/UCLz6MG2kx_0xeaW0LowYnMQ",
            "title": "いよわ/ iyowa",
            "channel": "いよわ/ iyowa",
            "playlist": "iyowa",
            "playlist_title": "iyowa",
            "playlist_webpage_url": "ytsearch30:iyowa",
        }
        yield {
            "_type": "url",
            "ie_key": "Youtube",
            "id": "OVwCr2MESfo",
            "url": "https://www.youtube.com/watch?v=OVwCr2MESfo",
            "title": "IMAWANOKIWA",
            "duration": 256,
            "playlist": "iyowa",
            "playlist_title": "iyowa",
            "playlist_webpage_url": "ytsearch30:iyowa",
        }

    mock_extractor = MagicMock()
    mock_extractor.extract_raw_info.return_value = (fake_gen(), StatusManager(""))

    with patch("pi_yo_8.sources.resolver.YTDLPManager.get_extractor", return_value=mock_extractor):
        result, _ = await TrackResolver.resolve("iyowa")

    assert isinstance(result, LazyPlaylist)
    await result.decompress_task
    assert len(result.entries) == 1
    assert result.entries[0].title == "IMAWANOKIWA"


def test_mixer_no_opus_silence_before_speaking():
    loop = asyncio.new_event_loop()
    try:
        guild = MagicMock()
        guild.name = "TestGuild"
        vc = MagicMock()
        client = MultiTrackVoiceClient(guild, vc, loop)

        track = MagicMock()
        read_calls = 0

        def fake_read_bytes() -> None:
            nonlocal read_calls
            read_calls += 1

        track.read_bytes.side_effect = fake_read_bytes
        track.is_paused.side_effect = lambda: read_calls >= 2
        client.tracks.append(track)

        client._run_loop()
        vc.send_audio_packet.assert_not_called()
    finally:
        loop.close()

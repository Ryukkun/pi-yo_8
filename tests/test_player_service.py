from unittest.mock import AsyncMock, MagicMock

import pytest

from pi_yo_8.services.player_service import PlayerService


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

import pytest

from pi_yo_8.engine.attributes import TrackAttribute
from pi_yo_8.gui.utils import (
    EmbedTemplates,
    calculate_days_ago_text,
    format_large_number,
    format_seconds_to_time,
)


def test_format_seconds_to_time():
    assert format_seconds_to_time(0) == "0:00"
    assert format_seconds_to_time(9) == "0:09"
    assert format_seconds_to_time(59) == "0:59"
    assert format_seconds_to_time(60) == "1:00"
    assert format_seconds_to_time(65) == "1:05"
    assert format_seconds_to_time(3599) == "59:59"
    assert format_seconds_to_time(3600) == "1:00:00"
    assert format_seconds_to_time(3665) == "1:01:05"


def test_format_large_number():
    assert format_large_number(500) == "500"
    assert format_large_number(12345) == "1.2万"
    assert format_large_number(10000) == "1万"
    assert format_large_number(100000000) == "1億"


def test_calculate_days_ago_text():
    # Invalid date string returns input
    assert calculate_days_ago_text("invalid") == "invalid"


def test_embed_templates():
    assert EmbedTemplates.get_main_color().value == EmbedTemplates.MAIN_COLOR.value
    assert EmbedTemplates.get_player_color().value == EmbedTemplates.PLAYER_COLOR.value
    assert EmbedTemplates.get_persistent_color().value == EmbedTemplates.PERSISTENT_COLOR.value


@pytest.mark.asyncio
async def test_track_attribute_float_rounding():
    called = []
    attr = TrackAttribute[float](init=1.0, min_val=0.1, max_val=3.0, on_update_callback=lambda: called.append(True))
    assert attr.get() == 1.0

    # Add 0.1 repeatedly, shouldn't suffer from floating point error (1.1000000000000001)
    await attr.add(0.1)
    assert attr.get() == 1.1

    await attr.add(0.1)
    assert attr.get() == 1.2

    # Bounds check
    assert await attr.set(3.5) is False
    assert attr.get() == 1.2

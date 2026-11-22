from pi_yo_8.sources.mapper import calculate_gain, is_playable_entry, map_info_to_track


def test_calculate_gain():
    assert calculate_gain(None) is None
    assert calculate_gain({}) is None
    assert calculate_gain({"perceptualLoudnessDb": -10.0}) == -4.0
    assert calculate_gain({"perceptualLoudnessDb": -14.0}) == 0.0

def test_map_info_to_track():
    raw = {
        "id": "abc1234",
        "title": "Test Song",
        "url": "http://stream.googlevideo.com/videoplayback",
        "webpage_url": "https://youtube.com/watch?v=abc1234",
        "duration": 180,
        "uploader": "Test Artist",
        "upload_date": "20250101",
        "volume_data": {"perceptualLoudnessDb": -12.0},
    }
    track = map_info_to_track(raw)
    assert track.id == "abc1234"
    assert track.title == "Test Song"
    assert track.upload_date == "2025/01/01"
    assert track.is_stream_ready() is True
    assert track.stream_info is not None
    assert track.stream_info.volume_gain_db == -2.0

def test_map_info_to_track_flat_item():
    raw = {
        "id": "flat123",
        "title": "Flat Search Result",
        "url": "https://www.youtube.com/watch?v=flat123",
        "webpage_url": "https://www.youtube.com/watch?v=flat123",
        "duration": 200,
    }
    track = map_info_to_track(raw)
    assert track.id == "flat123"
    assert track.title == "Flat Search Result"
    assert track.is_stream_ready() is False
    assert track.stream_info is None


def test_is_playable_entry_filters_channel_and_allows_live():
    channel_entry = {
        "_type": "url",
        "ie_key": "YoutubeTab",
        "url": "https://www.youtube.com/channel/UCLz6MG2kx_0xeaW0LowYnMQ",
        "title": "いよわ/ iyowa",
        "channel": "いよわ/ iyowa",
    }
    handle_entry = {
        "_type": "url",
        "ie_key": "Youtube",
        "url": "https://www.youtube.com/@igusuri_please",
        "title": "いよわ",
        "channel": "いよわ",
    }
    live_entry = {
        "_type": "url",
        "ie_key": "Youtube",
        "url": "https://www.youtube.com/watch?v=live123",
        "title": "Live Stream",
        "duration": None,
        "channel": "Some Channel",
    }
    assert is_playable_entry(channel_entry) is False
    assert is_playable_entry(handle_entry) is False
    assert is_playable_entry(live_entry) is True


def test_map_info_to_track_channel_url_is_not_stream_ready():
    channel_entry = {
        "id": "UCLz6MG2kx_0xeaW0LowYnMQ",
        "title": "いよわ/ iyowa",
        "url": "https://www.youtube.com/channel/UCLz6MG2kx_0xeaW0LowYnMQ",
        "webpage_url": "https://www.youtube.com/channel/UCLz6MG2kx_0xeaW0LowYnMQ",
    }
    track = map_info_to_track(channel_entry)
    assert track.is_stream_ready() is False
    assert track.stream_info is None


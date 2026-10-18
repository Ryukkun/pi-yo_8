from pi_yo_8.sources.mapper import map_info_to_track, calculate_gain

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

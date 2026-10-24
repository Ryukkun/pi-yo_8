from typing import Any

from pi_yo_8.core.track import StreamInfo, Track


def calculate_gain(volume_data: dict[str, Any] | None) -> float | None:
    if volume_data and (volume := volume_data.get('perceptualLoudnessDb')) is not None:
        return -14.0 - float(volume)
    return None


def format_upload_date(upload_date: str | None) -> str | None:
    if upload_date and len(upload_date) == 8:
        return f"{upload_date[:4]}/{upload_date[4:6]}/{upload_date[6:]}"
    return upload_date


def filter_essential_raw_info(info: dict[str, Any]) -> dict[str, Any]:
    """メモリ節約のため、巨大な不要メタデータを削ぎ落とした辞書を作成"""
    essential_keys = {"id", "title", "url", "webpage_url", "formats", "volume_data", "uploader"}
    filtered = {k: info[k] for k in essential_keys if k in info}
    # formats があれば必要なキーだけに圧縮
    if "formats" in filtered and isinstance(filtered["formats"], list):
        filtered["formats"] = [
            {
                k: f[k]
                for k in ("url", "width", "height", "resolution", "ext", "acodec", "abr", "protocol")
                if k in f
            }
            for f in filtered["formats"]
            if isinstance(f, dict)
        ]
    return filtered


def map_info_to_track(info: dict[str, Any]) -> Track:
    track_id = info.get("id")
    title = info.get("title") or info.get("webpage_url") or "No Title"
    web_url = info.get("webpage_url") or info.get("original_url") or info.get("url") or ""
    duration = info.get("duration")
    uploader = info.get("uploader")
    uploader_url = info.get("uploader_url")
    uploader_id = info.get("uploader_id")
    view_count = info.get("view_count")
    upload_date = format_upload_date(info.get("upload_date"))

    thumbnail_url = None
    if thumbnails := info.get("thumbnails"):
        for thumb in reversed(thumbnails):
            if u := thumb.get("url"):
                thumbnail_url = u
                break

    stream_info = None
    if stream_url := info.get("url"):
        is_webpage = ("youtube.com/watch" in stream_url) or ("youtu.be/" in stream_url) or ("youtube.com/playlist" in stream_url)
        has_formats = bool(info.get("formats"))
        if has_formats or not is_webpage:
            headers = info.get("http_headers") or {}
            cookie = info.get("cookies")
            gain = calculate_gain(info.get("volume_data"))
            acodec = info.get("acodec")
            stream_info = StreamInfo(
                url=stream_url,
                http_headers=headers,
                cookies=cookie,
                volume_gain_db=gain,
                duration=duration,
                acodec=acodec,
            )

    return Track(
        id=track_id,
        title=title,
        web_url=web_url,
        duration=duration,
        uploader=uploader,
        uploader_url=uploader_url,
        uploader_id=uploader_id,
        view_count=view_count,
        upload_date=upload_date,
        thumbnail_url=thumbnail_url,
        stream_info=stream_info,
        raw_info=filter_essential_raw_info(info),
    )

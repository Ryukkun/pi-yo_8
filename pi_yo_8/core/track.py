from dataclasses import dataclass, field
from typing import Any


@dataclass
class StreamInfo:
    url: str
    http_headers: dict[str, str] = field(default_factory=dict)
    cookies: str | None = None
    volume_gain_db: float | None = None
    duration: float | None = None
    acodec: str | None = None


@dataclass
class Track:
    id: str | None
    title: str
    web_url: str
    duration: int | float | None = None
    uploader: str | None = None
    uploader_url: str | None = None
    uploader_id: str | None = None
    view_count: int | None = None
    upload_date: str | None = None
    thumbnail_url: str | None = None
    channel_icon_url: str | None = None
    stream_info: StreamInfo | None = None
    raw_info: dict[str, Any] = field(default_factory=dict)
    _load_task: Any = field(default=None, repr=False, compare=False)

    def is_stream_ready(self) -> bool:
        return self.stream_info is not None and bool(self.stream_info.url)

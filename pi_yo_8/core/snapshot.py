from dataclasses import dataclass, field
from typing import Any


@dataclass
class TrackSnapshot:
    title: str
    web_url: str
    duration: float | None = None
    thumbnail_url: str | None = None
    uploader: str | None = None
    uploader_url: str | None = None
    view_count: int | None = None
    upload_date: str | None = None


@dataclass
class StatusSnapshot:
    name: str
    url: str
    type_name: str
    is_running: bool
    recent_errors: list[str] = field(default_factory=list)


@dataclass
class PlaybackSnapshot:
    track: TrackSnapshot | None = None
    timer: float = 0.0
    duration: float | None = None
    is_paused: bool = True
    has_audio_data: bool = False
    is_playing_playlist: bool = False
    playlist_title: str | None = None
    playlist_url: str | None = None
    loop: bool = False
    loop_pl: bool = False
    random_pl: bool = False
    speed: float = 1.0
    pitch: int = 0
    statuses: list[StatusSnapshot] = field(default_factory=list)

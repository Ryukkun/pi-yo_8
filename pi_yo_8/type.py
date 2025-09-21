
from typing import Generator, TypeAlias, TypeVar, TypedDict, List, Dict, Optional, Union
from discord import StageChannel, TextChannel, Thread, VoiceChannel


SendableChannels: TypeAlias = TextChannel | VoiceChannel | StageChannel | Thread

T = TypeVar('T')


# サムネイル情報
class Thumbnail(TypedDict, total=False):
    id: Optional[str]
    url: str
    width: Optional[int]
    height: Optional[int]
    preference: Optional[int]


class VolumeData(TypedDict, total=False):
    perceptualLoudnessDb: float
    enablePerFormatLoudness: bool
    trackAbsoluteLoudnessLkfs: float
    loudnessTargetLkfs: float

# 個別動画情報
class VideoInfo(TypedDict, total=False):
    id: str
    title: str
    url: str
    original_url: str
    webpage_url: str
    description: Optional[str]
    uploader: Optional[str]
    uploader_id: Optional[str]
    uploader_url: Optional[str]
    duration: Optional[int]  # 秒
    upload_date: Optional[str]  # YYYYMMDD
    view_count: Optional[int]
    like_count: Optional[int]
    thumbnails: Optional[List[Thumbnail]]
    tags: Optional[List[str]]
    formats: Optional[List[Dict[str, Union[str,int,float]]]]
    volume_data: Optional[VolumeData]

# Info情報
class InfoType(TypedDict, total=False):
    id: str
    title: str
    url: str
    original_url: str
    webpage_url: str
    description: Optional[str]
    uploader: Optional[str]
    uploader_id: Optional[str]
    uploader_url: Optional[str]
    entries: Union[List[VideoInfo], Generator]  # プレイリスト内の動画
    duration: Optional[int]  # 秒
    upload_date: Optional[str]  # YYYYMMDD
    view_count: Optional[int]
    like_count: Optional[int]
    thumbnails: Optional[List[Thumbnail]]
    tags: Optional[List[str]]
    formats: Optional[List[Dict[str, Union[str,int,float]]]]
    volume_data: Optional[VolumeData]
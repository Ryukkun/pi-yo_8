from typing import TypeAlias
from discord import StageChannel, TextChannel, Thread, VoiceChannel

SendableChannels: TypeAlias = TextChannel | VoiceChannel | StageChannel | Thread

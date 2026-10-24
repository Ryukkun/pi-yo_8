from discord import StageChannel, TextChannel, Thread, VoiceChannel

type SendableChannels = TextChannel | VoiceChannel | StageChannel | Thread

SENDABLE_CHANNEL_TYPES = (TextChannel, VoiceChannel, StageChannel, Thread)

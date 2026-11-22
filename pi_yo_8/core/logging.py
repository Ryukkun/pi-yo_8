import logging

from discord.utils import _ColourFormatter


def setup_logger(level: int = logging.INFO) -> None:
    """pi_yo_8 および discord 音声関連のロガーフォーマット・レベルを設定する"""
    handler = logging.StreamHandler()
    handler.setFormatter(_ColourFormatter())

    for name in ("pi_yo_8", "__main__"):
        logger = logging.getLogger(name)
        logger.setLevel(level)
        if not logger.handlers:
            logger.addHandler(handler)

    player_logger = logging.getLogger("discord.player")
    player_logger.setLevel(logging.DEBUG if level == logging.DEBUG else logging.WARNING)
    if not player_logger.handlers:
        player_logger.addHandler(handler)

    if level == logging.DEBUG:
        for name in ("discord.voice_client", "discord.voice_state", "discord.gateway"):
            v_logger = logging.getLogger(name)
            v_logger.setLevel(logging.DEBUG)
            if not v_logger.handlers:
                v_logger.addHandler(handler)

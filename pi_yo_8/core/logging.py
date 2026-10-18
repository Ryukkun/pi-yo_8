import logging
from discord.utils import _ColourFormatter

def setup_logger(level: int = logging.INFO):
    handler = logging.StreamHandler()
    handler.setFormatter(_ColourFormatter())

    for name in ("pi_yo_8", "discord.player"):
        logger = logging.getLogger(name)
        logger.setLevel(level)
        if not logger.handlers:
            logger.addHandler(handler)


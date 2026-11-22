import argparse
import asyncio
import logging
import os

import discord
from discord.ext import commands

IS_MAIN_PROCESS = __name__ == "__main__"
_log = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discord Music Bot (pi-yo_8) の起動スクリプト")
    parser.add_argument("--debug", action="store_true", help="デバッグモードを有効にする")
    return parser.parse_args()


async def main(debug: bool = False) -> None:
    from pi_yo_8.core.config import app_config
    from pi_yo_8.core.logging import setup_logger
    from pi_yo_8.engine.discord_patch import apply_discord_patch
    from pi_yo_8.main import MusicBotCog
    from pi_yo_8.sources.manager import YTDLPManager

    setup_logger(logging.DEBUG if debug else logging.INFO)
    apply_discord_patch()

    if not app_config.token:
        raise RuntimeError("Token が未設定です。config.json に token を設定して再起動してください。")

    os.makedirs(app_config.guild_config, exist_ok=True)
    os.makedirs(app_config.user_config, exist_ok=True)

    intents = discord.Intents.default()
    intents.message_content = True
    intents.reactions = True
    intents.voice_states = True
    bot = commands.Bot(command_prefix=app_config.prefix, intents=intents)
    YTDLPManager.initialize(general_pool_size=4, video_pool_size=4)

    async with bot:
        await bot.add_cog(MusicBotCog(bot))
        await bot.start(app_config.token)


if IS_MAIN_PROCESS:
    args = parse_args()
    try:
        asyncio.run(main(debug=args.debug), debug=args.debug)
    except KeyboardInterrupt:
        _log.info("Bot has stopped (Ctrl+C).")
    finally:
        try:
            from pi_yo_8.sources.manager import YTDLPManager
            YTDLPManager.shutdown_all()
        except Exception:
            pass

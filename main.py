import asyncio
import logging
import shutil
from pathlib import Path

import discord
from discord.ext import commands

IS_MAIN_PROCESS = __name__ == "__main__"
_log = logging.getLogger(__name__)

async def main() -> None:
    base_dir = Path(__file__).resolve().parent
    config_file = base_dir / "pi_yo_8" / "config.py"
    template_file = base_dir / "pi_yo_8" / "resources" / "config_template.py"

    if not config_file.exists():
        shutil.copy(template_file, config_file)
        raise RuntimeError("Config ファイル (pi_yo_8/config.py) をテンプレートから生成しました。Token等を設定して再起動してください。")

    from pi_yo_8 import config
    from pi_yo_8.core.logging import setup_logger
    from pi_yo_8.engine.discord_patch import apply_discord_patch
    from pi_yo_8.main import MusicBotCog
    from pi_yo_8.sources.manager import YTDLPManager

    apply_discord_patch()

    intents = discord.Intents.default()
    intents.message_content = True
    intents.reactions = True
    intents.voice_states = True
    bot = commands.Bot(command_prefix=config.Prefix, intents=intents)
    YTDLPManager.initialize(general_pool_size=4, video_pool_size=4)
    setup_logger()

    async with bot:
        await bot.add_cog(MusicBotCog(bot))
        await bot.start(config.Token)

if IS_MAIN_PROCESS:
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        _log.info("Bot has stopped (Ctrl+C).")
    finally:
        try:
            from pi_yo_8.sources.manager import YTDLPManager
            YTDLPManager.shutdown_all()
        except Exception:
            pass

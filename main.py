import asyncio
import shutil
import discord
from discord.ext import commands

IS_MAIN_PROCESS = __name__ == "__main__"

async def main():
    try:
        from pi_yo_8 import config
    except Exception:
        shutil.copy("./pi_yo_8/resources/config_template.py", "./pi_yo_8/config.py")
        raise Exception('Config ファイルを生成しました')

    from pi_yo_8.core.logging import setup_logger
    from pi_yo_8.engine.discord_patch import apply_discord_patch
    from pi_yo_8.main import MusicBotCog
    from pi_yo_8.sources.manager import YTDLPManager

    apply_discord_patch()

    ####  起動準備 And 初期設定
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
        print("\nBot has stopped (Ctrl+C).")
    finally:
        try:
            from pi_yo_8.sources.manager import YTDLPManager
            YTDLPManager.shutdown_all()
        except Exception:
            pass
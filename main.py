import asyncio
import shutil
import discord
from discord.ext import commands


IS_MAIN_PROCESS = __name__ == "__main__"

async def main():
    try: from pi_yo_8 import config
    except Exception:
        shutil.copy("./pi_yo_8/resources/config_template.py", "./pi_yo_8/config.py")
        raise Exception('Config ファイルを生成しました')
    
    from pi_yo_8.main import MyCog
    from pi_yo_8.utils import set_logger
    from pi_yo_8.yt_dlp.manager import YTDLPManager


    ####  起動準備 And 初期設定
    intents = discord.Intents.default()
    intents.message_content = True
    intents.reactions = True
    intents.voice_states = True
    bot = commands.Bot(command_prefix=config.Prefix,intents=intents)
    YTDLPManager.initiallize()
    set_logger()

    async with bot:
        await bot.add_cog(MyCog(bot))
        await bot.start(config.Token)

if IS_MAIN_PROCESS:
    asyncio.run(main())
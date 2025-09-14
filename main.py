import asyncio
import shutil
import discord
import pi_yo_8.main
from discord.ext import commands

from pi_yo_8.yt_dlp.manager import YTDLPManager


async def main():
    try: from pi_yo_8 import config
    except Exception:
        shutil.copy("./pi_yo_8/resources/config_template.py", "./pi_yo_8/config.py")
        raise Exception('Config ファイルを生成しました')

    ####  起動準備 And 初期設定
    intents = discord.Intents.default()
    intents.message_content = True
    intents.reactions = True
    intents.voice_states = True
    bot = commands.Bot(command_prefix=config.Prefix,intents=intents)
    YTDLPManager.initiallize()

    async with bot:
        await bot.add_cog(pi_yo_8.main.MyCog(bot))
        await bot.start(config.Token)

if __name__ == "__main__":
    asyncio.run(main())
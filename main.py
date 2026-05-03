# main.py
import asyncio
import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from utils.db import init_db

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("spitdope")


class SpitDopeBot(commands.Bot):
    async def setup_hook(self) -> None:
        # Init DB first — cogs depend on it
        await init_db()
        log.info("Database initialised.")

        # Load all cogs
        for filename in os.listdir("./cogs"):
            if not filename.endswith(".py"):
                continue
            ext = f"cogs.{filename[:-3]}"
            try:
                await self.load_extension(ext)
                log.info(f"Loaded {ext}")
            except Exception as exc:
                log.error(f"Failed to load {ext}: {exc}")

        await self.tree.sync()
        log.info("Slash commands synced.")

    async def on_ready(self) -> None:
        log.info(f"✅ Logged in as {self.user} ({self.user.id})")


def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN is not set in your .env file.")

    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    bot = SpitDopeBot(command_prefix="$", intents=intents)

    asyncio.run(bot.start(token))


if __name__ == "__main__":
    main()

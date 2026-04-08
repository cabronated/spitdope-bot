# main.py
import os
import asyncio
from dotenv import load_dotenv
import discord
from discord.ext import commands

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Load extensions on startup
@bot.event
async def setup_hook():
    # load cogs
    await bot.load_extension("cogs.word_of_day")
    # sync commands
    await bot.tree.sync()

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} ({bot.user.id})")
    print("🌐 Slash commands synced.")

if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN not set in environment")
    bot.run(TOKEN)

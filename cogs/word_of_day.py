# cogs/word_of_day.py
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import asyncio

from utils import db  # make sure utils is a package (utils/__init__.py)

OWNER_ID = 123456789012345678  # replace with your Discord ID

def admin_or_owner():
    async def predicate(interaction: discord.Interaction) -> bool:
        return (
            interaction.user.id == OWNER_ID
            or interaction.user.guild_permissions.administrator
        )
    return app_commands.check(predicate)

class WordOfDay(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # channel IDs stored per guild in memory; you should persist these if needed
        self.guild_configs = {}  # {guild_id: {"post_channel": int, "daily_time": "HH:MM", "timezone": "Asia/Kolkata"}}

    @commands.Cog.listener()
    async def on_ready(self):
        # ensure tables exist
        await db.create_tables()

    # Admin-only setup (kept restricted)
    @app_commands.command(name="setup", description="Configure Word of the Day for this server (Admin only).")
    @admin_or_owner()
    async def setup(self, interaction: discord.Interaction, post_channel: discord.TextChannel, daily_time: str, timezone: Optional[str] = "Asia/Kolkata"):
        self.guild_configs[interaction.guild.id] = {
            "post_channel": post_channel.id,
            "daily_time": daily_time,
            "timezone": timezone
        }
        await interaction.response.send_message("✅ Word of the Day configured for this server.", ephemeral=True)

    # Open to everyone: add words (comma separated). language optional.
    @app_commands.command(name="add_words", description="Add new words (comma separated). Language optional.")
    async def add_words(self, interaction: discord.Interaction, words: str, language: Optional[str] = "english"):
        added = 0
        for raw in words.split(","):
            w = raw.strip()
            if not w:
                continue
            await db.add_word(w, language.lower(), interaction.user.id)
            added += 1
        await interaction.response.send_message(f"✅ Added {added} word(s) to the pool.", ephemeral=True)

    # Open to everyone: view words (first N)
    @app_commands.command(name="view_words", description="View words stored in the bot (first 100).")
    async def view_words(self, interaction: discord.Interaction, limit: Optional[int] = 100):
        rows = await db.get_words(limit=limit)
        if not rows:
            await interaction.response.send_message("📭 No words in the pool.", ephemeral=True)
            return

        lines = []
        for r in rows:
            # r is a tuple: (id, word, language, added_by, added_at)
            _id, word, language, added_by, added_at = r
            lines.append(f"{_id}. {word} — **{language}**")

        # chunk message if too long
        chunk = "\n".join(lines)
        if len(chunk) > 1900:
            # split into multiple messages
            parts = [chunk[i:i+1900] for i in range(0, len(chunk), 1900)]
            for p in parts:
                await interaction.user.send(p)
            await interaction.response.send_message("📬 Sent the word list to your DMs.", ephemeral=True)
        else:
            await interaction.response.send_message(f"📚 Words:\n{chunk}", ephemeral=True)

    # Open to everyone: word count
    @app_commands.command(name="word_count", description="Show how many words are left in the pool.")
    async def word_count(self, interaction: discord.Interaction):
        count = await db.word_count()
        await interaction.response.send_message(f"🔢 Words in pool: **{count}**", ephemeral=True)

    # Admin or owner only: post now (pops next word and posts to configured channel)
    @app_commands.command(name="post_now", description="Post the next Word of the Day now (Admin or Owner only).")
    @admin_or_owner()
    async def post_now(self, interaction: discord.Interaction):
        cfg = self.guild_configs.get(interaction.guild.id)
        if not cfg:
            return await interaction.response.send_message("❌ Server not configured. Use /setup first.", ephemeral=True)

        row = await db.pop_next_word()
        if not row:
            return await interaction.response.send_message("📭 No words left to post.", ephemeral=True)

        # row is a dict if RealDictCursor used in pop; but our wrapper returns a dict-like or tuple depending on implementation.
        # To be safe, handle both:
        if isinstance(row, dict):
            word = row.get("word")
            language = row.get("language")
        else:
            # tuple: (id, word, language, added_by, added_at)
            _, word, language, _, _ = row

        channel = self.bot.get_channel(cfg["post_channel"])
        if not channel:
            return await interaction.response.send_message("❌ Post channel not found. Check configuration.", ephemeral=True)

        await channel.send(f"📢 **Word of the Day**\n**{word}** — *{language}*")
        await interaction.response.send_message("✅ Posted the next word.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(WordOfDay(bot))

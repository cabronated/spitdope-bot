# cogs/word_of_day.py
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
from utils import db
import os

OWNER_ID = int(os.getenv("OWNER_ID", "0"))

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
        self.guild_configs = {}  # ephemeral in-memory config

    @commands.Cog.listener()
    async def on_ready(self):
        await db.create_tables()

    @app_commands.command(name="ping", description="Check if cog is loaded")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message("pong", ephemeral=True)

    @app_commands.command(name="add_words", description="Add new words (comma separated).")
    async def add_words(self, interaction: discord.Interaction, words: str, language: Optional[str] = "english"):
        try:
            added = 0
            for raw in words.split(","):
                w = raw.strip()
                if not w:
                    continue
                await db.add_word(w, language.lower(), interaction.user.id)
                added += 1
            await interaction.response.send_message(f"✅ Added {added} word(s) to the pool.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error adding words: {e}", ephemeral=True)

    @app_commands.command(name="view_words", description="View words stored in the bot (first N).")
    async def view_words(self, interaction: discord.Interaction, limit: Optional[int] = 100):
        try:
            rows = await db.get_words(limit=limit)
            if not rows:
                await interaction.response.send_message("📭 No words in the pool.", ephemeral=True)
                return

            lines = [f"{r['id']}. {r['word']} — **{r['language']}**" for r in rows]
            chunk = "\n".join(lines)
            if len(chunk) > 1900:
                # send via DM in chunks
                for i in range(0, len(chunk), 1900):
                    await interaction.user.send(chunk[i:i+1900])
                await interaction.response.send_message("📬 Sent the word list to your DMs.", ephemeral=True)
            else:
                await interaction.response.send_message(f"📚 Words:\n{chunk}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error fetching words: {e}", ephemeral=True)

    @app_commands.command(name="word_count", description="Show how many words are left in the pool.")
    async def word_count(self, interaction: discord.Interaction):
        try:
            count = await db.word_count()
            await interaction.response.send_message(f"🔢 Words in pool: **{count}**", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error fetching count: {e}", ephemeral=True)

    @app_commands.command(name="post_now", description="Post the next Word of the Day now (Admin or Owner only).")
    @admin_or_owner()
    async def post_now(self, interaction: discord.Interaction):
        try:
            cfg = self.guild_configs.get(interaction.guild.id)
            if not cfg:
                return await interaction.response.send_message("❌ Server not configured. Use /setup first.", ephemeral=True)

            row = await db.pop_next_word()
            if not row:
                return await interaction.response.send_message("📭 No words left to post.", ephemeral=True)

            word = row.get("word")
            language = row.get("language")
            channel = self.bot.get_channel(cfg["post_channel"])
            if not channel:
                return await interaction.response.send_message("❌ Post channel not found. Check configuration.", ephemeral=True)

            await channel.send(f"📢 **Word of the Day**\n**{word}** — *{language}*")
            await interaction.response.send_message("✅ Posted the next word.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error posting word: {e}", ephemeral=True)

    @app_commands.command(name="setup", description="Configure Word of the Day for this server (Admin only).")
    @admin_or_owner()
    async def setup(self, interaction: discord.Interaction, post_channel: discord.TextChannel, daily_time: str, timezone: Optional[str] = "Asia/Kolkata"):
        self.guild_configs[interaction.guild.id] = {
            "post_channel": post_channel.id,
            "daily_time": daily_time,
            "timezone": timezone
        }
        await interaction.response.send_message("✅ Word of the Day configured for this server.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(WordOfDay(bot))

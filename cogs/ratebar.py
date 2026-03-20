# cogs/ratebar.py
import os
import json
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import pytz
from utils.ai_client import analyze_text

COOLDOWN_FILE = "cooldowns.json"
DAILY_LIMIT = 3
IST = pytz.timezone("Asia/Kolkata")

def load_cooldowns():
    if os.path.exists(COOLDOWN_FILE):
        try:
            with open(COOLDOWN_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_cooldowns(data):
    with open(COOLDOWN_FILE, "w") as f:
        json.dump(data, f, indent=2)

user_last_used = load_cooldowns()

class BarsAnalyzer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def analyze_bar(self, text: str) -> str:
        prompt = f"""
You are a rap analyst and rhyme technician known for being brutally honest, fair, and unfiltered.
Judge rap bars based on overall writing quality — including creativity, emotion, originality, wordplay, and technical execution.
If it's weak, say so directly. If it's exceptional, give full credit.
Respond concisely in this format:

🎭 Overall Breakdown
• (creativity, emotion, wordplay, references, originality etc)

🎚️ Overall Rating (1–10)
• (Give blunt reason(s) — based on total impact, structure, and craftsmanship)

Keep it compact, direct, and formatted cleanly for Discord.

Bar:
{text}
"""
        return await analyze_text(prompt)

    @app_commands.command(name="ratebar", description="Analyze your rap bar (3 uses per day).")
    async def ratebar(self, interaction: discord.Interaction, bar: str):
        user_id = str(interaction.user.id)
        now = datetime.now(IST)
        today = now.date().isoformat()
        entry = user_last_used.get(user_id, {"date": today, "count": 0})
        if entry["date"] != today:
            entry = {"date": today, "count": 0}
        if entry["count"] >= DAILY_LIMIT:
            return await interaction.response.send_message(
                f"🕒 You've used all **{DAILY_LIMIT}** ratings for today.\nTry again tomorrow!",
                ephemeral=True
            )
        await interaction.response.defer(thinking=True)
        analysis = await self.analyze_bar(bar)
        entry["count"] += 1
        entry["date"] = today
        user_last_used[user_id] = entry
        save_cooldowns(user_last_used)
        embed = discord.Embed(
            title="🎧 SPITDOPE BAR BREAKDOWN",
            description=analysis[:4000],
            color=discord.Color.orange()
        )
        embed.set_footer(
            text=f"dropped by {interaction.user.display_name} | {now.strftime('%H:%M')} | {entry['count']}/{DAILY_LIMIT} used"
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="clearcooldown", description="Clear all ratebar cooldowns (Admin only).")
    async def clearcooldown(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Admin only command.", ephemeral=True)
        user_last_used.clear()
        save_cooldowns(user_last_used)
        await interaction.response.send_message("✅ All cooldowns cleared.", ephemeral=True)

    @app_commands.command(name="statsbar", description="Show today's bar rating usage (Admin only).")
    async def statsbar(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Admin only command.", ephemeral=True)
        now = datetime.now(IST)
        today = now.date().isoformat()
        lines = []
        for user_id, entry in user_last_used.items():
            if entry["date"] != today:
                continue
            user = self.bot.get_user(int(user_id))
            name = user.display_name if user else f"User {user_id}"
            lines.append(f"• **{name}** — {entry['count']}/{DAILY_LIMIT} used")
        if not lines:
            return await interaction.response.send_message("📭 No one has used /ratebar today yet.", ephemeral=True)
        embed = discord.Embed(
            title="📊 Today’s /ratebar Usage",
            description="\n".join(lines),
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Team Spitdope • {today}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(BarsAnalyzer(bot))
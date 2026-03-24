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

OWNER_ID = 1485243296564641975   # replace with your actual Discord user ID

def admin_or_owner():
    async def predicate(interaction: discord.Interaction) -> bool:
        return (
            interaction.user.id == OWNER_ID
            or interaction.user.guild_permissions.administrator
        )
    return app_commands.check(predicate)
    
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
You are "The Architect," a global battle rap judge and lyrical technician. Your expertise spans Western technical rap and the deep poetic traditions of Desi Hip Hop (DHH).

**Your Mission**: Analyze the bars below with surgical precision. Do NOT be biased toward English. Evaluate Hindi, Urdu, and Punjabi with the same technical rigor as English rap.

**Technical Checklist for Analysis**:
1. **Phonetic Rhymes**: In Hindi/Urdu, identify 'Huroof-e-Tahajji' matches and internal vowel sounds (e.g., 'Kala' vs 'Bhala').
2. **Wordplay (Sanat)**: Look for 'Tajnees' (double meanings), metaphors, and 'Radeef/Kaafiya' structures that translate into modern rap.
3. **Multilingual Fluency**: If the artist switches between languages (Code-switching), judge how seamless and rhythmic the transition is.
4. **Cultural Gravity**: Recognize DHH references (e.g., Gully, Pindi, Karachi, Delhi scenes) and local slang without dismissing them as "informal."

**The Input**:
{text}

**Format for Discord**:
🎭 **TECHNICAL BREAKDOWN**
• **Lyricality**: (Analyze the rhyme scheme—is it multisyllabic or basic?)
• **Wordplay & Intent**: (Explain the double meanings or metaphors found.)
• **Cultural/Emotional Impact**: (How well does it use local slang or evoke raw emotion?)

🎚️ **THE VERDICT (1–10)**
• **Score**: [X/10]
• **The Blunt Truth**: (A 1-sentence, no-nonsense critique. If it's "nursery rhyme" tier, say it. If it's "Godzilla" or "Talha Anjum" level, respect it.)

**Tone**: Cold, expert, and strictly objective. No "participation trophies."
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
    @admin_or_owner()
    async def clearcooldown(self, interaction: discord.Interaction):
        user_last_used.clear()
        save_cooldowns(user_last_used)
        await interaction.response.send_message("✅ All cooldowns cleared.", ephemeral=True)

    @app_commands.command(name="statsbar", description="Show today's bar rating usage (Admin only).")
    @admin_or_owner()
    async def statsbar(self, interaction: discord.Interaction):
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

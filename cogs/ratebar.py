# cogs/ratebar.py
import re
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import pytz

from utils.ai_client import analyze_text
from utils.checks import admin_or_owner
from utils import db

DAILY_LIMIT = 3
IST = pytz.timezone("Asia/Kolkata")

COLOR_NORMAL = discord.Color.orange()
COLOR_WOTD   = discord.Color.green()

BAR_PROMPT = """\
You are "The Architect," a global battle rap judge and lyrical technician. \
Your expertise spans Western technical rap and the deep poetic traditions of Desi Hip Hop (DHH).

**Your Mission**: Analyze the bars below with surgical precision. \
Do NOT be biased toward English. Evaluate Hindi, Urdu, and Punjabi with the same technical rigor as English rap.

**Technical Checklist for Analysis**:
1. **Phonetic Rhymes**: In Hindi/Urdu, identify 'Huroof-e-Tahajji' matches and internal vowel sounds (e.g., 'Kala' vs 'Bhala').
2. **Wordplay (Sanat)**: Look for 'Tajnees' (double meanings), metaphors, and 'Radeef/Kaafiya' structures.
3. **Multilingual Fluency**: Judge code-switching on seamlessness and rhythm.
4. **Cultural Gravity**: Recognize DHH references (Gully, Pindi, Karachi, Delhi scenes) and local slang without dismissing them.

**The Input**:
{bar}

**Format for Discord**:
🎭 **TECHNICAL BREAKDOWN**
• **Lyricality**: (rhyme scheme — multisyllabic or basic?)
• **Wordplay & Intent**: (double meanings or metaphors)
• **Cultural/Emotional Impact**: (local slang or raw emotion)

🎚️ **THE VERDICT (1–10)**
• **Score**: [X/10]
• **The Blunt Truth**: (one sentence, no filter — nursery rhyme or Godzilla tier, say it straight)

Keep it compact, direct, and formatted cleanly for Discord.\
"""

_SCORE_RE = re.compile(r"\b(\d(?:\.\d)?)/10\b")


def parse_score(text: str) -> float:
    """Pull the first X/10 out of the AI response. Returns 0.0 if not found."""
    m = _SCORE_RE.search(text)
    return float(m.group(1)) if m else 0.0


def contains_wotd(bar: str, wotd: str) -> bool:
    """Case-insensitive whole-word match."""
    pattern = rf"\b{re.escape(wotd)}\b"
    return bool(re.search(pattern, bar, re.IGNORECASE))


class BarsAnalyzer(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── /ratebar ─────────────────────────────────────────────────────────────

    @app_commands.command(name="ratebar", description="Analyze your rap bar (3 uses per day).")
    async def ratebar(self, interaction: discord.Interaction, bar: str) -> None:
        now = datetime.now(IST)
        today = now.date()

        count = await db.get_usage_count(interaction.user.id, today)
        if count >= DAILY_LIMIT:
            await interaction.response.send_message(
                f"🕒 You've used all **{DAILY_LIMIT}** ratings for today. Try again tomorrow!",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)

        wotd = await db.get_current_wotd(interaction.guild_id)
        had_wotd = bool(wotd and contains_wotd(bar, wotd))

        analysis = await analyze_text(BAR_PROMPT.format(bar=bar))
        score = parse_score(analysis)
        new_count = await db.increment_usage(interaction.user.id, today)

        await db.save_verse(
            guild_id=interaction.guild_id,
            user_id=interaction.user.id,
            bar_text=bar,
            score=score,
            had_wotd=had_wotd,
            wotd=wotd,
            scored_date=today,
        )

        color = COLOR_WOTD if had_wotd else COLOR_NORMAL
        title = "🎧 SPITDOPE BAR BREAKDOWN"
        if had_wotd:
            title += f"  •  🔥 WOTD: {wotd}"

        embed = discord.Embed(title=title, description=analysis[:4000], color=color)
        embed.set_footer(
            text=(
                f"dropped by {interaction.user.display_name} "
                f"| {now.strftime('%H:%M')} IST "
                f"| {new_count}/{DAILY_LIMIT} used"
                + (" | contains WOTD ✅" if had_wotd else "")
            )
        )
        await interaction.followup.send(embed=embed)

        if had_wotd:
            cfg = await db.get_guild_config(interaction.guild_id)
            if cfg:
                await self._handle_wotd_action(interaction, cfg, embed)

    async def _handle_wotd_action(
        self,
        interaction: discord.Interaction,
        cfg: dict,
        embed: discord.Embed,
    ) -> None:
        action = cfg.get("wotd_action", "color")
        if action == "color":
            return  # green embed is all we do

        bars_channel = self.bot.get_channel(cfg.get("bars_channel"))
        if not bars_channel:
            return

        fwd_embed = discord.Embed(
            title=f"🔥 WOTD Verse — {embed.title}",
            description=embed.description,
            color=COLOR_WOTD,
        )
        fwd_embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url,
        )

        if action == "forward":
            await bars_channel.send(embed=fwd_embed)
        elif action == "ping":
            role_id = cfg.get("role_id")
            mention = f"<@&{role_id}>" if role_id else ""
            await bars_channel.send(content=mention, embed=fwd_embed)

    # ── /clearcooldown ────────────────────────────────────────────────────────

    @app_commands.command(name="clearcooldown", description="Clear all ratebar cooldowns (Admin only).")
    @admin_or_owner()
    async def clearcooldown(self, interaction: discord.Interaction) -> None:
        await db.clear_all_usage()
        await interaction.response.send_message("✅ All cooldowns cleared.", ephemeral=True)

    # ── /statsbar ─────────────────────────────────────────────────────────────

    @app_commands.command(name="statsbar", description="Show today's bar rating usage (Admin only).")
    @admin_or_owner()
    async def statsbar(self, interaction: discord.Interaction) -> None:
        today = datetime.now(IST).date()
        rows = await db.get_today_usage(today)

        if not rows:
            await interaction.response.send_message(
                "📭 No one has used /ratebar today yet.", ephemeral=True
            )
            return

        lines = []
        for row in rows:
            user = self.bot.get_user(int(row["user_id"]))
            name = user.display_name if user else f"User {row['user_id']}"
            lines.append(f"• **{name}** — {row['count']}/{DAILY_LIMIT} used")

        embed = discord.Embed(
            title="📊 Today's /ratebar Usage",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        embed.set_footer(text=f"Team Spitdope • {today.isoformat()}")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BarsAnalyzer(bot))

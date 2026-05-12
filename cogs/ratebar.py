# cogs/ratebar.py
import re
import logging
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

logger = logging.getLogger(__name__)

BAR_PROMPT = """\
You are a sharp, knowledgeable hip-hop verse critic. When a user shares rap lyrics or a verse, analyze it across five dimensions — lyricism, flow & rhythm, rhyme scheme, bars & punchlines, and theme & storytelling.

Be honest, constructive, and direct. No sugarcoating, no unnecessary harshness. Speak like someone who genuinely lives and breathes hip-hop culture.

---

**OUTPUT FORMAT**

Keep it tight — Discord has a 2000 character limit. Use this exact structure:

🎤 **VERSE REVIEW**

📝 **Lyricism**
[2–3 sentences — wordplay, metaphors, vocabulary, originality]

🎵 **Flow & Rhythm**
[2–3 sentences — cadence, syllable pacing, how bars ride the beat]

🔁 **Rhyme Scheme**
[2–3 sentences — complexity, multisyllabics, forced vs. natural rhymes]

💥 **Bars & Punchlines**
[2–3 sentences — quotable moments, wit, cleverness, re-listen value]

📖 **Theme & Storytelling**
[2–3 sentences — message clarity, depth, originality, emotional impact]

---
⚡ **BEST LINE:** "[quote the single strongest bar]"
🚩 **WEAKEST POINT:** [one-line callout of the biggest flaw]

🏆 **FINAL RATING: X.X / 10**
[2 sentences — overall verdict and one concrete tip to level up]

---

**RULES**
- Never show a number score for individual categories. Final rating only.
- Internally weigh: Lyricism 25%, Flow 20%, Rhyme 20%, Bars 25%, Theme 10% to arrive at the final score.
- Never pad responses. Every word must earn its place.
- If the verse is under 4 bars, note it and still rate what's there.
- Do not rate anything that isn't rap lyrics. Politely redirect.
- Avoid filler like "Great effort!" — give real, specific critique.
- If a bar is genuinely elite, say so. If it's weak, say exactly why.

**The Input**:
{bar}\
"""

_SCORE_RE = re.compile(
    r"\*{0,2}(\d+(?:\.\d+)?)\*{0,2}\s*/\s*10\b",
    re.IGNORECASE
)

# Strings that ai_client.py might return instead of raising on failure.
# Adjust these to match whatever your ai_client actually returns on error.
_ERROR_PREFIXES = (
    "error",
    "❌",
    "sorry",
    "i'm sorry",
    "i am sorry",
    "unable to",
    "i couldn't",
    "i could not",
)


def _looks_like_error(text: str) -> bool:
    """Return True if analyze_text returned an error string instead of raising."""
    lowered = text.strip().lower()
    return any(lowered.startswith(p) for p in _ERROR_PREFIXES)


def parse_score(text: str) -> float:
    matches = _SCORE_RE.findall(text)
    if not matches:
        return 0.0
    return round(min(max(float(matches[-1]), 0), 10), 1)


def contains_wotd(bar: str, wotd: str) -> bool:
    """Case-insensitive whole-word match."""
    pattern = rf"\b{re.escape(wotd)}\b"
    return bool(re.search(pattern, bar, re.IGNORECASE))


class BarsAnalyzer(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── /ratebar ──────────────────────────────────────────────────────────

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

        try:
            wotd = await db.get_current_wotd(interaction.guild_id)
            had_wotd = bool(wotd and contains_wotd(bar, wotd))

            analysis = await analyze_text(BAR_PROMPT.format(bar=bar))

            # ── KEY FIX: treat a returned error string the same as a raised exception ──
            if not analysis or _looks_like_error(analysis):
                raise ValueError(f"analyze_text returned an error string: {analysis!r}")

            score = parse_score(analysis)

            await db.save_verse(
                guild_id=interaction.guild_id,
                user_id=interaction.user.id,
                bar_text=bar,
                score=score,
                had_wotd=had_wotd,
                wotd=wotd,
                scored_date=today,
            )

            # ── Increment ONLY after everything above succeeded ──
            new_count = await db.increment_usage(interaction.user.id, today)

            color = COLOR_WOTD if had_wotd else COLOR_NORMAL
            title = "🎧 SPITDOPE BAR BREAKDOWN"
            if had_wotd:
                title += f"  •  🔥 WOTD: {wotd}"

            description = analysis if len(analysis) <= 4000 else analysis[:3997] + "..."

            embed = discord.Embed(title=title, description=description, color=color)
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
                    try:
                        await self._handle_wotd_action(interaction, cfg, embed)
                    except Exception:
                        logger.warning("WOTD action failed", exc_info=True)

        except Exception as e:
            logger.error(f"Error in ratebar for user {interaction.user.id}: {e}", exc_info=True)

            try:
                error_embed = discord.Embed(
                    title="❌ Something went wrong",
                    description="Sorry, couldn't analyze that bar right now. Please try again later!",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=error_embed)
            except Exception:
                logger.error("Failed to send error embed to user", exc_info=True)

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

    # ── /clearcooldown ───────────────────────────────────────────────────────

    @app_commands.command(name="clearcooldown", description="Clear all ratebar cooldowns (Admin only).")
    @admin_or_owner()
    async def clearcooldown(self, interaction: discord.Interaction) -> None:
        await db.clear_all_usage()
        await interaction.response.send_message("✅ All cooldowns cleared.", ephemeral=True)

    # ── /statsbar ─────────────────────────────────────────────────────────

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

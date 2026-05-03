# cogs/word_of_day.py
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import pytz

from utils.checks import admin_or_owner, staff_only
from utils import db

IST = pytz.timezone("Asia/Kolkata")


class WordOfDayCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.daily_word_task.start()

    def cog_unload(self) -> None:
        self.daily_word_task.cancel()

    # ── WOTD scheduler ───────────────────────────────────────────────────────

    @tasks.loop(minutes=1)
    async def daily_word_task(self) -> None:
        guilds = await db.get_all_configured_guilds()
        for cfg in guilds:
            await self._maybe_post_wotd(cfg)

    @daily_word_task.before_loop
    async def _before_wotd(self) -> None:
        await self.bot.wait_until_ready()

    async def _maybe_post_wotd(self, cfg: dict) -> None:
        try:
            tz = pytz.timezone(cfg.get("timezone") or "Asia/Kolkata")
        except Exception:
            tz = pytz.timezone("Asia/Kolkata")

        now = datetime.now(tz)

        try:
            hour, minute = map(int, cfg["daily_time"].split(":"))
        except Exception:
            hour, minute = 7, 0

        last_post_date = None
        if cfg.get("last_post"):
            try:
                lp = datetime.fromisoformat(cfg["last_post"])
                if lp.tzinfo is None:
                    lp = lp.replace(tzinfo=pytz.UTC)
                last_post_date = lp.astimezone(tz).date()
            except ValueError:
                pass

        if now.hour == hour and now.minute == minute and last_post_date != now.date():
            await self._post_word(cfg["guild_id"])

    # ── Core posting ──────────────────────────────────────────────────────────

    async def _post_word(self, guild_id: int) -> bool:
        cfg = await db.get_guild_config(guild_id)
        if not cfg:
            return False

        word = await db.pop_next_word(guild_id)
        if not word:
            print(f"[WOTD] ❌ No words left for guild {guild_id}")
            return False

        channel = self.bot.get_channel(cfg["post_channel"])
        if not channel:
            print(f"[WOTD] ⚠️ Post channel not found for guild {guild_id}")
            return False

        await channel.send(
            f"**Word of the day is:**\n"
            f"## {word}\n"
            f"Drop bars using this word in <#{cfg['bars_channel']}>\n"
            f"<@&{cfg['role_id']}>"
        )

        await db.upsert_guild_config(
            guild_id,
            last_post=datetime.now(pytz.UTC).isoformat(),
            current_wotd=word,
        )
        print(f"[WOTD] ✅ Posted '{word}' in guild {guild_id}")
        return True

    # ── /setup ────────────────────────────────────────────────────────────────

    @app_commands.command(name="setup", description="Configure bot for this server (Admin).")
    @admin_or_owner()
    async def setup_cmd(
        self,
        inter: discord.Interaction,
        post_channel: discord.TextChannel,
        bars_channel: discord.TextChannel,
        role: discord.Role,
        daily_time: str,
        timezone: str = "Asia/Kolkata",
        wotd_action: str = "color",
    ) -> None:
        try:
            pytz.timezone(timezone)
        except pytz.UnknownTimeZoneError:
            await inter.response.send_message(
                f"⚠️ Unknown timezone `{timezone}`. Use a valid tz string like `Asia/Kolkata`.",
                ephemeral=True,
            )
            return

        try:
            hour, minute = map(int, daily_time.split(":"))
            assert 0 <= hour <= 23 and 0 <= minute <= 59
        except Exception:
            await inter.response.send_message(
                "⚠️ `daily_time` must be in `HH:MM` format, e.g. `07:00`.",
                ephemeral=True,
            )
            return

        valid_actions = ("color", "forward", "ping")
        if wotd_action not in valid_actions:
            await inter.response.send_message(
                f"⚠️ `wotd_action` must be one of: `color`, `forward`, `ping`.",
                ephemeral=True,
            )
            return

        await db.upsert_guild_config(
            inter.guild.id,
            post_channel=post_channel.id,
            bars_channel=bars_channel.id,
            role_id=role.id,
            daily_time=daily_time,
            timezone=timezone,
            wotd_action=wotd_action,
        )

        action_desc = {
            "color": "green embed only",
            "forward": "forward to bars channel",
            "ping": "forward + ping role",
        }[wotd_action]

        await inter.response.send_message(
            f"✅ Setup updated! WOTD action set to **{wotd_action}** ({action_desc}).",
            ephemeral=True,
        )

    # ── /add_words ────────────────────────────────────────────────────────────

    @app_commands.command(name="add_words", description="Add comma-separated words to the queue (Staff).")
    @staff_only()
    async def add_words(self, inter: discord.Interaction, words: str) -> None:
        word_list = [w.strip() for w in words.split(",") if w.strip()]
        if not word_list:
            await inter.response.send_message("⚠️ No valid words provided.", ephemeral=True)
            return
        added = await db.add_words(inter.guild.id, word_list)
        skipped = len(word_list) - added
        msg = f"✅ Added **{added}** word(s)."
        if skipped:
            msg += f" Skipped **{skipped}** duplicate(s)."
        await inter.response.send_message(msg, ephemeral=True)

    # ── /view_words ───────────────────────────────────────────────────────────

    @app_commands.command(name="view_words", description="View remaining words in the queue (Admin).")
    @staff_only()
    async def view_words(self, inter: discord.Interaction) -> None:
        words = await db.get_words(inter.guild.id)
        if not words:
            await inter.response.send_message("📭 No words left.", ephemeral=True)
            return
        lines = [f"{i+1}. {w}" for i, w in enumerate(words)]
        text = "\n".join(lines)
        if len(text) > 1900:
            text = text[:1900] + "\n…(truncated)"
        await inter.response.send_message(f"📜 Word queue:\n{text}", ephemeral=True)

    # ── /remove_word ──────────────────────────────────────────────────────────

    @app_commands.command(name="remove_word", description="Remove a word from the queue (Admin).")
    @admin_or_owner()
    async def remove_word(self, inter: discord.Interaction, word: str) -> None:
        removed = await db.remove_word(inter.guild.id, word)
        if removed:
            await inter.response.send_message(f"🗑️ Removed **{word}**.", ephemeral=True)
        else:
            await inter.response.send_message("⚠️ Word not found in the queue.", ephemeral=True)

    # ── /word_count ───────────────────────────────────────────────────────────

    @app_commands.command(name="word_count", description="Show how many words are left in the queue.")
    async def word_count(self, inter: discord.Interaction) -> None:
        count = await db.word_count(inter.guild.id)
        await inter.response.send_message(f"🧾 Words left: **{count}**", ephemeral=True)

    # ── /next_wordtime ────────────────────────────────────────────────────────

    @app_commands.command(name="next_wordtime", description="See when the next word will post (Admin).")
    @admin_or_owner()
    async def next_wordtime(self, inter: discord.Interaction) -> None:
        cfg = await db.get_guild_config(inter.guild.id)
        if not cfg:
            await inter.response.send_message("⚠️ Bot not configured. Run `/setup` first.", ephemeral=True)
            return

        try:
            tz = pytz.timezone(cfg.get("timezone") or "Asia/Kolkata")
        except Exception:
            tz = pytz.timezone("Asia/Kolkata")

        now = datetime.now(tz)
        try:
            hour, minute = map(int, cfg["daily_time"].split(":"))
        except Exception:
            await inter.response.send_message(
                "⚠️ `daily_time` is misconfigured. Run `/setup` again.", ephemeral=True
            )
            return

        next_post = tz.localize(datetime(now.year, now.month, now.day, hour, minute))
        if now >= next_post:
            next_post += timedelta(days=1)

        diff = next_post - now
        hours, rem = divmod(int(diff.total_seconds()), 3600)
        mins = rem // 60

        await inter.response.send_message(
            f"🕓 **Next Post:** {next_post.strftime('%Y-%m-%d %H:%M %Z')}\n"
            f"⏳ **Time left:** {hours}h {mins}m",
            ephemeral=True,
        )

    # ── /post_now ─────────────────────────────────────────────────────────────

    @app_commands.command(name="post_now", description="Post the next word immediately (Admin).")
    @admin_or_owner()
    async def post_now(self, inter: discord.Interaction) -> None:
        await inter.response.defer(ephemeral=True)
        success = await self._post_word(inter.guild.id)
        if success:
            await inter.followup.send("✅ Posted!")
        else:
            await inter.followup.send("⚠️ Could not post. Check config and word queue.")

    # ── /topverse ─────────────────────────────────────────────────────────────

    @app_commands.command(name="topverse", description="Show today's top rated verse(s).")
    async def topverse(self, inter: discord.Interaction) -> None:
        try:
            tz = pytz.timezone("Asia/Kolkata")
            cfg = await db.get_guild_config(inter.guild.id)
            if cfg and cfg.get("timezone"):
                tz = pytz.timezone(cfg["timezone"])
        except Exception:
            tz = pytz.timezone("Asia/Kolkata")

        today = datetime.now(tz).date()

        top_wotd    = await db.get_top_verse(inter.guild.id, today, had_wotd=True)
        top_overall = await db.get_top_verse(inter.guild.id, today, had_wotd=None)

        if not top_overall:
            await inter.response.send_message("📭 No verses rated today yet.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🏆 Top Verses Today — {today.strftime('%d %b %Y')}",
            color=discord.Color.gold(),
        )

        if top_wotd:
            user_mention = f"<@{top_wotd['user_id']}>"
            embed.add_field(
                name=f"🔥 Best WOTD Verse  •  {top_wotd['score']}/10",
                value=user_mention,
                inline=False,
            )

        if top_overall and (not top_wotd or top_overall["id"] != top_wotd["id"]):
            user_mention = f"<@{top_overall['user_id']}>"
            embed.add_field(
                name=f"🎤 Best Overall  •  {top_overall['score']}/10",
                value=user_mention,
                inline=False,
            )

        await inter.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WordOfDayCog(bot))

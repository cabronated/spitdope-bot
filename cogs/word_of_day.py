# cogs/word_of_day.py
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import pytz
import os
from utils.storage import guild_file, load_json, save_json

# perms checker
OWNER_ID = 1485243296564641975  # replace with your actual Discord user ID

def admin_or_owner():
    async def predicate(interaction: discord.Interaction) -> bool:
        return (
            interaction.user.id == OWNER_ID
            or interaction.user.guild_permissions.administrator
        )
    return app_commands.check(predicate)
    

DEFAULT_CONFIG = {
    "post_channel": None,
    "bars_channel": None,
    "role_id": None,
    "daily_time": "07:00",
    "timezone": "Asia/Kolkata",
    "words": [],
    "last_post": None,
}

class WordOfDayCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Start the background task when the cog is loaded
        self.daily_word_task.start()

    def cog_unload(self):
        # Clean up and stop the background task when the cog is unloaded
        self.daily_word_task.cancel()

    # ========== Background Task ==========
    @tasks.loop(minutes=1)
    async def daily_word_task(self):
        # Ensure the bot is connected before trying to do anything
        await self.bot.wait_until_ready()
        
        DATA_DIR = "bot_data"
        if not os.path.exists(DATA_DIR):
            return

        for file in os.listdir(DATA_DIR):
            if not file.endswith(".json"):
                continue
            
            try:
                gid = int(file.split(".")[0])
            except ValueError:
                continue

            path = guild_file(gid)
            cfg = await load_json(path, DEFAULT_CONFIG)
            
            # Check if setup is fully complete for this guild
            if not (cfg.get("post_channel") and cfg.get("bars_channel") and cfg.get("role_id")):
                continue

            try:
                tz = pytz.timezone(cfg.get("timezone", "Asia/Kolkata"))
            except Exception:
                tz = pytz.timezone("Asia/Kolkata")
                
            local_now = datetime.now(tz)
            
            # Parse target time
            try:
                hour, minute = map(int, cfg["daily_time"].split(":"))
            except (ValueError, KeyError):
                # Fallback if config is broken
                hour, minute = 7, 0 
            
            # Check if we already posted today
            last_post_iso = cfg.get("last_post")
            last_post_date = None
            if last_post_iso:
                # Convert the UTC ISO string back to local date for comparison
                try:
                    last_post_dt = datetime.fromisoformat(last_post_iso)
                    if last_post_dt.tzinfo is None:
                        last_post_dt = last_post_dt.replace(tzinfo=pytz.UTC)
                    last_post_date = last_post_dt.astimezone(tz).date()
                except ValueError:
                    pass

            # If it's the right hour and minute, and we haven't posted today yet
            if local_now.hour == hour and local_now.minute == minute:
                if last_post_date != local_now.date():
                    await self.post_word(gid)

    # ========== Core Posting Logic ==========
    async def post_word(self, gid: int) -> bool:
        path = guild_file(gid)
        cfg = await load_json(path, DEFAULT_CONFIG)
        words = cfg.get("words", [])
        
        if not words:
            print(f"[AUTO] ❌ No words left for guild {gid}")
            return False
            
        channel = self.bot.get_channel(cfg["post_channel"])
        if not channel:
            print(f"[AUTO] ⚠️ Missing post channel for guild {gid}")
            return False

        word = words.pop(0)
        msg = (
            f"**Word of the day is:**\n"
            f"## {word}\n"
            f"Drop bars using this word in <#{cfg['bars_channel']}>\n"
            f"<@&{cfg['role_id']}>"
        )
        
        await channel.send(msg)
        
        cfg["words"] = words
        # Save last post time as UTC ISO format
        cfg["last_post"] = datetime.now(pytz.UTC).isoformat()
        await save_json(path, cfg)
        print(f"[AUTO] ✅ Posted WOTD '{word}' in guild {gid}")
        return True

    # ========== Slash commands ==========
    @app_commands.command(name="setup", description="Configure bot for this server (Admin)")
    @admin_or_owner()
    async def setup(self, inter: discord.Interaction,
                    post_channel: discord.TextChannel,
                    bars_channel: discord.TextChannel,
                    role: discord.Role,
                    daily_time: str,
                    timezone: str = "Asia/Kolkata"):
        cfg = await load_json(guild_file(inter.guild.id), DEFAULT_CONFIG)
        cfg.update({
            "post_channel": post_channel.id,
            "bars_channel": bars_channel.id,
            "role_id": role.id,
            "daily_time": daily_time,
            "timezone": timezone,
        })
        await save_json(guild_file(inter.guild.id), cfg)
        await inter.response.send_message("✅ Setup updated!", ephemeral=True)

    @app_commands.command(name="add_words", description="Add comma-separated words (Admin)")
    @admin_or_owner()
    async def add_words(self, inter: discord.Interaction, words: str):
        path = guild_file(inter.guild.id)
        cfg = await load_json(path, DEFAULT_CONFIG)
        count = 0
        for w in [x.strip() for x in words.split(",") if x.strip()]:
            if w.lower() not in [x.lower() for x in cfg["words"]]:
                cfg["words"].append(w)
                count += 1
        await save_json(path, cfg)
        await inter.response.send_message(f"✅ Added {count} words!", ephemeral=True)

    @app_commands.command(name="view_words", description="View remaining words (Admin)")
    @admin_or_owner()
    async def view_words(self, inter: discord.Interaction):
        cfg = await load_json(guild_file(inter.guild.id), DEFAULT_CONFIG)
        words = cfg["words"]
        if not words:
            return await inter.response.send_message("📭 No words left.", ephemeral=True)
        msg = "\n".join([f"{i+1}. {w}" for i, w in enumerate(words)])
        await inter.response.send_message(f"📜 Word list:\n{msg}", ephemeral=True)

    @app_commands.command(name="remove_word", description="Remove word (Admin)")
    @admin_or_owner()
    async def remove_word(self, inter: discord.Interaction, word: str):
        path = guild_file(inter.guild.id)
        cfg = await load_json(path, DEFAULT_CONFIG)
        for w in cfg["words"]:
            if w.lower() == word.lower():
                cfg["words"].remove(w)
                await save_json(path, cfg)
                return await inter.response.send_message(f"🗑️ Removed **{word}**", ephemeral=True)
        await inter.response.send_message("⚠️ Word not found.", ephemeral=True)

    @app_commands.command(name="word_count", description="Show words left (Admin)")
    @admin_or_owner()
    async def word_count(self, inter: discord.Interaction):
        cfg = await load_json(guild_file(inter.guild.id), DEFAULT_CONFIG)
        await inter.response.send_message(f"🧾 Words left: **{len(cfg['words'])}**", ephemeral=True)

    @app_commands.command(name="next_wordtime", description="See when the next word will post (Admin)")
    @admin_or_owner()
    async def next_wordtime(self, inter: discord.Interaction):
        cfg = await load_json(guild_file(inter.guild.id), DEFAULT_CONFIG)
        try:
            tz = pytz.timezone(cfg.get("timezone", "Asia/Kolkata"))
        except Exception:
            tz = pytz.timezone("Asia/Kolkata")
            
        now = datetime.now(tz)
        try:
            hour, minute = map(int, cfg["daily_time"].split(":"))
        except (ValueError, KeyError):
            return await inter.response.send_message("⚠️ `daily_time` is not configured correctly. Please run `/setup` again.", ephemeral=True)
            
        next_time = tz.localize(datetime(now.year, now.month, now.day, hour, minute))
        if now >= next_time:
            next_time += timedelta(days=1)
            
        diff = next_time - now
        hours, remainder = divmod(int(diff.total_seconds()), 3600)
        mins = remainder // 60
        
        await inter.response.send_message(
            f"🕓 **Next Post:** {next_time.strftime('%Y-%m-%d %H:%M %Z')}\n"
            f"⏳ Time left: {hours}h {mins}m",
            ephemeral=True
        )

    @app_commands.command(name="post_now", description="Post next word immediately (Admin)")
    @admin_or_owner()
    async def post_now(self, inter: discord.Interaction):
        # We can defer response if sending takes a moment
        await inter.response.defer(ephemeral=True)
        success = await self.post_word(inter.guild.id)
        if success:
            await inter.followup.send("✅ Posted manually!")
        else:
            await inter.followup.send("⚠️ Could not post. Check configuration or word list.")

async def setup(bot):
    await bot.add_cog(WordOfDayCog(bot))

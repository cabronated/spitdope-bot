# cogs/staff.py
import discord
from discord.ext import commands
from discord import app_commands

from utils.checks import staff_only


class Staff(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── error handler for this cog ────────────────────────────────────────────

    async def cog_app_command_error(
        self,
        inter: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        if isinstance(error, app_commands.CheckFailure):
            await inter.response.send_message(
                "🚫 This command is for staff and admins only.",
                ephemeral=True,
            )

    # ── /thread ───────────────────────────────────────────────────────────────

    @app_commands.command(name="thread", description="Create a thread in this channel (Staff).")
    @staff_only()
    async def thread(self, inter: discord.Interaction, name: str) -> None:
        thread = await inter.channel.create_thread(
            name=name,
            type=discord.ChannelType.public_thread,
        )
        await inter.response.send_message(f"✅ Thread created: {thread.mention}")
        )

    # ── /thread ───────────────────────────────────────────────────────────────
    @app_commands.command(name="chatbattle", description="Start a chat battle between two users (Staff).")
    @staff_only()
    async def chatbattle(
        self,
        inter: discord.Interaction,
        user1: discord.Member,
        user2: discord.Member,
    ) -> None:
        thread = await inter.channel.create_thread(
            name=f"⚔️ {user1.display_name} vs {user2.display_name}",
            type=discord.ChannelType.public_thread,
        )
    
        embed = discord.Embed(
            title="⚔️ Chat Battle",
            description=(
                f"A battle has been called between {user1.mention} and {user2.mention}!\n\n"
                f"Head to {thread.mention} and drop your verses.\n"
                f"May the best rapper win. 🎤"
            ),
            color=discord.Color.red(),
        )
        embed.set_footer(text=f"Battle started by {inter.user.display_name}")
    
        # pings outside embed so they actually get notified
        await inter.response.send_message(
            content=f"{user1.mention} {user2.mention}",
            embed=embed,
        )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Staff(bot))

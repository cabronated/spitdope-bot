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
        await inter.response.send_message(
            f"✅ Thread created: {thread.mention}",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Staff(bot))

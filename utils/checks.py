# utils/checks.py
"""
Reusable app_commands checks so we don't copy-paste them into every cog.
"""

import os
import discord
from discord import app_commands

OWNER_ID = int(os.getenv("OWNER_ID", "1485243296564641975"))


def admin_or_owner() -> app_commands.check:
    """Allow server admins and the bot owner."""
    async def predicate(interaction: discord.Interaction) -> bool:
        return (
            interaction.user.id == OWNER_ID
            or interaction.user.guild_permissions.administrator
        )
    return app_commands.check(predicate)

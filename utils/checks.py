# utils/checks.py
"""
Reusable app_commands checks so we don't copy-paste them into every cog.
"""

import os
import discord
from discord import app_commands

OWNER_ID = int(os.getenv("OWNER_ID", "1485243296564641975"))

# Add role IDs and user IDs you want to count as staff
STAFF_ROLE_IDS: set[int] = {1181266645965094912}

STAFF_USER_IDS: set[int] = {}


def admin_or_owner() -> app_commands.check:
    """Allow server admins and the bot owner."""
    async def predicate(interaction: discord.Interaction) -> bool:
        return (
            interaction.user.id == OWNER_ID
            or interaction.user.guild_permissions.administrator
        )
    return app_commands.check(predicate)


def staff_only() -> app_commands.check:
    """Allow owner, admins, specific role IDs, and specific user IDs."""
    async def predicate(interaction: discord.Interaction) -> bool:
        user = interaction.user

        if user.id == OWNER_ID:
            return True
        if user.guild_permissions.administrator:
            return True
        if user.id in STAFF_USER_IDS:
            return True
        if any(role.id in STAFF_ROLE_IDS for role in user.roles):
            return True
        return False

    return app_commands.check(predicate)

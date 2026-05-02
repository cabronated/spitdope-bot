# cogs/admin.py
import os
import sys
import discord
from discord.ext import commands

from utils.checks import OWNER_ID


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _is_owner(self, ctx: commands.Context) -> bool:
        return ctx.author.id == OWNER_ID

    @commands.command(name="restart")
    async def restart(self, ctx: commands.Context) -> None:
        if not self._is_owner(ctx):
            return  

        await ctx.message.add_reaction("🔄")
        await ctx.send("Restarting...", delete_after=3)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    @commands.command(name="shutdown")
    async def shutdown(self, ctx: commands.Context) -> None:
        if not self._is_owner(ctx):
            return

        await ctx.message.add_reaction("⛔")
        await ctx.send("Shutting down.", delete_after=3)
        await self.bot.close()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))

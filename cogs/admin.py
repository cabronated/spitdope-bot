import os
import sys
import discord
from discord.ext import commands

from utils.checks import OWNER_ID

RESTART_FLAG = ".restart_channel"  # temp file to remember where to reply


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _is_owner(self, ctx: commands.Context) -> bool:
        return ctx.author.id == OWNER_ID

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if not os.path.exists(RESTART_FLAG):
            return
        with open(RESTART_FLAG) as f:
            channel_id = int(f.read().strip())
        os.remove(RESTART_FLAG)
        channel = self.bot.get_channel(channel_id)
        if channel:
            await channel.send("✅ Back online.")

    @commands.command(name="restart")
    async def restart(self, ctx: commands.Context) -> None:
        if not self._is_owner(ctx):
            return

        with open(RESTART_FLAG, "w") as f:
            f.write(str(ctx.channel.id))

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

    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context) -> None:
        if not self._is_owner(ctx):
            return
        await ctx.send(f"🏓 {round(self.bot.latency * 1000)}ms")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))

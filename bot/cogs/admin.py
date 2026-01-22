import discord
from discord.ext import commands

from bot.main import db
from bot.utils import TELLER_NAME

class AdminCog(commands.Cog):
    """Admin commands to configure the bot (set FORUM_ID and FINANCE_ROLE_ID)."""

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="set_forum", description="Set the forum (parent) channel ID for automatic responses.")
    @commands.has_permissions(administrator=True)
    async def set_forum(self, ctx: commands.Context, forum_id: int):
        """
        Usage (slash): /set_forum forum_id:123456789012345678
        Usage (prefix): ub!set_forum 123456789012345678
        """
        await db.set_config("FORUM_ID", str(forum_id))
        await ctx.send(f"✅ Saved FORUM_ID = `{forum_id}`")

    @commands.hybrid_command(name="set_finance_role", description="Set the role to ping for finance notifications.")
    @commands.has_permissions(administrator=True)
    async def set_finance_role(self, ctx: commands.Context, role: discord.Role):
        """
        Usage (slash): /set_finance_role role:@Finance
        Usage (prefix): ub!set_finance_role @Finance
        """
        await db.set_config("FINANCE_ROLE_ID", str(role.id))
        await ctx.send(f"✅ Saved FINANCE_ROLE_ID = `{role.id}` ({role.mention})")

    @commands.hybrid_command(name="show_config", description="Show saved configuration values.")
    @commands.has_permissions(administrator=True)
    async def show_config(self, ctx: commands.Context):
        forum = await db.get_config("FORUM_ID") or "not set"
        fin = await db.get_config("FINANCE_ROLE_ID") or "not set"
        await ctx.send(f"Configuration:\n- FORUM_ID: `{forum}`\n- FINANCE_ROLE_ID: `{fin}`")

    @set_forum.error
    @set_finance_role.error
    @show_config.error
    async def _config_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You need administrator privileges to run this command.")
        else:
            await ctx.send(f"Command failed: {error}")


def setup(bot):
    bot.add_cog(AdminCog(bot))

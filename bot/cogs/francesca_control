import discord
from discord.ext import commands
import os

class FrancescaControl(commands.Cog):
    """Control when Francesca responds in threads"""
    
    def __init__(self, bot):
        self.bot = bot
        # Track which users have paused Francesca (user_id -> True/False)
        self.paused_users = {}
        # Role ID that can close threads
        self.closer_role_id = int(os.getenv("THREAD_CLOSER_ROLE_ID", "0"))
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for Francesca control phrases"""
        if message.author.bot:
            return
        
        content = message.content.strip().lower()
        
        # Check for "Thanks Francesca" - pause responses for this user
        if "thanks francesca" in content or "thank you francesca" in content:
            self.paused_users[message.author.id] = True
            await message.add_reaction("👋")
            return
        
        # Check for "Hey Francesca" - resume responses for this user
        if "hey francesca" in content or "hi francesca" in content or "hello francesca" in content:
            if message.author.id in self.paused_users:
                self.paused_users[message.author.id] = False
            await message.add_reaction("👋")
            return
        
        # Check for "Close Francesca" - close thread if user has proper role
        if "close francesca" in content:
            # Check if in a thread
            if not isinstance(message.channel, discord.Thread):
                await message.reply("⚠️ This command only works in forum threads!")
                return
            
            # Check if user has the closer role
            if not self.closer_role_id:
                await message.reply("⚠️ Thread closer role not configured!")
                return
            
            if not any(role.id == self.closer_role_id for role in message.author.roles):
                await message.reply("❌ You don't have permission to close threads!")
                return
            
            # Close the thread
            thread = message.channel
            
            # Add [CLOSED] prefix if not already there
            new_name = thread.name
            if not new_name.startswith("[CLOSED]"):
                new_name = f"[CLOSED] {new_name}"
            
            try:
                await thread.edit(name=new_name, archived=True, locked=True)
                await message.add_reaction("✅")
            except discord.Forbidden:
                await message.reply("❌ I don't have permission to close this thread!")
            except discord.HTTPException as e:
                await message.reply(f"❌ Error closing thread: {e}")
    
    def is_user_paused(self, user_id: int) -> bool:
        """Check if a user has paused Francesca"""
        return self.paused_users.get(user_id, False)
    
    @commands.hybrid_command(name="set_closer_role")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def set_closer_role(self, ctx, role: discord.Role):
        """Set the role that can close threads with 'Close Francesca' (Admin/Owner only)
        
        Usage: !set_closer_role @RoleName
        """
        self.closer_role_id = role.id
        
        embed = discord.Embed(
            title="✅ Thread Closer Role Set",
            description=f"Users with {role.mention} can now close threads with 'Close Francesca'",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="francesca_status")
    async def francesca_status(self, ctx):
        """Check if Francesca is paused for you"""
        is_paused = self.is_user_paused(ctx.author.id)
        
        if is_paused:
            embed = discord.Embed(
                title="⏸️ Francesca is Paused",
                description="Say **'Hey Francesca'** to resume responses",
                color=discord.Color.orange()
            )
        else:
            embed = discord.Embed(
                title="✅ Francesca is Active",
                description="Say **'Thanks Francesca'** to pause responses",
                color=discord.Color.green()
            )
        
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(FrancescaControl(bot))

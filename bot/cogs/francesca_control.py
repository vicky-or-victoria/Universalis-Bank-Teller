import discord
from discord.ext import commands
import os

class FrancescaControl(commands.Cog):
    """Control when Francesca responds in threads and channels"""
    
    def __init__(self, bot):
        self.bot = bot
        # Track which channels/threads have paused Francesca (channel_id -> True/False)
        self.paused_channels = {}
        # Role ID that can close threads
        self.closer_role_id = int(os.getenv("THREAD_CLOSER_ROLE_ID", "0"))
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for Francesca control phrases"""
        if message.author.bot:
            return
        
        content = message.content.strip().lower()
        
        # Check for "Thanks Francesca" - pause responses for THIS CHANNEL/THREAD
        if "thanks francesca" in content or "thank you francesca" in content:
            self.paused_channels[message.channel.id] = True
            await message.add_reaction("👋")
            await message.reply("You're welcome! I'll step back now. Say **'Hey Francesca'** if you need me again!")
            return
        
        # Check for "Hey Francesca" - resume responses for THIS CHANNEL/THREAD
        if "hey francesca" in content or "hi francesca" in content or "hello francesca" in content:
            if message.channel.id in self.paused_channels:
                self.paused_channels[message.channel.id] = False
            await message.add_reaction("👋")
            await message.reply("Hello! I'm back to help you! *smiles warmly*")
            return
        
        # Check for "Close Francesca" - close thread if user has proper role
        if "close francesca" in content:
            # Check if in a thread
            if not isinstance(message.channel, discord.Thread):
                await message.reply("⚠️ This command only works in forum threads!")
                return
            
            # Check if user has the closer role (or is admin/owner)
            has_permission = False
            
            # Check for admin permissions
            if message.author.guild_permissions.administrator:
                has_permission = True
            # Check for closer role
            elif self.closer_role_id and any(role.id == self.closer_role_id for role in message.author.roles):
                has_permission = True
            # Check if user is bot owner
            elif await self.bot.is_owner(message.author):
                has_permission = True
            
            if not has_permission:
                await message.reply("❌ You don't have permission to close threads!")
                return
            
            # Close the thread
            thread = message.channel
            
            # Add [CLOSED] prefix if not already there
            new_name = thread.name
            if not new_name.startswith("[CLOSED]"):
                new_name = f"[CLOSED] {new_name}"
            
            try:
                # Unarchive first if needed
                if thread.archived:
                    await thread.edit(archived=False)
                
                # Close and archive
                await thread.edit(name=new_name, archived=True, locked=True)
                
                embed = discord.Embed(
                    title="👋 Thread Closed",
                    description="This thread has been closed and archived. Thank you for banking with us!",
                    color=discord.Color.blue()
                )
                await thread.send(embed=embed)
            except discord.Forbidden:
                await message.reply("❌ I don't have permission to close this thread!")
            except discord.HTTPException as e:
                await message.reply(f"❌ Error closing thread: {e}")
    
    def is_channel_paused(self, channel_id: int) -> bool:
        """Check if Francesca is paused in this channel/thread"""
        return self.paused_channels.get(channel_id, False)
    
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
        """Check if Francesca is paused in this channel/thread"""
        is_paused = self.is_channel_paused(ctx.channel.id)
        
        if is_paused:
            embed = discord.Embed(
                title="⏸️ Francesca is Paused in This Channel",
                description="Say **'Hey Francesca'** to resume responses here",
                color=discord.Color.orange()
            )
        else:
            embed = discord.Embed(
                title="✅ Francesca is Active in This Channel",
                description="Say **'Thanks Francesca'** to pause responses here",
                color=discord.Color.green()
            )
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="unpause_all")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def unpause_all(self, ctx):
        """Unpause Francesca in all channels (Admin/Owner only)"""
        count = len([v for v in self.paused_channels.values() if v])
        self.paused_channels.clear()
        
        embed = discord.Embed(
            title="✅ All Channels Unpaused",
            description=f"Francesca has been unpaused in {count} channel(s)/thread(s)",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(FrancescaControl(bot))

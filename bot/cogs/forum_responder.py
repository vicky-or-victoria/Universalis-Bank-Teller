import discord
from discord.ext import commands
import os

class ForumResponder(commands.Cog):
    """Automatic responses in forum channels"""
    
    def __init__(self, bot):
        self.bot = bot
        self.forum_channel_id = int(os.getenv("FORUM_CHANNEL_ID", "0"))
    
    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        """Respond when a new thread is created in the forum"""
        if thread.parent_id != self.forum_channel_id:
            return
        
        # Wait a moment for the initial message to be posted
        await asyncio.sleep(1)
        
        embed = discord.Embed(
            title="📋 Welcome to Universalis Banking",
            description=(
                "Thank you for creating a thread! Here's what you can do:\n\n"
                "**Financial Reports:**\n"
                "Post your report in format: `Company | Revenue | Expenses`\n\n"
                "**Stock Market:**\n"
                "• `ub!stocks` - View all available stocks\n"
                "• `ub!buy <ticker> <amount>` - Buy stocks\n"
                "• `ub!portfolio` - View your holdings\n\n"
                "**Company Management:**\n"
                "• `ub!register <company_name>` - Register a company\n"
                "• `ub!balance` - Check your balance"
            ),
            color=discord.Color.blue()
        )
        embed.set_footer(text="Universalis Bank Teller")
        
        await thread.send(embed=embed)
        
        # Track thread for auto-lock feature
        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "INSERT OR REPLACE INTO tracked_threads (thread_id) VALUES (?)",
                (thread.id,)
            )
            await self.bot.db.commit()
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Respond to messages in forum threads"""
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Check if message is in a thread of the forum channel
        if not isinstance(message.channel, discord.Thread):
            return
        
        if message.channel.parent_id != self.forum_channel_id:
            return
        
        # Update thread activity timestamp
        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "UPDATE tracked_threads SET last_activity = CURRENT_TIMESTAMP WHERE thread_id = ?",
                (message.channel.id,)
            )
            await self.bot.db.commit()
        
        # Check for financial report format
        if "|" in message.content and message.content.count("|") >= 2:
            # This might be a financial report, let the financial_reports cog handle it
            # We just acknowledge it here
            await message.add_reaction("📊")

async def setup(bot):
    await bot.add_cog(ForumResponder(bot))

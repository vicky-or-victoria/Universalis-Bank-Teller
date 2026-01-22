import discord
from discord.ext import commands, tasks
import random
from datetime import datetime, timedelta
import os

class BackgroundTasks(commands.Cog):
    """Background tasks for thread auto-lock and stock price fluctuation"""
    
    def __init__(self, bot):
        self.bot = bot
        self.auto_lock_threads.start()
        self.fluctuate_stock_prices.start()
    
    def cog_unload(self):
        """Stop tasks when cog is unloaded"""
        self.auto_lock_threads.cancel()
        self.fluctuate_stock_prices.cancel()
    
    @tasks.loop(hours=1)
    async def auto_lock_threads(self):
        """Auto-lock inactive threads in the forum channel"""
        forum_channel_id = int(os.getenv("FORUM_CHANNEL_ID", "0"))
        if not forum_channel_id:
            return
        
        try:
            # Get inactive threads (no activity for 7 days)
            cutoff = datetime.now() - timedelta(days=7)
            
            async with self.bot.db.cursor() as cursor:
                await cursor.execute(
                    """SELECT thread_id FROM tracked_threads 
                       WHERE last_activity < ?""",
                    (cutoff,)
                )
                inactive_threads = await cursor.fetchall()
            
            locked_count = 0
            for (thread_id,) in inactive_threads:
                try:
                    thread = self.bot.get_channel(thread_id)
                    if not thread:
                        # Try to fetch if not in cache
                        thread = await self.bot.fetch_channel(thread_id)
                    
                    if thread and isinstance(thread, discord.Thread):
                        if not thread.locked and not thread.archived:
                            await thread.edit(
                                locked=True,
                                archived=True,
                                reason="Auto-locked due to inactivity (7 days)"
                            )
                            
                            # Send notification
                            embed = discord.Embed(
                                title="🔒 Thread Auto-Locked",
                                description="This thread has been locked due to 7 days of inactivity.",
                                color=discord.Color.orange()
                            )
                            await thread.send(embed=embed)
                            locked_count += 1
                        
                        # Remove from tracking
                        async with self.bot.db.cursor() as cursor:
                            await cursor.execute(
                                "DELETE FROM tracked_threads WHERE thread_id = ?",
                                (thread_id,)
                            )
                            await self.bot.db.commit()
                
                except Exception as e:
                    print(f"Error locking thread {thread_id}: {e}")
            
            if locked_count > 0:
                print(f"✓ Auto-locked {locked_count} inactive thread(s)")
        
        except Exception as e:
            print(f"Error in auto_lock_threads task: {e}")
    
    @auto_lock_threads.before_loop
    async def before_auto_lock(self):
        """Wait for bot to be ready before starting"""
        await self.bot.wait_until_ready()
    
    @tasks.loop(hours=24)
    async def fluctuate_stock_prices(self):
        """Daily stock price fluctuation"""
        try:
            async with self.bot.db.cursor() as cursor:
                # Get all stocks
                await cursor.execute("SELECT id, ticker, price FROM stocks")
                stocks = await cursor.fetchall()
                
                if not stocks:
                    return
                
                changes = []
                for stock_id, ticker, current_price in stocks:
                    # Random fluctuation between -5% and +5%
                    change_percent = random.uniform(-0.05, 0.05)
                    new_price = current_price * (1 + change_percent)
                    
                    # Ensure minimum price of $0.01
                    new_price = max(0.01, round(new_price, 2))
                    
                    # Update price
                    await cursor.execute(
                        "UPDATE stocks SET price = ? WHERE id = ?",
                        (new_price, stock_id)
                    )
                    
                    changes.append({
                        'ticker': ticker,
                        'old_price': current_price,
                        'new_price': new_price,
                        'change_percent': change_percent * 100
                    })
                
                await self.bot.db.commit()
            
            # Log changes
            print(f"✓ Updated {len(changes)} stock price(s)")
            for change in changes:
                direction = "📈" if change['change_percent'] > 0 else "📉"
                print(f"  {direction} {change['ticker']}: ${change['old_price']:.2f} → ${change['new_price']:.2f} ({change['change_percent']:+.2f}%)")
            
            # Optional: Post to a stock updates channel
            updates_channel_id = os.getenv("STOCK_UPDATES_CHANNEL_ID")
            if updates_channel_id:
                try:
                    channel = self.bot.get_channel(int(updates_channel_id))
                    if channel:
                        embed = discord.Embed(
                            title="📊 Daily Stock Market Update",
                            description="Stock prices have been updated!",
                            color=discord.Color.blue(),
                            timestamp=datetime.now()
                        )
                        
                        for change in changes[:10]:  # Limit to first 10 to avoid embed limits
                            direction = "📈" if change['change_percent'] > 0 else "📉"
                            embed.add_field(
                                name=f"{direction} {change['ticker']}",
                                value=f"${change['old_price']:.2f} → ${change['new_price']:.2f} ({change['change_percent']:+.2f}%)",
                                inline=True
                            )
                        
                        if len(changes) > 10:
                            embed.set_footer(text=f"... and {len(changes) - 10} more stocks updated")
                        
                        await channel.send(embed=embed)
                except Exception as e:
                    print(f"Error posting stock updates: {e}")
        
        except Exception as e:
            print(f"Error in fluctuate_stock_prices task: {e}")
    
    @fluctuate_stock_prices.before_loop
    async def before_fluctuate(self):
        """Wait for bot to be ready before starting"""
        await self.bot.wait_until_ready()
    
    @commands.hybrid_command(name="market_status")
    @commands.has_permissions(administrator=True)
    async def market_status(self, ctx):
        """Check background task status (Admin only)"""
        embed = discord.Embed(
            title="🔧 Background Tasks Status",
            color=discord.Color.blue()
        )
        
        # Auto-lock status
        auto_lock_status = "✅ Running" if self.auto_lock_threads.is_running() else "❌ Stopped"
        auto_lock_next = self.auto_lock_threads.next_iteration
        if auto_lock_next:
            auto_lock_info = f"{auto_lock_status}\nNext run: <t:{int(auto_lock_next.timestamp())}:R>"
        else:
            auto_lock_info = auto_lock_status
        
        embed.add_field(
            name="🔒 Thread Auto-Lock",
            value=auto_lock_info,
            inline=False
        )
        
        # Stock fluctuation status
        fluctuate_status = "✅ Running" if self.fluctuate_stock_prices.is_running() else "❌ Stopped"
        fluctuate_next = self.fluctuate_stock_prices.next_iteration
        if fluctuate_next:
            fluctuate_info = f"{fluctuate_status}\nNext run: <t:{int(fluctuate_next.timestamp())}:R>"
        else:
            fluctuate_info = fluctuate_status
        
        embed.add_field(
            name="📈 Stock Price Fluctuation",
            value=fluctuate_info,
            inline=False
        )
        
        # Database stats
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("SELECT COUNT(*) FROM tracked_threads")
            thread_count = (await cursor.fetchone())[0]
            
            await cursor.execute("SELECT COUNT(*) FROM stocks")
            stock_count = (await cursor.fetchone())[0]
        
        embed.add_field(
            name="📊 Statistics",
            value=f"Tracked threads: {thread_count}\nActive stocks: {stock_count}",
            inline=False
        )
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(BackgroundTasks(bot))

import discord
from discord.ext import commands
from discord import app_commands

class Admin(commands.Cog):
    """Admin commands for bot management"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.hybrid_command(name="help")
    async def help_command(self, ctx):
        """Show all available commands"""
        embed = discord.Embed(
            title="🏦 Universalis Bank Teller - Commands",
            description="Here are all available commands:",
            color=discord.Color.blue()
        )
        
        # Financial Reports
        embed.add_field(
            name="📊 Financial Reports",
            value=(
                "`ub!report <company> <revenue> <expenses>` - Submit a report\n"
                "Or post: `Company | Revenue | Expenses` in any message"
            ),
            inline=False
        )
        
        # Stock Market
        embed.add_field(
            name="📈 Stock Market",
            value=(
                "`ub!register <company>` - Register a company\n"
                "`ub!ipo <ticker> <price> <shares>` - Launch an IPO\n"
                "`ub!stocks` - View all stocks\n"
                "`ub!buy <ticker> <amount>` - Buy stocks\n"
                "`ub!sell <ticker> <amount>` - Sell stocks\n"
                "`ub!portfolio [@user]` - View portfolio\n"
                "`ub!balance` - Check your balance"
            ),
            inline=False
        )
        
        # Admin
        embed.add_field(
            name="⚙️ Admin",
            value=(
                "`ub!market_status` - Check background tasks\n"
                "`ub!sync` - Sync slash commands\n"
                "`ub!stats` - View bot statistics"
            ),
            inline=False
        )
        
        embed.set_footer(text="All commands work with slash commands too!")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="sync")
    @commands.has_permissions(administrator=True)
    async def sync_commands(self, ctx):
        """Sync slash commands (Admin only)"""
        await ctx.defer()
        
        try:
            synced = await self.bot.tree.sync()
            await ctx.send(f"✅ Synced {len(synced)} command(s)")
        except Exception as e:
            await ctx.send(f"❌ Failed to sync: {e}")
    
    @commands.hybrid_command(name="stats")
    async def stats(self, ctx):
        """View bot statistics"""
        async with self.bot.db.cursor() as cursor:
            # Count companies
            await cursor.execute("SELECT COUNT(*) FROM companies")
            company_count = (await cursor.fetchone())[0]
            
            # Count stocks
            await cursor.execute("SELECT COUNT(*) FROM stocks")
            stock_count = (await cursor.fetchone())[0]
            
            # Count users
            await cursor.execute("SELECT COUNT(*) FROM users")
            user_count = (await cursor.fetchone())[0]
            
            # Count reports
            await cursor.execute("SELECT COUNT(*) FROM reports")
            report_count = (await cursor.fetchone())[0]
            
            # Total market cap
            await cursor.execute(
                "SELECT SUM(price * total_shares) FROM stocks"
            )
            market_cap = (await cursor.fetchone())[0] or 0
            
            # Most valuable company
            await cursor.execute("""
                SELECT c.name, MAX(s.price * s.total_shares) as value
                FROM stocks s
                JOIN companies c ON s.company_id = c.id
                GROUP BY c.name
                ORDER BY value DESC
                LIMIT 1
            """)
            top_company = await cursor.fetchone()
        
        embed = discord.Embed(
            title="📊 Universalis Bank Statistics",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="🏢 Companies", value=str(company_count), inline=True)
        embed.add_field(name="📈 Stocks", value=str(stock_count), inline=True)
        embed.add_field(name="👥 Active Users", value=str(user_count), inline=True)
        
        embed.add_field(name="📄 Reports Filed", value=str(report_count), inline=True)
        embed.add_field(name="💰 Total Market Cap", value=f"${market_cap:,.2f}", inline=True)
        embed.add_field(name="🏆 Top Company", value=top_company[0] if top_company else "N/A", inline=True)
        
        embed.add_field(
            name="🤖 Bot Info",
            value=f"Guilds: {len(self.bot.guilds)}\nLatency: {round(self.bot.latency * 1000)}ms",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="give")
    @commands.has_permissions(administrator=True)
    async def give_money(self, ctx, user: discord.User, amount: float):
        """Give money to a user (Admin only)"""
        if amount <= 0:
            await ctx.send("❌ Amount must be positive!")
            return
        
        async with self.bot.db.cursor() as cursor:
            # Ensure user exists
            await cursor.execute(
                "INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, ?)",
                (user.id, 0)
            )
            
            # Add money
            await cursor.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (amount, user.id)
            )
            
            await self.bot.db.commit()
            
            # Get new balance
            await cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user.id,))
            new_balance = (await cursor.fetchone())[0]
        
        embed = discord.Embed(
            title="💰 Money Added",
            description=f"Gave ${amount:,.2f} to {user.mention}",
            color=discord.Color.green()
        )
        embed.add_field(name="New Balance", value=f"${new_balance:,.2f}")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="reset_user")
    @commands.has_permissions(administrator=True)
    async def reset_user(self, ctx, user: discord.User):
        """Reset a user's balance and holdings (Admin only)"""
        async with self.bot.db.cursor() as cursor:
            # Delete holdings
            await cursor.execute("DELETE FROM holdings WHERE user_id = ?", (user.id,))
            
            # Reset balance to default
            await cursor.execute(
                "UPDATE users SET balance = 10000 WHERE user_id = ?",
                (user.id,)
            )
            
            await self.bot.db.commit()
        
        await ctx.send(f"✅ Reset {user.mention}'s account to default state")
    
    @commands.hybrid_command(name="adjust_price")
    @commands.has_permissions(administrator=True)
    async def adjust_price(self, ctx, ticker: str, new_price: float):
        """Manually adjust a stock price (Admin only)"""
        ticker = ticker.upper()
        
        if new_price <= 0:
            await ctx.send("❌ Price must be positive!")
            return
        
        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "SELECT price FROM stocks WHERE ticker = ?",
                (ticker,)
            )
            result = await cursor.fetchone()
            
            if not result:
                await ctx.send(f"❌ Stock '{ticker}' not found!")
                return
            
            old_price = result[0]
            
            await cursor.execute(
                "UPDATE stocks SET price = ? WHERE ticker = ?",
                (new_price, ticker)
            )
            await self.bot.db.commit()
        
        change = ((new_price - old_price) / old_price) * 100
        
        embed = discord.Embed(
            title="💹 Stock Price Adjusted",
            color=discord.Color.blue()
        )
        embed.add_field(name="Ticker", value=ticker, inline=True)
        embed.add_field(name="Old Price", value=f"${old_price:,.2f}", inline=True)
        embed.add_field(name="New Price", value=f"${new_price:,.2f}", inline=True)
        embed.add_field(name="Change", value=f"{change:+.2f}%", inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="reload")
    @commands.is_owner()
    async def reload_cog(self, ctx, cog: str):
        """Reload a cog (Owner only)"""
        try:
            await self.bot.reload_extension(f"cogs.{cog}")
            await ctx.send(f"✅ Reloaded `cogs.{cog}`")
        except Exception as e:
            await ctx.send(f"❌ Failed to reload: {e}")

async def setup(bot):
    await bot.add_cog(Admin(bot))

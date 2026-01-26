import discord
from discord.ext import commands, tasks
import random

class StockTrading(commands.Cog):
    """Core stock trading functionality - buy, sell, view stocks and portfolios"""
    
    def __init__(self, bot):
        self.bot = bot
        self.daily_fluctuation.start()
    
    def cog_unload(self):
        self.daily_fluctuation.cancel()
    
    async def get_user_balance(self, user_id: int) -> float:
        """Get or create user balance"""
        async with self.bot.db.acquire() as conn:
            row = await conn.fetchrow("SELECT balance FROM users WHERE user_id = $1", user_id)
            
            if not row:
                await conn.execute(
                    "INSERT INTO users (user_id, balance) VALUES ($1, $2)",
                    user_id, 50000
                )
                return 50000.0
            
            return float(row['balance'])
    
    async def update_user_balance(self, user_id: int, amount: float):
        """Update user balance"""
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                "UPDATE users SET balance = balance + $1 WHERE user_id = $2",
                amount, user_id
            )
    
    @commands.hybrid_command(name="stocks")
    async def list_stocks(self, ctx):
        """View all publicly traded stocks"""
        async with self.bot.db.acquire() as conn:
            stocks = await conn.fetch("""
                SELECT s.ticker, c.name, s.price, s.available_shares, s.total_shares
                FROM stocks s
                JOIN companies c ON s.company_id = c.id
                ORDER BY s.ticker
            """)
        
        if not stocks:
            await ctx.send("📉 No stocks available yet!")
            return
        
        embed = discord.Embed(
            title="📈 Stock Exchange",
            description="Available stocks for trading",
            color=discord.Color.blue()
        )
        
        for row in stocks:
            ticker = row['ticker']
            company = row['name']
            price = float(row['price'])
            available = row['available_shares']
            total = row['total_shares']
            owned_pct = ((total - available) / total * 100) if total > 0 else 0
            
            embed.add_field(
                name=f"**{ticker}** - {company}",
                value=f"💵 ${price:,.2f}/share\n📊 {available:,}/{total:,} available ({owned_pct:.1f}% owned)",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="buy")
    async def buy_stock(self, ctx, ticker: str, amount: int):
        """Buy shares of a stock
        
        Usage: !buy MYCO 10
        """
        ticker = ticker.upper()
        
        if amount <= 0:
            await ctx.send("❌ Amount must be positive!")
            return
        
        async with self.bot.db.acquire() as conn:
            # Get stock info
            stock = await conn.fetchrow(
                """SELECT s.id, s.price, s.available_shares, c.name
                   FROM stocks s
                   JOIN companies c ON s.company_id = c.id
                   WHERE s.ticker = $1""",
                ticker
            )
            
            if not stock:
                await ctx.send(f"❌ Stock '{ticker}' not found!")
                return
            
            stock_id = stock['id']
            price = float(stock['price'])
            available = stock['available_shares']
            company_name = stock['name']
            
            if amount > available:
                await ctx.send(f"❌ Only {available:,} shares available!")
                return
            
            # Check balance
            balance = await self.get_user_balance(ctx.author.id)
            total_cost = price * amount
            
            if balance < total_cost:
                await ctx.send(f"❌ Insufficient funds! Need ${total_cost:,.2f}, have ${balance:,.2f}")
                return
            
            # Execute purchase
            await conn.execute(
                "UPDATE stocks SET available_shares = available_shares - $1 WHERE id = $2",
                amount, stock_id
            )
            
            await self.update_user_balance(ctx.author.id, -total_cost)
            
            # Update holdings
            holding = await conn.fetchrow(
                "SELECT shares FROM holdings WHERE user_id = $1 AND stock_id = $2",
                ctx.author.id, stock_id
            )
            
            if holding:
                await conn.execute(
                    "UPDATE holdings SET shares = shares + $1 WHERE user_id = $2 AND stock_id = $3",
                    amount, ctx.author.id, stock_id
                )
            else:
                await conn.execute(
                    "INSERT INTO holdings (user_id, stock_id, shares) VALUES ($1, $2, $3)",
                    ctx.author.id, stock_id, amount
                )
        
        new_balance = balance - total_cost
        
        embed = discord.Embed(
            title="✅ Purchase Successful",
            color=discord.Color.green()
        )
        embed.add_field(name="Stock", value=f"{ticker} ({company_name})", inline=False)
        embed.add_field(name="Shares", value=f"{amount:,}", inline=True)
        embed.add_field(name="Price/Share", value=f"${price:,.2f}", inline=True)
        embed.add_field(name="Total Cost", value=f"${total_cost:,.2f}", inline=True)
        embed.add_field(name="New Balance", value=f"${new_balance:,.2f}", inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="sell")
    async def sell_stock(self, ctx, ticker: str, amount: int):
        """Sell shares of a stock
        
        Usage: !sell MYCO 5
        """
        ticker = ticker.upper()
        
        if amount <= 0:
            await ctx.send("❌ Amount must be positive!")
            return
        
        async with self.bot.db.acquire() as conn:
            # Get stock and holding info
            result = await conn.fetchrow(
                """SELECT s.id, s.price, h.shares, c.name
                   FROM stocks s
                   JOIN companies c ON s.company_id = c.id
                   LEFT JOIN holdings h ON s.id = h.stock_id AND h.user_id = $1
                   WHERE s.ticker = $2""",
                ctx.author.id, ticker
            )
            
            if not result or not result['shares']:
                await ctx.send(f"❌ You don't own any {ticker} shares!")
                return
            
            stock_id = result['id']
            price = float(result['price'])
            owned_shares = result['shares']
            company_name = result['name']
            
            if amount > owned_shares:
                await ctx.send(f"❌ You only own {owned_shares:,} shares!")
                return
            
            total_value = price * amount
            
            # Update holding
            if amount == owned_shares:
                await conn.execute(
                    "DELETE FROM holdings WHERE user_id = $1 AND stock_id = $2",
                    ctx.author.id, stock_id
                )
            else:
                await conn.execute(
                    "UPDATE holdings SET shares = shares - $1 WHERE user_id = $2 AND stock_id = $3",
                    amount, ctx.author.id, stock_id
                )
            
            # Return shares to market
            await conn.execute(
                "UPDATE stocks SET available_shares = available_shares + $1 WHERE id = $2",
                amount, stock_id
            )
            
            await self.update_user_balance(ctx.author.id, total_value)
        
        balance = await self.get_user_balance(ctx.author.id)
        
        embed = discord.Embed(
            title="✅ Sale Successful",
            color=discord.Color.green()
        )
        embed.add_field(name="Stock", value=f"{ticker} ({company_name})", inline=False)
        embed.add_field(name="Shares", value=f"{amount:,}", inline=True)
        embed.add_field(name="Price/Share", value=f"${price:,.2f}", inline=True)
        embed.add_field(name="Total Value", value=f"${total_value:,.2f}", inline=True)
        embed.add_field(name="New Balance", value=f"${balance:,.2f}", inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="portfolio")
    async def portfolio(self, ctx, user: discord.User = None):
        """View your investment portfolio"""
        user = user or ctx.author
        
        async with self.bot.db.acquire() as conn:
            holdings = await conn.fetch("""
                SELECT s.ticker, c.name, s.price, h.shares
                FROM holdings h
                JOIN stocks s ON h.stock_id = s.id
                JOIN companies c ON s.company_id = c.id
                WHERE h.user_id = $1
                ORDER BY (s.price * h.shares) DESC
            """, user.id)
        
        balance = await self.get_user_balance(user.id)
        
        embed = discord.Embed(
            title=f"📊 {user.display_name}'s Portfolio",
            color=discord.Color.blue()
        )
        
        if not holdings:
            embed.description = "No stock holdings"
        else:
            total_value = 0
            for row in holdings:
                ticker = row['ticker']
                company = row['name']
                price = float(row['price'])
                shares = row['shares']
                value = price * shares
                total_value += value
                embed.add_field(
                    name=f"{ticker} - {company}",
                    value=f"Shares: {shares:,}\nPrice: ${price:,.2f}\nValue: ${value:,.2f}",
                    inline=True
                )
            
            embed.add_field(
                name="💼 Total Portfolio Value",
                value=f"${total_value:,.2f}",
                inline=False
            )
        
        embed.add_field(name="💰 Cash Balance", value=f"${balance:,.2f}", inline=False)
        
        total_net_worth = balance + sum(float(row['price']) * row['shares'] for row in holdings)
        embed.set_footer(text=f"Net Worth: ${total_net_worth:,.2f}")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="balance")
    async def balance(self, ctx, user: discord.User = None):
        """Check cash balance
        
        Usage: !balance [@user]
        """
        target_user = user or ctx.author
        balance = await self.get_user_balance(target_user.id)
        
        if target_user == ctx.author:
            title = "💰 Your Balance"
        else:
            title = f"💰 {target_user.display_name}'s Balance"
        
        embed = discord.Embed(
            title=title,
            description=f"**${balance:,.2f}**",
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="transfer_money")
    async def transfer_money(self, ctx, user: discord.User, amount: float):
        """Transfer money to another user
        
        Usage: !transfer_money @user 1000
        """
        if amount <= 0:
            await ctx.send("❌ Amount must be positive!")
            return
        
        if user.id == ctx.author.id:
            await ctx.send("❌ You cannot transfer money to yourself!")
            return
        
        if user.bot:
            await ctx.send("❌ You cannot transfer money to a bot!")
            return
        
        balance = await self.get_user_balance(ctx.author.id)
        
        if balance < amount:
            await ctx.send(f"❌ Insufficient funds! You have ${balance:,.2f}")
            return
        
        # Execute transfer
        await self.update_user_balance(ctx.author.id, -amount)
        await self.update_user_balance(user.id, amount)
        
        new_balance = balance - amount
        
        embed = discord.Embed(
            title="💸 Transfer Successful",
            color=discord.Color.green()
        )
        embed.add_field(name="To", value=user.mention, inline=True)
        embed.add_field(name="Amount", value=f"${amount:,.2f}", inline=True)
        embed.add_field(name="Your New Balance", value=f"${new_balance:,.2f}", inline=False)
        
        await ctx.send(embed=embed)
        
        # Notify recipient
        try:
            recipient_embed = discord.Embed(
                title="💰 Money Received",
                description=f"You received **${amount:,.2f}** from {ctx.author.mention}!",
                color=discord.Color.gold()
            )
            await user.send(embed=recipient_embed)
        except:
            pass  # DMs disabled
    
    @tasks.loop(hours=24)
    async def daily_fluctuation(self):
        """Daily automatic stock price fluctuation"""
        try:
            async with self.bot.db.acquire() as conn:
                stocks = await conn.fetch("SELECT id, ticker, price FROM stocks")
                
                if not stocks:
                    return
                
                changes = []
                for row in stocks:
                    stock_id = row['id']
                    ticker = row['ticker']
                    price = float(row['price'])
                    
                    # Random fluctuation -5% to +5%
                    change_pct = random.uniform(-0.05, 0.05)
                    new_price = price * (1 + change_pct)
                    new_price = max(0.01, round(new_price, 2))
                    
                    await conn.execute(
                        "UPDATE stocks SET price = $1 WHERE id = $2",
                        new_price, stock_id
                    )
                    
                    changes.append((ticker, price, new_price, change_pct * 100))
            
            print(f"✅ Daily fluctuation: Updated {len(changes)} stock(s)")
            for ticker, old, new, pct in changes:
                emoji = "📈" if pct > 0 else "📉"
                print(f"  {emoji} {ticker}: ${old:.2f} → ${new:.2f} ({pct:+.2f}%)")
        
        except Exception as e:
            print(f"Error in daily fluctuation: {e}")
    
    @daily_fluctuation.before_loop
    async def before_daily_fluctuation(self):
        await self.bot.wait_until_ready()
    
    @commands.hybrid_command(name="fluctuate")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def manual_fluctuate(self, ctx):
        """Manually trigger stock price fluctuation (Admin/Owner only)"""
        async with ctx.typing():
            async with self.bot.db.acquire() as conn:
                stocks = await conn.fetch("SELECT id, ticker, price FROM stocks")
                
                if not stocks:
                    await ctx.send("📉 No stocks to fluctuate!")
                    return
                
                embed = discord.Embed(
                    title="📊 Stock Market Update",
                    description="Prices have been updated!",
                    color=discord.Color.blue()
                )
                
                for row in stocks:
                    stock_id = row['id']
                    ticker = row['ticker']
                    price = float(row['price'])
                    
                    change_pct = random.uniform(-0.05, 0.05)
                    new_price = price * (1 + change_pct)
                    new_price = max(0.01, round(new_price, 2))
                    
                    await conn.execute(
                        "UPDATE stocks SET price = $1 WHERE id = $2",
                        new_price, stock_id
                    )
                    
                    emoji = "📈" if change_pct > 0 else "📉"
                    embed.add_field(
                        name=f"{emoji} {ticker}",
                        value=f"${price:.2f} → ${new_price:.2f} ({change_pct * 100:+.2f}%)",
                        inline=True
                    )
            
            await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(StockTrading(bot))

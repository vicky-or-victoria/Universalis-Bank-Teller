import discord
from discord.ext import commands, tasks
import random
from datetime import datetime

class StockMarket(commands.Cog):
    """Public stock market for player companies"""
    
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
    
    @commands.hybrid_command(name="go_public")
    async def go_public(self, ctx, company_name: str, ticker: str, price: float, shares: int):
        """Take your company public on the stock market
        
        Usage: !go_public "My Company" MYCO 100.00 1000
        """
        ticker = ticker.upper()
        
        if price <= 0 or shares <= 0:
            await ctx.send("❌ Price and shares must be positive!")
            return
        
        if len(ticker) > 5:
            await ctx.send("❌ Ticker symbol must be 5 characters or less!")
            return
        
        async with self.bot.db.acquire() as conn:
            # Check if user owns this company
            company = await conn.fetchrow(
                "SELECT id, is_public FROM companies WHERE owner_id = $1 AND name = $2",
                ctx.author.id, company_name
            )
            
            if not company:
                await ctx.send("❌ You don't own a company with that name!")
                return
            
            company_id = company['id']
            is_public = company['is_public']
            
            if is_public:
                await ctx.send("❌ This company is already public!")
                return
            
            # Check if ticker exists
            existing_ticker = await conn.fetchrow("SELECT id FROM stocks WHERE ticker = $1", ticker)
            if existing_ticker:
                await ctx.send(f"❌ Ticker '{ticker}' is already in use!")
                return
            
            # Create stock and mark company as public
            await conn.execute(
                "INSERT INTO stocks (company_id, ticker, price, available_shares, total_shares) VALUES ($1, $2, $3, $4, $5)",
                company_id, ticker, price, shares, shares
            )
            
            await conn.execute(
                "UPDATE companies SET is_public = $1 WHERE id = $2",
                True, company_id
            )
        
        embed = discord.Embed(
            title="🎉 IPO Launch!",
            description=f"**{company_name}** is now publicly traded!",
            color=discord.Color.green()
        )
        embed.add_field(name="Ticker", value=ticker, inline=True)
        embed.add_field(name="Initial Price", value=f"${price:,.2f}", inline=True)
        embed.add_field(name="Shares Available", value=f"{shares:,}", inline=True)
        embed.add_field(name="Market Cap", value=f"${price * shares:,.2f}", inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="adjust_shares")
    async def adjust_shares(self, ctx, ticker: str, new_available: int):
        """Adjust the number of publicly available shares
        
        Usage: !adjust_shares MYCO 500
        """
        ticker = ticker.upper()
        
        if new_available < 0:
            await ctx.send("❌ Available shares cannot be negative!")
            return
        
        async with self.bot.db.acquire() as conn:
            # Get stock info
            stock = await conn.fetchrow(
                """SELECT s.id, s.available_shares, s.total_shares, c.owner_id, c.name
                   FROM stocks s
                   JOIN companies c ON s.company_id = c.id
                   WHERE s.ticker = $1""",
                ticker
            )
            
            if not stock:
                await ctx.send(f"❌ Stock '{ticker}' not found!")
                return
            
            stock_id = stock['id']
            current_available = stock['available_shares']
            total_shares = stock['total_shares']
            owner_id = stock['owner_id']
            company_name = stock['name']
            
            # Check ownership
            if owner_id != ctx.author.id:
                await ctx.send("❌ You don't own this company!")
                return
            
            # Calculate shares owned by public
            shares_owned = total_shares - current_available
            
            if new_available > total_shares - shares_owned:
                max_available = total_shares - shares_owned
                await ctx.send(f"❌ Cannot set available shares higher than {max_available:,} (total shares minus publicly owned shares)!")
                return
            
            # Update available shares
            await conn.execute(
                "UPDATE stocks SET available_shares = $1 WHERE id = $2",
                new_available, stock_id
            )
        
        change = new_available - current_available
        
        embed = discord.Embed(
            title="📊 Shares Adjusted",
            description=f"Updated available shares for **{company_name}** ({ticker})",
            color=discord.Color.blue()
        )
        embed.add_field(name="Previous Available", value=f"{current_available:,}", inline=True)
        embed.add_field(name="New Available", value=f"{new_available:,}", inline=True)
        embed.add_field(name="Change", value=f"{change:+,}", inline=True)
        
        await ctx.send(embed=embed)
    
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
    async def balance(self, ctx):
        """Check your cash balance"""
        balance = await self.get_user_balance(ctx.author.id)
        
        embed = discord.Embed(
            title="💰 Your Balance",
            description=f"**${balance:,.2f}**",
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)
    
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
            
            print(f"✓ Daily fluctuation: Updated {len(changes)} stock(s)")
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
    await bot.add_cog(StockMarket(bot))

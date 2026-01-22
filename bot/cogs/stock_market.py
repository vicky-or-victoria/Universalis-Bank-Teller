import discord
from discord.ext import commands
from discord import app_commands
import random

class StockMarket(commands.Cog):
    """IPO, stock trading, and portfolio management"""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def get_user_balance(self, user_id: int) -> float:
        """Get user's balance, create account if doesn't exist"""
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            
            if not row:
                await cursor.execute(
                    "INSERT INTO users (user_id, balance) VALUES (?, ?)",
                    (user_id, 10000)
                )
                await self.bot.db.commit()
                return 10000.0
            
            return row[0]
    
    async def update_user_balance(self, user_id: int, amount: float):
        """Update user's balance"""
        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (amount, user_id)
            )
            await self.bot.db.commit()
    
    @commands.hybrid_command(name="balance")
    async def balance(self, ctx):
        """Check your current balance"""
        balance = await self.get_user_balance(ctx.author.id)
        
        embed = discord.Embed(
            title="💰 Your Balance",
            description=f"**${balance:,.2f}**",
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"User: {ctx.author.display_name}")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="register")
    async def register_company(self, ctx, *, company_name: str):
        """Register a new company"""
        async with self.bot.db.cursor() as cursor:
            # Check if company exists
            await cursor.execute("SELECT id FROM companies WHERE name = ?", (company_name,))
            if await cursor.fetchone():
                await ctx.send(f"❌ Company '{company_name}' already exists!")
                return
            
            # Create company
            await cursor.execute(
                "INSERT INTO companies (name, owner_id, balance) VALUES (?, ?, ?)",
                (company_name, ctx.author.id, 0)
            )
            await self.bot.db.commit()
        
        embed = discord.Embed(
            title="🏢 Company Registered",
            description=f"**{company_name}** has been registered!",
            color=discord.Color.green()
        )
        embed.add_field(name="Owner", value=ctx.author.mention)
        embed.add_field(name="Starting Balance", value="$0.00")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="ipo")
    async def ipo(self, ctx, ticker: str, price: float, shares: int):
        """Launch an IPO for your company
        
        Usage: ub!ipo ACME 100.00 1000
        """
        ticker = ticker.upper()
        
        async with self.bot.db.cursor() as cursor:
            # Check if user owns a company
            await cursor.execute(
                "SELECT id, name FROM companies WHERE owner_id = ?",
                (ctx.author.id,)
            )
            company = await cursor.fetchone()
            
            if not company:
                await ctx.send("❌ You don't own a company! Use `ub!register` first.")
                return
            
            company_id, company_name = company
            
            # Check if ticker already exists
            await cursor.execute("SELECT id FROM stocks WHERE ticker = ?", (ticker,))
            if await cursor.fetchone():
                await ctx.send(f"❌ Ticker '{ticker}' is already in use!")
                return
            
            # Create stock
            await cursor.execute(
                """INSERT INTO stocks (company_id, ticker, price, available_shares, total_shares)
                   VALUES (?, ?, ?, ?, ?)""",
                (company_id, ticker, price, shares, shares)
            )
            await self.bot.db.commit()
        
        embed = discord.Embed(
            title="🎉 IPO Launched!",
            description=f"**{company_name}** ({ticker}) is now public!",
            color=discord.Color.blue()
        )
        embed.add_field(name="Initial Price", value=f"${price:,.2f}", inline=True)
        embed.add_field(name="Available Shares", value=f"{shares:,}", inline=True)
        embed.add_field(name="Market Cap", value=f"${price * shares:,.2f}", inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="stocks")
    async def list_stocks(self, ctx):
        """View all available stocks"""
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("""
                SELECT s.ticker, c.name, s.price, s.available_shares, s.total_shares
                FROM stocks s
                JOIN companies c ON s.company_id = c.id
                ORDER BY s.ticker
            """)
            stocks = await cursor.fetchall()
        
        if not stocks:
            await ctx.send("📉 No stocks available yet!")
            return
        
        embed = discord.Embed(
            title="📈 Stock Market",
            description="Available stocks for trading",
            color=discord.Color.blue()
        )
        
        for ticker, company, price, available, total in stocks:
            ownership = ((total - available) / total * 100) if total > 0 else 0
            embed.add_field(
                name=f"{ticker} - {company}",
                value=(
                    f"💵 ${price:,.2f}/share\n"
                    f"📊 {available:,}/{total:,} available ({ownership:.1f}% owned)"
                ),
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="buy")
    async def buy_stock(self, ctx, ticker: str, amount: int):
        """Buy stocks
        
        Usage: ub!buy ACME 10
        """
        ticker = ticker.upper()
        
        if amount <= 0:
            await ctx.send("❌ Amount must be positive!")
            return
        
        async with self.bot.db.cursor() as cursor:
            # Get stock info
            await cursor.execute(
                """SELECT s.id, s.price, s.available_shares, c.name
                   FROM stocks s
                   JOIN companies c ON s.company_id = c.id
                   WHERE s.ticker = ?""",
                (ticker,)
            )
            stock = await cursor.fetchone()
            
            if not stock:
                await ctx.send(f"❌ Stock '{ticker}' not found!")
                return
            
            stock_id, price, available, company_name = stock
            
            if amount > available:
                await ctx.send(f"❌ Only {available:,} shares available!")
                return
            
            # Check user balance
            balance = await self.get_user_balance(ctx.author.id)
            total_cost = price * amount
            
            if balance < total_cost:
                await ctx.send(f"❌ Insufficient funds! Need ${total_cost:,.2f}, have ${balance:,.2f}")
                return
            
            # Execute purchase
            await cursor.execute(
                "UPDATE stocks SET available_shares = available_shares - ? WHERE id = ?",
                (amount, stock_id)
            )
            
            await self.update_user_balance(ctx.author.id, -total_cost)
            
            # Update or create holding
            await cursor.execute(
                "SELECT shares FROM holdings WHERE user_id = ? AND stock_id = ?",
                (ctx.author.id, stock_id)
            )
            holding = await cursor.fetchone()
            
            if holding:
                await cursor.execute(
                    "UPDATE holdings SET shares = shares + ? WHERE user_id = ? AND stock_id = ?",
                    (amount, ctx.author.id, stock_id)
                )
            else:
                await cursor.execute(
                    "INSERT INTO holdings (user_id, stock_id, shares) VALUES (?, ?, ?)",
                    (ctx.author.id, stock_id, amount)
                )
            
            await self.bot.db.commit()
        
        new_balance = balance - total_cost
        
        embed = discord.Embed(
            title="✅ Purchase Successful",
            color=discord.Color.green()
        )
        embed.add_field(name="Stock", value=f"{ticker} ({company_name})", inline=False)
        embed.add_field(name="Shares Purchased", value=f"{amount:,}", inline=True)
        embed.add_field(name="Price per Share", value=f"${price:,.2f}", inline=True)
        embed.add_field(name="Total Cost", value=f"${total_cost:,.2f}", inline=True)
        embed.add_field(name="New Balance", value=f"${new_balance:,.2f}", inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="sell")
    async def sell_stock(self, ctx, ticker: str, amount: int):
        """Sell stocks
        
        Usage: ub!sell ACME 5
        """
        ticker = ticker.upper()
        
        if amount <= 0:
            await ctx.send("❌ Amount must be positive!")
            return
        
        async with self.bot.db.cursor() as cursor:
            # Get stock and holding info
            await cursor.execute(
                """SELECT s.id, s.price, h.shares, c.name
                   FROM stocks s
                   JOIN companies c ON s.company_id = c.id
                   LEFT JOIN holdings h ON s.id = h.stock_id AND h.user_id = ?
                   WHERE s.ticker = ?""",
                (ctx.author.id, ticker)
            )
            result = await cursor.fetchone()
            
            if not result or not result[2]:
                await ctx.send(f"❌ You don't own any {ticker} shares!")
                return
            
            stock_id, price, owned_shares, company_name = result
            
            if amount > owned_shares:
                await ctx.send(f"❌ You only own {owned_shares:,} shares!")
                return
            
            total_value = price * amount
            
            # Update holding
            if amount == owned_shares:
                await cursor.execute(
                    "DELETE FROM holdings WHERE user_id = ? AND stock_id = ?",
                    (ctx.author.id, stock_id)
                )
            else:
                await cursor.execute(
                    "UPDATE holdings SET shares = shares - ? WHERE user_id = ? AND stock_id = ?",
                    (amount, ctx.author.id, stock_id)
                )
            
            # Return shares to market
            await cursor.execute(
                "UPDATE stocks SET available_shares = available_shares + ? WHERE id = ?",
                (amount, stock_id)
            )
            
            await self.update_user_balance(ctx.author.id, total_value)
            await self.bot.db.commit()
        
        balance = await self.get_user_balance(ctx.author.id)
        
        embed = discord.Embed(
            title="✅ Sale Successful",
            color=discord.Color.green()
        )
        embed.add_field(name="Stock", value=f"{ticker} ({company_name})", inline=False)
        embed.add_field(name="Shares Sold", value=f"{amount:,}", inline=True)
        embed.add_field(name="Price per Share", value=f"${price:,.2f}", inline=True)
        embed.add_field(name="Total Value", value=f"${total_value:,.2f}", inline=True)
        embed.add_field(name="New Balance", value=f"${balance:,.2f}", inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="portfolio")
    async def portfolio(self, ctx, user: discord.User = None):
        """View your stock portfolio"""
        user = user or ctx.author
        
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("""
                SELECT s.ticker, c.name, s.price, h.shares
                FROM holdings h
                JOIN stocks s ON h.stock_id = s.id
                JOIN companies c ON s.company_id = c.id
                WHERE h.user_id = ?
                ORDER BY (s.price * h.shares) DESC
            """, (user.id,))
            holdings = await cursor.fetchall()
        
        balance = await self.get_user_balance(user.id)
        
        embed = discord.Embed(
            title=f"📊 {user.display_name}'s Portfolio",
            color=discord.Color.blue()
        )
        
        if not holdings:
            embed.description = "No stock holdings"
        else:
            total_value = 0
            for ticker, company, price, shares in holdings:
                value = price * shares
                total_value += value
                embed.add_field(
                    name=f"{ticker} - {company}",
                    value=(
                        f"Shares: {shares:,}\n"
                        f"Price: ${price:,.2f}\n"
                        f"Value: ${value:,.2f}"
                    ),
                    inline=True
                )
            
            embed.add_field(
                name="💼 Total Portfolio Value",
                value=f"${total_value:,.2f}",
                inline=False
            )
        
        embed.add_field(name="💰 Cash Balance", value=f"${balance:,.2f}", inline=False)
        
        total_net_worth = balance + sum(row[2] * row[3] for row in holdings)
        embed.set_footer(text=f"Net Worth: ${total_net_worth:,.2f}")
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(StockMarket(bot))

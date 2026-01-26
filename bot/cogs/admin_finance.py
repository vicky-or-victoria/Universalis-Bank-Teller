import discord
from discord.ext import commands

class AdminFinance(commands.Cog):
    """Admin commands for financial management"""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def get_user_balance(self, user_id: int) -> float:
        """Get user balance"""
        async with self.bot.db.acquire() as conn:
            row = await conn.fetchrow("SELECT balance FROM users WHERE user_id = $1", user_id)
            if not row:
                await conn.execute("INSERT INTO users (user_id, balance) VALUES ($1, $2)", user_id, 50000)
                return 50000.0
            return float(row['balance'])
    
    async def update_user_balance(self, user_id: int, amount: float):
        """Update user balance"""
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                "UPDATE users SET balance = balance + $1 WHERE user_id = $2",
                amount, user_id
            )
    
    @commands.hybrid_command(name="give_money")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def give_money(self, ctx, user: discord.User, amount: float):
        """Give money to a user (Admin/Owner only)
        
        Usage: !give_money @user 10000
        """
        if amount <= 0:
            await ctx.send("❌ Amount must be positive!")
            return
        
        await self.update_user_balance(user.id, amount)
        new_balance = await self.get_user_balance(user.id)
        
        embed = discord.Embed(
            title="✅ Money Given",
            color=discord.Color.green()
        )
        embed.add_field(name="User", value=user.mention, inline=True)
        embed.add_field(name="Amount", value=f"${amount:,.2f}", inline=True)
        embed.add_field(name="New Balance", value=f"${new_balance:,.2f}", inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="remove_money")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def remove_money(self, ctx, user: discord.User, amount: float):
        """Remove money from a user (Admin/Owner only)
        
        Usage: !remove_money @user 5000
        """
        if amount <= 0:
            await ctx.send("❌ Amount must be positive!")
            return
        
        current_balance = await self.get_user_balance(user.id)
        
        if current_balance < amount:
            await ctx.send(f"⚠️ User only has ${current_balance:,.2f}. Proceeding anyway...")
        
        await self.update_user_balance(user.id, -amount)
        new_balance = await self.get_user_balance(user.id)
        
        embed = discord.Embed(
            title="✅ Money Removed",
            color=discord.Color.orange()
        )
        embed.add_field(name="User", value=user.mention, inline=True)
        embed.add_field(name="Amount", value=f"${amount:,.2f}", inline=True)
        embed.add_field(name="New Balance", value=f"${new_balance:,.2f}", inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="set_stock_price")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def set_stock_price(self, ctx, ticker: str, new_price: float):
        """Manually set a stock's price (Admin/Owner only)
        
        Usage: !set_stock_price MYCO 150.00
        """
        ticker = ticker.upper()
        
        if new_price <= 0:
            await ctx.send("❌ Price must be positive!")
            return
        
        async with self.bot.db.acquire() as conn:
            stock = await conn.fetchrow(
                "SELECT s.id, s.price, c.name FROM stocks s JOIN companies c ON s.company_id = c.id WHERE s.ticker = $1",
                ticker
            )
            
            if not stock:
                await ctx.send(f"❌ Stock '{ticker}' not found!")
                return
            
            old_price = float(stock['price'])
            company_name = stock['name']
            
            await conn.execute(
                "UPDATE stocks SET price = $1 WHERE id = $2",
                new_price, stock['id']
            )
        
        change_pct = ((new_price - old_price) / old_price) * 100
        
        embed = discord.Embed(
            title="📊 Stock Price Updated",
            description=f"**{ticker}** - {company_name}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Old Price", value=f"${old_price:,.2f}", inline=True)
        embed.add_field(name="New Price", value=f"${new_price:,.2f}", inline=True)
        embed.add_field(name="Change", value=f"{change_pct:+.2f}%", inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="delist_company")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def delist_company(self, ctx, ticker: str):
        """Remove a company from the stock market (Admin/Owner only)
        
        Usage: !delist_company MYCO
        """
        ticker = ticker.upper()
        
        async with self.bot.db.acquire() as conn:
            stock = await conn.fetchrow(
                """SELECT s.id, s.company_id, c.name, s.available_shares, s.total_shares
                   FROM stocks s
                   JOIN companies c ON s.company_id = c.id
                   WHERE s.ticker = $1""",
                ticker
            )
            
            if not stock:
                await ctx.send(f"❌ Stock '{ticker}' not found!")
                return
            
            stock_id = stock['id']
            company_id = stock['company_id']
            company_name = stock['name']
            available = stock['available_shares']
            total = stock['total_shares']
            
            # Check if there are any holdings
            holdings_count = await conn.fetchval(
                "SELECT COUNT(*) FROM holdings WHERE stock_id = $1",
                stock_id
            )
            
            if holdings_count > 0:
                await ctx.send(f"⚠️ Warning: {holdings_count} user(s) still hold shares of {ticker}. Delisting anyway...")
            
            # Delete holdings first (foreign key constraint)
            await conn.execute("DELETE FROM holdings WHERE stock_id = $1", stock_id)
            
            # Delete short positions
            await conn.execute("DELETE FROM short_positions WHERE stock_id = $1", stock_id)
            
            # Delete stock
            await conn.execute("DELETE FROM stocks WHERE id = $1", stock_id)
            
            # Mark company as not public
            await conn.execute("UPDATE companies SET is_public = $1 WHERE id = $2", False, company_id)
        
        embed = discord.Embed(
            title="🔴 Company Delisted",
            description=f"**{ticker}** - {company_name} has been removed from the stock market",
            color=discord.Color.red()
        )
        embed.add_field(name="Shares", value=f"{available:,}/{total:,} available", inline=True)
        embed.add_field(name="Holdings Cleared", value=str(holdings_count), inline=True)
        
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AdminFinance(bot))

import discord
from discord.ext import commands
import asyncio
from datetime import datetime, timedelta

class CompanyManagement(commands.Cog):
    """Company registration, viewing, and management"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.hybrid_command(name="register_company")
    async def register_company(self, ctx, company_name: str):
        """Register a new company"""
        stock_market_cog = self.bot.get_cog("StockMarket")
        max_companies = stock_market_cog.max_companies if stock_market_cog else 3
        
        async with self.bot.db.acquire() as conn:
            company_count = await conn.fetchval(
                "SELECT COUNT(*) FROM companies WHERE owner_id = $1",
                ctx.author.id
            )
            
            if company_count >= max_companies:
                await ctx.send(f"❌ You've reached the maximum of **{max_companies}** companies! Disband one to create another.")
                return
            
            existing = await conn.fetchrow(
                "SELECT id FROM companies WHERE name = $1",
                company_name
            )
            
            if existing:
                await ctx.send(f"❌ A company named **{company_name}** already exists!")
                return
            
            await conn.execute(
                "INSERT INTO companies (name, owner_id) VALUES ($1, $2)",
                company_name, ctx.author.id
            )
        
        embed = discord.Embed(
            title="🏢 Company Registered!",
            description=f"**{company_name}** has been successfully registered!",
            color=discord.Color.green()
        )
        embed.add_field(name="Owner", value=ctx.author.mention, inline=True)
        embed.add_field(name="Starting Balance", value="$0.00", inline=True)
        embed.add_field(name="CEO Salary", value="5.00%", inline=True)
        embed.add_field(name="Companies Owned", value=f"{company_count + 1}/{max_companies}", inline=True)
        embed.set_footer(text="Use /file-report to start earning money!")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="company_balance")
    async def company_balance(self, ctx, company_name: str = None):
        """Check your company's balance"""
        async with self.bot.db.acquire() as conn:
            if company_name:
                companies = await conn.fetch(
                    "SELECT name, balance, ceo_salary_percent FROM companies WHERE owner_id = $1 AND name = $2",
                    ctx.author.id, company_name
                )
            else:
                companies = await conn.fetch(
                    "SELECT name, balance, ceo_salary_percent FROM companies WHERE owner_id = $1",
                    ctx.author.id
                )
        
        if not companies:
            await ctx.send("❌ You don't own any companies!")
            return
        
        embed = discord.Embed(
            title="🏢 Your Companies",
            color=discord.Color.gold()
        )
        
        for row in companies:
            name = row['name']
            balance = float(row['balance'])
            ceo_salary = float(row['ceo_salary_percent'])
            embed.add_field(
                name=name,
                value=f"Balance: **${balance:,.2f}**\nCEO Salary: {ceo_salary:.1f}%",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="set_ceo_salary")
    async def set_ceo_salary(self, ctx, company_name: str, percentage: float):
        """Set your CEO salary percentage for a company
        
        Usage: /set-ceo-salary "My Company" 7.5
        """
        if percentage < 0 or percentage > 100:
            await ctx.send("❌ Percentage must be between 0 and 100!")
            return
        
        async with self.bot.db.acquire() as conn:
            company = await conn.fetchrow(
                "SELECT id, ceo_salary_percent FROM companies WHERE owner_id = $1 AND name = $2",
                ctx.author.id, company_name
            )
            
            if not company:
                await ctx.send(f"❌ You don't own a company named **{company_name}**!")
                return
            
            old_percent = float(company['ceo_salary_percent'])
            
            await conn.execute(
                "UPDATE companies SET ceo_salary_percent = $1 WHERE id = $2",
                percentage, company['id']
            )
        
        embed = discord.Embed(
            title="💼 CEO Salary Updated",
            description=f"**{company_name}**",
            color=discord.Color.blue()
        )
        embed.add_field(name="Previous", value=f"{old_percent:.1f}%", inline=True)
        embed.add_field(name="New", value=f"{percentage:.1f}%", inline=True)
        embed.set_footer(text="This will apply to all future financial reports")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="my-companies")  # Changed from my_companies
    async def my_companies(self, ctx, user: discord.User = None):
        """View detailed information about your companies (or another user's)"""
        target_user = user or ctx.author
        
        async with self.bot.db.acquire() as conn:
            companies = await conn.fetch(
                "SELECT name, balance, is_public, ceo_salary_percent, created_at FROM companies WHERE owner_id = $1 ORDER BY created_at DESC",
                target_user.id
            )
        
        if not companies:
            if target_user == ctx.author:
                await ctx.send("❌ You don't own any companies! Use `/register-company` to create one.")
            else:
                await ctx.send(f"❌ {target_user.mention} doesn't own any companies.")
            return
        
        stock_market_cog = self.bot.get_cog("StockMarket")
        max_companies = stock_market_cog.max_companies if stock_market_cog else 3
        
        if target_user == ctx.author:
            title = f"🏢 Your Companies ({len(companies)}/{max_companies})"
        else:
            title = f"🏢 {target_user.display_name}'s Companies ({len(companies)}/{max_companies})"
        
        embed = discord.Embed(
            title=title,
            color=discord.Color.blue()
        )
        
        total_balance = 0
        
        for company in companies:
            name = company['name']
            balance = float(company['balance'])
            is_public = company['is_public']
            ceo_salary = float(company['ceo_salary_percent'])
            created_at = company['created_at']
            
            total_balance += balance
            
            status = "📈 Public" if is_public else "🔒 Private"
            
            stock_info = ""
            if is_public:
                async with self.bot.db.acquire() as conn:
                    stock = await conn.fetchrow(
                        "SELECT ticker, price FROM stocks s JOIN companies c ON s.company_id = c.id WHERE c.name = $1",
                        name
                    )
                    if stock:
                        ticker = stock['ticker']
                        price = float(stock['price'])
                        stock_info = f"\nTicker: **{ticker}** | Stock Price: **${price:,.2f}**"
            
            embed.add_field(
                name=f"{status} {name}",
                value=f"Balance: **${balance:,.2f}** | CEO Salary: {ceo_salary:.1f}%{stock_info}\nFounded: {created_at.strftime('%Y-%m-%d')}",
                inline=False
            )
        
        embed.set_footer(text=f"Total Company Balance: ${total_balance:,.2f}")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="disband_company")
    async def disband_company(self, ctx, company_name: str):
        """Disband your company (WARNING: This is permanent!)"""
        async with self.bot.db.acquire() as conn:
            company = await conn.fetchrow(
                "SELECT id, balance, is_public FROM companies WHERE owner_id = $1 AND name = $2",
                ctx.author.id, company_name
            )
            
            if not company:
                await ctx.send("❌ You don't own a company with that name!")
                return
            
            company_id = company['id']
            balance = float(company['balance'])
            is_public = company['is_public']
            
            if is_public:
                await ctx.send("❌ You cannot disband a public company! Use `/delist-company` first (Admin only).")
                return
            
            confirm_embed = discord.Embed(
                title="⚠️ Confirm Company Disbandment",
                description=f"Are you sure you want to disband **{company_name}**?",
                color=discord.Color.orange()
            )
            confirm_embed.add_field(name="Company Balance", value=f"${balance:,.2f} (will be lost)", inline=False)
            confirm_embed.add_field(name="Reports", value="All financial reports will be deleted", inline=False)
            confirm_embed.set_footer(text="React with ✅ to confirm or ❌ to cancel (60 seconds)")
            
            msg = await ctx.send(embed=confirm_embed)
            await msg.add_reaction("✅")
            await msg.add_reaction("❌")
            
            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == msg.id
            
            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=60.0, check=check)
                
                if str(reaction.emoji) == "❌":
                    await ctx.send("❌ Company disbandment cancelled.")
                    return
                
                await conn.execute("DELETE FROM reports WHERE company_id = $1", company_id)
                await conn.execute("DELETE FROM companies WHERE id = $1", company_id)
                
                success_embed = discord.Embed(
                    title="🗑️ Company Disbanded",
                    description=f"**{company_name}** has been permanently disbanded.",
                    color=discord.Color.red()
                )
                success_embed.add_field(name="Balance Lost", value=f"${balance:,.2f}", inline=True)
                
                await ctx.send(embed=success_embed)
                
            except asyncio.TimeoutError:
                await ctx.send("⏱️ Confirmation timed out. Company disbandment cancelled.")
    
    @commands.hybrid_command(name="force_disband")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def force_disband(self, ctx, user: discord.User, company_name: str):
        """Forcefully disband a player's company (Admin/Owner only)"""
        async with self.bot.db.acquire() as conn:
            company = await conn.fetchrow(
                "SELECT id, balance, is_public FROM companies WHERE owner_id = $1 AND name = $2",
                user.id, company_name
            )
            
            if not company:
                await ctx.send(f"❌ {user.mention} doesn't own a company named **{company_name}**!")
                return
            
            company_id = company['id']
            balance = float(company['balance'])
            is_public = company['is_public']
            
            if is_public:
                stock = await conn.fetchrow(
                    "SELECT id, ticker FROM stocks WHERE company_id = $1",
                    company_id
                )
                
                if stock:
                    stock_id = stock['id']
                    ticker = stock['ticker']
                    await conn.execute("DELETE FROM holdings WHERE stock_id = $1", stock_id)
                    await conn.execute("DELETE FROM short_positions WHERE stock_id = $1", stock_id)
                    await conn.execute("DELETE FROM stocks WHERE id = $1", stock_id)
                    await ctx.send(f"📉 Delisted **{ticker}** before disbanding...")
            
            await conn.execute("DELETE FROM reports WHERE company_id = $1", company_id)
            await conn.execute("DELETE FROM companies WHERE id = $1", company_id)
        
        embed = discord.Embed(
            title="🔨 Company Forcefully Disbanded",
            description=f"**{company_name}** (owned by {user.mention}) has been disbanded by an administrator.",
            color=discord.Color.red()
        )
        embed.add_field(name="Balance Lost", value=f"${balance:,.2f}", inline=True)
        embed.add_field(name="Was Public", value="Yes" if is_public else "No", inline=True)
        
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(CompanyManagement(bot))

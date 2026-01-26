import discord
from discord.ext import commands

class CompanyPublic(commands.Cog):
    """IPO system and public company share management"""
    
    def __init__(self, bot):
        self.bot = bot
        # Active IPO sessions (user_id -> session_data)
        self.ipo_sessions = {}
        # Maximum companies a player can own (configurable)
        self.max_companies = 3
    
    @staticmethod
    def calculate_ipo_price(company_balance: float, total_reports: int, avg_net_profit: float) -> float:
        """Calculate realistic IPO price based on company history
        
        Algorithm factors:
        - Company balance (assets)
        - Number of reports filed (company age/track record)
        - Average net profit (profitability)
        """
        # Base valuation from company balance
        base_value = company_balance
        
        # Adjust for track record
        # More reports = more established = higher multiplier
        track_record_multiplier = 1 + (min(total_reports, 20) * 0.1)  # Up to 3x for 20+ reports
        
        # Adjust for profitability
        if avg_net_profit > 0:
            # Profitable companies get earnings multiplier
            # Use P/E ratio concept: higher profits = higher valuation
            earnings_multiplier = 1 + min(avg_net_profit / 5000, 2.0)  # Cap at 3x
        else:
            # Unprofitable companies get penalized
            earnings_multiplier = 0.5
        
        # Calculate total valuation
        total_valuation = base_value * track_record_multiplier * earnings_multiplier
        
        # Ensure minimum valuation
        total_valuation = max(total_valuation, 1000)
        
        return total_valuation
    
    @commands.hybrid_command(name="go_public")
    async def go_public(self, ctx):
        """Start the IPO process for your company (interactive)"""
        if ctx.author.id in self.ipo_sessions:
            await ctx.send("⚠️ You already have an active IPO session! Use `/cancel-ipo` to cancel it.")
            return
        
        self.ipo_sessions[ctx.author.id] = {
            "step": "company_name",
            "company_name": None,
            "ticker": None,
            "total_shares": None,
            "owner_percentage": None,
            "channel_id": ctx.channel.id
        }
        
        await ctx.send(
            "**🎉 Let's take your company public!**\n\n"
            "This is a big step! I'll guide you through the IPO process.\n\n"
            "**First, which company would you like to take public?**\n"
            "_(Please provide the exact company name)_"
        )
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle IPO filing conversation"""
        if message.author.bot:
            return
        
        user_id = message.author.id
        
        if user_id not in self.ipo_sessions:
            return
        
        session = self.ipo_sessions[user_id]
        
        if message.channel.id != session["channel_id"]:
            return
        
        if message.content.startswith("ub!") or message.content.startswith("/"):
            return
        
        # Step 1: Get company name
        if session["step"] == "company_name":
            company_name = message.content.strip()
            
            async with self.bot.db.acquire() as conn:
                company = await conn.fetchrow(
                    "SELECT id, balance, is_public FROM companies WHERE owner_id = $1 AND name = $2",
                    user_id, company_name
                )
                
                if not company:
                    await message.reply(f"❌ You don't own a company named **{company_name}**!")
                    del self.ipo_sessions[user_id]
                    return
                
                if company['is_public']:
                    await message.reply(f"❌ **{company_name}** is already public!")
                    del self.ipo_sessions[user_id]
                    return
                
                company_id = company['id']
                company_balance = float(company['balance'])
                
                # Get company performance data
                reports = await conn.fetch(
                    "SELECT net_profit FROM reports WHERE company_id = $1 ORDER BY reported_at DESC",
                    company_id
                )
                
                total_reports = len(reports)
                avg_net_profit = sum(float(r['net_profit']) for r in reports) / max(total_reports, 1)
                
                # Calculate suggested IPO valuation
                suggested_valuation = self.calculate_ipo_price(company_balance, total_reports, avg_net_profit)
            
            session["company_name"] = company_name
            session["company_id"] = company_id
            session["company_balance"] = company_balance
            session["suggested_valuation"] = suggested_valuation
            session["step"] = "ticker"
            
            await message.reply(
                f"**Great choice!** Here's what I found about **{company_name}**:\n\n"
                f"📊 **Company Balance:** ${company_balance:,.2f}\n"
                f"📈 **Reports Filed:** {total_reports}\n"
                f"💰 **Avg Net Profit:** ${avg_net_profit:,.2f}\n\n"
                f"**Suggested IPO Valuation:** ${suggested_valuation:,.2f}\n"
                f"_(Based on company performance and industry standards)_\n\n"
                f"**Next, what ticker symbol would you like?**\n"
                f"_(3-5 characters, e.g., TECH, MYCORP, etc.)_"
            )
        
        # Step 2: Get ticker
        elif session["step"] == "ticker":
            ticker = message.content.strip().upper()
            
            if len(ticker) < 3 or len(ticker) > 5:
                await message.reply("⚠️ Ticker must be 3-5 characters!")
                return
            
            if not ticker.isalpha():
                await message.reply("⚠️ Ticker must contain only letters!")
                return
            
            async with self.bot.db.acquire() as conn:
                existing = await conn.fetchrow("SELECT id FROM stocks WHERE ticker = $1", ticker)
                if existing:
                    await message.reply(f"❌ Ticker **{ticker}** is already in use! Please choose another.")
                    return
            
            session["ticker"] = ticker
            session["step"] = "total_shares"
            
            await message.reply(
                f"**Perfect! Your ticker will be {ticker}** 🎫\n\n"
                f"**How many total shares would you like to issue?**\n"
                f"_(Recommended: 1,000 to 100,000 shares)_\n"
                f"_More shares = lower price per share_"
            )
        
        # Step 3: Get total shares
        elif session["step"] == "total_shares":
            try:
                total_shares = int(message.content.strip().replace(",", ""))
            except ValueError:
                await message.reply("⚠️ Please enter a valid number!")
                return
            
            if total_shares < 100:
                await message.reply("⚠️ You must issue at least 100 shares!")
                return
            
            if total_shares > 10000000:
                await message.reply("⚠️ That's too many shares! Maximum is 10 million.")
                return
            
            # Calculate price per share
            suggested_valuation = session["suggested_valuation"]
            price_per_share = round(suggested_valuation / total_shares, 2)
            
            session["total_shares"] = total_shares
            session["price_per_share"] = price_per_share
            session["step"] = "owner_percentage"
            
            await message.reply(
                f"**Excellent!** Based on your company's valuation:\n\n"
                f"📊 **Total Shares:** {total_shares:,}\n"
                f"💵 **Price Per Share:** ${price_per_share:,.2f}\n"
                f"💰 **Total Market Cap:** ${suggested_valuation:,.2f}\n\n"
                f"**Finally, what percentage of the company do you want to keep?**\n"
                f"_(Enter a number between 1-99, e.g., 51 to keep 51% ownership)_\n"
                f"_Recommended: Keep at least 51% for majority control_"
            )
        
        # Step 4: Get owner percentage and complete IPO
        elif session["step"] == "owner_percentage":
            try:
                owner_percentage = float(message.content.strip())
            except ValueError:
                await message.reply("⚠️ Please enter a valid percentage!")
                return
            
            if owner_percentage <= 0 or owner_percentage >= 100:
                await message.reply("⚠️ Percentage must be between 1 and 99!")
                return
            
            # Calculate shares
            total_shares = session["total_shares"]
            owner_shares = int(total_shares * (owner_percentage / 100))
            public_shares = total_shares - owner_shares
            
            if public_shares <= 0:
                await message.reply("⚠️ You must offer at least some shares to the public!")
                return
            
            # Execute IPO
            company_id = session["company_id"]
            company_name = session["company_name"]
            ticker = session["ticker"]
            price = session["price_per_share"]
            
            async with self.bot.db.acquire() as conn:
                # Create stock
                stock_id = await conn.fetchval(
                    "INSERT INTO stocks (company_id, ticker, price, available_shares, total_shares) VALUES ($1, $2, $3, $4, $5) RETURNING id",
                    company_id, ticker, price, public_shares, total_shares
                )
                
                # Mark company as public
                await conn.execute(
                    "UPDATE companies SET is_public = $1 WHERE id = $2",
                    True, company_id
                )
                
                # Give owner their shares
                if owner_shares > 0:
                    await conn.execute(
                        "INSERT INTO holdings (user_id, stock_id, shares) VALUES ($1, $2, $3)",
                        user_id, stock_id, owner_shares
                    )
            
            # Success embed
            embed = discord.Embed(
                title="🎉 IPO Successfully Completed!",
                description=f"**{company_name}** is now publicly traded!",
                color=discord.Color.green()
            )
            embed.add_field(name="Ticker", value=ticker, inline=True)
            embed.add_field(name="Share Price", value=f"${price:,.2f}", inline=True)
            embed.add_field(name="Total Shares", value=f"{total_shares:,}", inline=True)
            embed.add_field(name="Your Ownership", value=f"{owner_shares:,} shares ({owner_percentage:.1f}%)", inline=True)
            embed.add_field(name="Public Shares", value=f"{public_shares:,} shares ({100-owner_percentage:.1f}%)", inline=True)
            embed.add_field(name="Market Cap", value=f"${price * total_shares:,.2f}", inline=False)
            embed.set_footer(text="🎊 Congratulations on going public!")
            
            await message.reply(embed=embed)
            del self.ipo_sessions[user_id]
    
    @commands.hybrid_command(name="cancel_ipo")
    async def cancel_ipo(self, ctx):
        """Cancel your active IPO session"""
        if ctx.author.id in self.ipo_sessions:
            del self.ipo_sessions[ctx.author.id]
            await ctx.send("✅ IPO session cancelled.")
        else:
            await ctx.send("ℹ️ You don't have an active IPO session.")
    
    @commands.hybrid_command(name="adjust_shares")
    async def adjust_shares(self, ctx, ticker: str, action: str, amount: int):
        """Adjust shares for your public company
        
        Usage: 
        - /adjust-shares MYCO issue 500 - Issue 500 new shares (dilutes ownership, lowers price)
        - /adjust-shares MYCO buyback 200 - Buy back 200 shares (increases ownership, raises price)
        - /adjust-shares MYCO release 300 - Release 300 of your shares to public (no dilution)
        - /adjust-shares MYCO withdraw 100 - Take back 100 shares from market (if available)
        
        Actions:
        - issue: Create new shares (dilutes all shareholders, lowers stock price)
        - buyback: Company buys back shares from market (raises stock price)
        - release: Owner releases personal shares to market (no price change)
        - withdraw: Owner takes shares back from market (if available)
        """
        ticker = ticker.upper()
        action = action.lower()
        
        if action not in ["issue", "buyback", "release", "withdraw"]:
            await ctx.send("❌ Invalid action! Use: `issue`, `buyback`, `release`, or `withdraw`")
            return
        
        if amount <= 0:
            await ctx.send("❌ Amount must be positive!")
            return
        
        async with self.bot.db.acquire() as conn:
            # Get stock and company info
            stock = await conn.fetchrow(
                """SELECT s.id, s.ticker, s.price, s.available_shares, s.total_shares, s.company_id,
                          c.owner_id, c.name, c.balance
                   FROM stocks s
                   JOIN companies c ON s.company_id = c.id
                   WHERE s.ticker = $1""",
                ticker
            )
            
            if not stock:
                await ctx.send(f"❌ Stock '{ticker}' not found!")
                return
            
            # Check ownership
            if stock['owner_id'] != ctx.author.id:
                await ctx.send("❌ You don't own this company!")
                return
            
            stock_id = stock['id']
            company_id = stock['company_id']
            company_name = stock['name']
            current_price = float(stock['price'])
            current_available = stock['available_shares']
            current_total = stock['total_shares']
            company_balance = float(stock['balance'])
            
            # Get owner's shares
            owner_holding = await conn.fetchrow(
                "SELECT shares FROM holdings WHERE user_id = $1 AND stock_id = $2",
                ctx.author.id, stock_id
            )
            owner_shares = owner_holding['shares'] if owner_holding else 0
            
            # Process based on action
            if action == "issue":
                # Issue new shares (dilution)
                new_total = current_total + amount
                new_available = current_available + amount
                
                # Price decreases due to dilution
                dilution_factor = current_total / new_total
                new_price = round(current_price * dilution_factor, 2)
                
                await conn.execute(
                    "UPDATE stocks SET total_shares = $1, available_shares = $2, price = $3 WHERE id = $4",
                    new_total, new_available, new_price, stock_id
                )
                
                embed = discord.Embed(
                    title="📈 New Shares Issued",
                    description=f"**{company_name}** ({ticker})",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Shares Issued", value=f"+{amount:,}", inline=True)
                embed.add_field(name="New Total", value=f"{new_total:,}", inline=True)
                embed.add_field(name="Available", value=f"{new_available:,}", inline=True)
                embed.add_field(name="Price Change", value=f"${current_price:.2f} → ${new_price:.2f}", inline=True)
                embed.add_field(name="Dilution", value=f"{(1 - dilution_factor) * 100:.2f}%", inline=True)
                embed.set_footer(text="⚠️ All shareholders were diluted proportionally")
                
            elif action == "buyback":
                # Buy back shares from market
                if amount > current_available:
                    await ctx.send(f"❌ Only {current_available:,} shares available in market!")
                    return
                
                buyback_cost = current_price * amount
                
                if company_balance < buyback_cost:
                    await ctx.send(f"❌ Company needs ${buyback_cost:,.2f} but only has ${company_balance:,.2f}!")
                    return
                
                new_total = current_total - amount
                new_available = current_available - amount
                
                # Price increases due to reduced supply
                scarcity_factor = current_total / max(new_total, 1)
                new_price = round(current_price * scarcity_factor, 2)
                
                # Deduct from company balance
                new_company_balance = company_balance - buyback_cost
                
                await conn.execute(
                    "UPDATE stocks SET total_shares = $1, available_shares = $2, price = $3 WHERE id = $4",
                    new_total, new_available, new_price, stock_id
                )
                
                await conn.execute(
                    "UPDATE companies SET balance = $1 WHERE id = $2",
                    new_company_balance, company_id
                )
                
                embed = discord.Embed(
                    title="💰 Share Buyback Completed",
                    description=f"**{company_name}** ({ticker})",
                    color=discord.Color.green()
                )
                embed.add_field(name="Shares Bought", value=f"{amount:,}", inline=True)
                embed.add_field(name="Cost", value=f"${buyback_cost:,.2f}", inline=True)
                embed.add_field(name="New Total", value=f"{new_total:,}", inline=True)
                embed.add_field(name="Price Change", value=f"${current_price:.2f} → ${new_price:.2f}", inline=True)
                embed.add_field(name="Company Balance", value=f"${new_company_balance:,.2f}", inline=True)
                embed.set_footer(text="✨ Reduced supply increased stock price")
                
            elif action == "release":
                # Release owner's shares to market
                if amount > owner_shares:
                    await ctx.send(f"❌ You only own {owner_shares:,} shares!")
                    return
                
                new_available = current_available + amount
                new_owner_shares = owner_shares - amount
                
                if new_owner_shares == 0:
                    await conn.execute(
                        "DELETE FROM holdings WHERE user_id = $1 AND stock_id = $2",
                        ctx.author.id, stock_id
                    )
                else:
                    await conn.execute(
                        "UPDATE holdings SET shares = $1 WHERE user_id = $2 AND stock_id = $3",
                        new_owner_shares, ctx.author.id, stock_id
                    )
                
                await conn.execute(
                    "UPDATE stocks SET available_shares = $1 WHERE id = $2",
                    new_available, stock_id
                )
                
                embed = discord.Embed(
                    title="📤 Shares Released to Market",
                    description=f"**{company_name}** ({ticker})",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Shares Released", value=f"{amount:,}", inline=True)
                embed.add_field(name="Your Remaining", value=f"{new_owner_shares:,}", inline=True)
                embed.add_field(name="Now Available", value=f"{new_available:,}", inline=True)
                embed.add_field(name="Stock Price", value=f"${current_price:.2f} (unchanged)", inline=True)
                embed.set_footer(text="✅ No dilution - total shares unchanged")
                
            elif action == "withdraw":
                # Withdraw shares from market back to owner
                if amount > current_available:
                    await ctx.send(f"❌ Only {current_available:,} shares available in market!")
                    return
                
                new_available = current_available - amount
                new_owner_shares = owner_shares + amount
                
                if owner_shares == 0:
                    await conn.execute(
                        "INSERT INTO holdings (user_id, stock_id, shares) VALUES ($1, $2, $3)",
                        ctx.author.id, stock_id, new_owner_shares
                    )
                else:
                    await conn.execute(
                        "UPDATE holdings SET shares = $1 WHERE user_id = $2 AND stock_id = $3",
                        new_owner_shares, ctx.author.id, stock_id
                    )
                
                await conn.execute(
                    "UPDATE stocks SET available_shares = $1 WHERE id = $2",
                    new_available, stock_id
                )
                
                embed = discord.Embed(
                    title="📥 Shares Withdrawn from Market",
                    description=f"**{company_name}** ({ticker})",
                    color=discord.Color.purple()
                )
                embed.add_field(name="Shares Withdrawn", value=f"{amount:,}", inline=True)
                embed.add_field(name="Your New Total", value=f"{new_owner_shares:,}", inline=True)
                embed.add_field(name="Now Available", value=f"{new_available:,}", inline=True)
                embed.add_field(name="Stock Price", value=f"${current_price:.2f} (unchanged)", inline=True)
                embed.set_footer(text="✅ No dilution - total shares unchanged")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="set_max_companies")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def set_max_companies(self, ctx, max_amount: int):
        """Set the maximum number of companies a player can own (Admin/Owner only)
        
        Usage: !set_max_companies 5
        """
        if max_amount < 1:
            await ctx.send("❌ Maximum must be at least 1!")
            return
        
        old_max = self.max_companies
        self.max_companies = max_amount
        
        embed = discord.Embed(
            title="🏢 Max Companies Updated",
            description=f"Players can now own up to **{max_amount}** companies",
            color=discord.Color.blue()
        )
        embed.add_field(name="Previous Limit", value=str(old_max), inline=True)
        embed.add_field(name="New Limit", value=str(max_amount), inline=True)
        
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(CompanyPublic(bot))

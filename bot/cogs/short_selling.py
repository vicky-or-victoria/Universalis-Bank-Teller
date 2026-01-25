import discord
from discord.ext import commands
from datetime import datetime, timedelta

class ShortSelling(commands.Cog):
    """Short selling system for stocks"""
    
    def __init__(self, bot):
        self.bot = bot
        # Short selling settings
        self.short_fee_percent = 0.03  # 3% fee to open short position
        self.trade_cooldown_seconds = 300  # 5 minutes between trades of same stock
    
    async def check_trade_cooldown(self, user_id: int, ticker: str) -> tuple[bool, int]:
        """Check if user is in cooldown for this ticker
        
        Returns:
            (can_trade: bool, seconds_remaining: int)
        """
        async with self.bot.db.acquire() as conn:
            cooldown = await conn.fetchrow(
                "SELECT last_trade FROM trade_cooldowns WHERE user_id = $1 AND ticker = $2",
                user_id, ticker
            )
            
            if not cooldown:
                return (True, 0)
            
            last_trade = cooldown['last_trade']
            time_since = datetime.now() - last_trade
            
            if time_since.total_seconds() >= self.trade_cooldown_seconds:
                return (True, 0)
            
            remaining = self.trade_cooldown_seconds - time_since.total_seconds()
            return (False, int(remaining))
    
    async def update_trade_cooldown(self, user_id: int, ticker: str):
        """Update the last trade time for this user and ticker"""
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """INSERT INTO trade_cooldowns (user_id, ticker, last_trade)
                   VALUES ($1, $2, $3)
                   ON CONFLICT (user_id, ticker)
                   DO UPDATE SET last_trade = $3""",
                user_id, ticker, datetime.now()
            )
    
    @commands.hybrid_command(name="short")
    async def short_stock(self, ctx, ticker: str, amount: int):
        """Short sell a stock (bet on price going down)
        
        Usage: /short MYCO 10
        
        How shorting works:
        - You borrow shares and sell them at current price
        - Later, you buy them back (cover) at hopefully a lower price
        - Profit = (entry_price - cover_price) * shares
        - 3% fee to open position
        - If price goes up, you lose money when you cover
        """
        ticker = ticker.upper()
        
        if amount <= 0:
            await ctx.send("❌ Amount must be positive!")
            return
        
        # Check trade cooldown
        can_trade, remaining = await self.check_trade_cooldown(ctx.author.id, ticker)
        if not can_trade:
            await ctx.send(f"⏰ Please wait {remaining}s before trading {ticker} again!")
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
                await ctx.send(f"❌ Only {available:,} shares available to short!")
                return
            
            # Check if user already has short position
            existing_short = await conn.fetchrow(
                "SELECT shares FROM short_positions WHERE user_id = $1 AND stock_id = $2",
                ctx.author.id, stock_id
            )
            
            if existing_short:
                await ctx.send(f"❌ You already have a short position on {ticker}! Cover it first with `/cover {ticker} {existing_short['shares']}`")
                return
            
            # Calculate costs
            stock_market_cog = self.bot.get_cog("StockMarket")
            if not stock_market_cog:
                await ctx.send("❌ Stock market system unavailable!")
                return
            
            balance = await stock_market_cog.get_user_balance(ctx.author.id)
            
            short_fee = (price * amount) * self.short_fee_percent
            proceeds = (price * amount) - short_fee
            
            # User gets proceeds but must have enough for fee
            if balance < short_fee:
                await ctx.send(f"❌ Insufficient funds for short fee! Need ${short_fee:,.2f}, have ${balance:,.2f}")
                return
            
            # Deduct shares from market
            await conn.execute(
                "UPDATE stocks SET available_shares = available_shares - $1 WHERE id = $2",
                amount, stock_id
            )
            
            # Create short position
            await conn.execute(
                """INSERT INTO short_positions (user_id, stock_id, shares, entry_price)
                   VALUES ($1, $2, $3, $4)""",
                ctx.author.id, stock_id, amount, price
            )
            
            # Pay short fee and give proceeds
            await stock_market_cog.update_user_balance(ctx.author.id, proceeds - short_fee)
        
        # Update trade cooldown
        await self.update_trade_cooldown(ctx.author.id, ticker)
        
        new_balance = await stock_market_cog.get_user_balance(ctx.author.id)
        
        embed = discord.Embed(
            title="📉 Short Position Opened",
            color=discord.Color.red()
        )
        embed.add_field(name="Stock", value=f"{ticker} ({company_name})", inline=False)
        embed.add_field(name="Shares Shorted", value=f"{amount:,}", inline=True)
        embed.add_field(name="Entry Price", value=f"${price:,.2f}/share", inline=True)
        embed.add_field(name="Short Fee (3%)", value=f"${short_fee:,.2f}", inline=True)
        embed.add_field(name="Proceeds", value=f"${proceeds:,.2f}", inline=True)
        embed.add_field(name="New Balance", value=f"${new_balance:,.2f}", inline=True)
        embed.set_footer(text=f"Cover with: /cover {ticker} {amount}")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="cover")
    async def cover_short(self, ctx, ticker: str, amount: int):
        """Cover (close) a short position
        
        Usage: /cover MYCO 10
        """
        ticker = ticker.upper()
        
        if amount <= 0:
            await ctx.send("❌ Amount must be positive!")
            return
        
        # Check trade cooldown
        can_trade, remaining = await self.check_trade_cooldown(ctx.author.id, ticker)
        if not can_trade:
            await ctx.send(f"⏰ Please wait {remaining}s before trading {ticker} again!")
            return
        
        async with self.bot.db.acquire() as conn:
            # Get stock and short position info
            result = await conn.fetchrow(
                """SELECT s.id, s.price, sp.shares, sp.entry_price, c.name
                   FROM stocks s
                   JOIN companies c ON s.company_id = c.id
                   JOIN short_positions sp ON s.id = sp.stock_id
                   WHERE s.ticker = $1 AND sp.user_id = $2""",
                ticker, ctx.author.id
            )
            
            if not result:
                await ctx.send(f"❌ You don't have a short position on {ticker}!")
                return
            
            stock_id = result['id']
            current_price = float(result['price'])
            short_shares = result['shares']
            entry_price = float(result['entry_price'])
            company_name = result['name']
            
            if amount > short_shares:
                await ctx.send(f"❌ You only have {short_shares:,} shares shorted!")
                return
            
            # Calculate profit/loss
            price_diff = entry_price - current_price
            total_pnl = price_diff * amount
            cost_to_cover = current_price * amount
            
            stock_market_cog = self.bot.get_cog("StockMarket")
            if not stock_market_cog:
                await ctx.send("❌ Stock market system unavailable!")
                return
            
            balance = await stock_market_cog.get_user_balance(ctx.author.id)
            
            # Need to pay to buy back shares
            if balance < cost_to_cover:
                await ctx.send(f"❌ Insufficient funds to cover! Need ${cost_to_cover:,.2f}, have ${balance:,.2f}")
                return
            
            # Update short position or remove if fully covered
            if amount == short_shares:
                await conn.execute(
                    "DELETE FROM short_positions WHERE user_id = $1 AND stock_id = $2",
                    ctx.author.id, stock_id
                )
            else:
                await conn.execute(
                    "UPDATE short_positions SET shares = shares - $1 WHERE user_id = $2 AND stock_id = $3",
                    amount, ctx.author.id, stock_id
                )
            
            # Return shares to market
            await conn.execute(
                "UPDATE stocks SET available_shares = available_shares + $1 WHERE id = $2",
                amount, stock_id
            )
            
            # Update balance (cost to buy back + PnL)
            await stock_market_cog.update_user_balance(ctx.author.id, total_pnl - cost_to_cover)
        
        # Update trade cooldown
        await self.update_trade_cooldown(ctx.author.id, ticker)
        
        new_balance = await stock_market_cog.get_user_balance(ctx.author.id)
        
        profit_color = discord.Color.green() if total_pnl > 0 else discord.Color.red()
        pnl_emoji = "📈" if total_pnl > 0 else "📉" if total_pnl < 0 else "➡️"
        
        embed = discord.Embed(
            title=f"{pnl_emoji} Short Position Covered",
            color=profit_color
        )
        embed.add_field(name="Stock", value=f"{ticker} ({company_name})", inline=False)
        embed.add_field(name="Shares Covered", value=f"{amount:,}", inline=True)
        embed.add_field(name="Entry Price", value=f"${entry_price:,.2f}/share", inline=True)
        embed.add_field(name="Cover Price", value=f"${current_price:,.2f}/share", inline=True)
        embed.add_field(name="Cost to Cover", value=f"${cost_to_cover:,.2f}", inline=True)
        embed.add_field(name="Profit/Loss", value=f"${total_pnl:+,.2f}", inline=True)
        embed.add_field(name="New Balance", value=f"${new_balance:,.2f}", inline=True)
        
        if amount < short_shares:
            remaining = short_shares - amount
            embed.set_footer(text=f"Remaining short position: {remaining:,} shares")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="short_positions")
    async def view_short_positions(self, ctx, user: discord.User = None):
        """View your active short positions"""
        user = user or ctx.author
        
        async with self.bot.db.acquire() as conn:
            positions = await conn.fetch(
                """SELECT s.ticker, c.name, s.price, sp.shares, sp.entry_price, sp.opened_at
                   FROM short_positions sp
                   JOIN stocks s ON sp.stock_id = s.id
                   JOIN companies c ON s.company_id = c.id
                   WHERE sp.user_id = $1
                   ORDER BY sp.opened_at DESC""",
                user.id
            )
        
        embed = discord.Embed(
            title=f"📉 {user.display_name}'s Short Positions",
            color=discord.Color.red()
        )
        
        if not positions:
            embed.description = "No active short positions"
        else:
            total_pnl = 0
            for row in positions:
                ticker = row['ticker']
                company = row['name']
                current_price = float(row['price'])
                shares = row['shares']
                entry_price = float(row['entry_price'])
                opened_at = row['opened_at']
                
                # Calculate unrealized P&L
                price_diff = entry_price - current_price
                position_pnl = price_diff * shares
                total_pnl += position_pnl
                
                pnl_emoji = "📈" if position_pnl > 0 else "📉" if position_pnl < 0 else "➡️"
                
                embed.add_field(
                    name=f"{ticker} - {company}",
                    value=f"Shares: {shares:,} | Entry: ${entry_price:,.2f} | Current: ${current_price:,.2f}\n"
                          f"{pnl_emoji} Unrealized P&L: **${position_pnl:+,.2f}**\n"
                          f"Opened: {opened_at.strftime('%Y-%m-%d %H:%M')}",
                    inline=False
                )
            
            total_emoji = "📈" if total_pnl > 0 else "📉" if total_pnl < 0 else "➡️"
            embed.add_field(
                name=f"{total_emoji} Total Unrealized P&L",
                value=f"**${total_pnl:+,.2f}**",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="set_short_fee")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def set_short_fee(self, ctx, fee_percentage: float):
        """Set the short selling fee percentage (Admin/Owner only)
        
        Usage: /set_short_fee 3.0
        """
        if fee_percentage < 0 or fee_percentage > 100:
            await ctx.send("❌ Fee percentage must be between 0 and 100!")
            return
        
        old_fee = self.short_fee_percent * 100
        self.short_fee_percent = fee_percentage / 100
        
        embed = discord.Embed(
            title="📉 Short Fee Updated",
            color=discord.Color.blue()
        )
        embed.add_field(name="Previous Fee", value=f"{old_fee:.1f}%", inline=True)
        embed.add_field(name="New Fee", value=f"{fee_percentage:.1f}%", inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="set_trade_cooldown")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def set_trade_cooldown(self, ctx, seconds: int):
        """Set the cooldown between trades of the same stock (Admin/Owner only)
        
        Usage: /set_trade_cooldown 300
        """
        if seconds < 0 or seconds > 3600:
            await ctx.send("❌ Cooldown must be between 0 and 3600 seconds (1 hour)!")
            return
        
        old_cooldown = self.trade_cooldown_seconds
        self.trade_cooldown_seconds = seconds
        
        embed = discord.Embed(
            title="⏰ Trade Cooldown Updated",
            color=discord.Color.blue()
        )
        embed.add_field(name="Previous Cooldown", value=f"{old_cooldown}s ({old_cooldown // 60}m)", inline=True)
        embed.add_field(name="New Cooldown", value=f"{seconds}s ({seconds // 60}m)", inline=True)
        
        if seconds == 0:
            embed.add_field(name="⚠️ Warning", value="Trade cooldown is disabled!", inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="force_cover")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def force_cover(self, ctx, user: discord.User, ticker: str):
        """Force cover a user's short position (Admin/Owner only)"""
        ticker = ticker.upper()
        
        async with self.bot.db.acquire() as conn:
            result = await conn.fetchrow(
                """SELECT s.id, s.price, sp.shares, sp.entry_price, c.name
                   FROM stocks s
                   JOIN companies c ON s.company_id = c.id
                   JOIN short_positions sp ON s.id = sp.stock_id
                   WHERE s.ticker = $1 AND sp.user_id = $2""",
                ticker, user.id
            )
            
            if not result:
                await ctx.send(f"❌ {user.mention} doesn't have a short position on {ticker}!")
                return
            
            stock_id = result['id']
            current_price = float(result['price'])
            shares = result['shares']
            entry_price = float(result['entry_price'])
            company_name = result['name']
            
            # Calculate P&L
            price_diff = entry_price - current_price
            total_pnl = price_diff * shares
            cost_to_cover = current_price * shares
            
            # Remove short position
            await conn.execute(
                "DELETE FROM short_positions WHERE user_id = $1 AND stock_id = $2",
                user.id, stock_id
            )
            
            # Return shares to market
            await conn.execute(
                "UPDATE stocks SET available_shares = available_shares + $1 WHERE id = $2",
                shares, stock_id
            )
            
            # Update user balance
            stock_market_cog = self.bot.get_cog("StockMarket")
            if stock_market_cog:
                await stock_market_cog.update_user_balance(user.id, total_pnl - cost_to_cover)
        
        embed = discord.Embed(
            title="🔨 Short Position Force Covered",
            description=f"{user.mention}'s position on **{ticker}** was force covered by an administrator",
            color=discord.Color.orange()
        )
        embed.add_field(name="Shares", value=f"{shares:,}", inline=True)
        embed.add_field(name="Entry Price", value=f"${entry_price:,.2f}", inline=True)
        embed.add_field(name="Cover Price", value=f"${current_price:,.2f}", inline=True)
        embed.add_field(name="P&L", value=f"${total_pnl:+,.2f}", inline=True)
        
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(ShortSelling(bot))

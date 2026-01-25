import discord
from discord.ext import commands
from typing import List

class HelpSystem(commands.Cog):
    """Comprehensive help system for all bot commands"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.hybrid_command(name="help")
    async def help_command(self, ctx, category: str = None):
        """View all available commands
        
        Usage: 
        - /help - View all categories
        - /help company - View company management commands
        - /help report - View report filing commands
        - /help stock - View stock market commands
        - /help short - View short selling commands
        - /help tax - View tax system commands
        - /help admin - View admin commands
        """
        
        if not category:
            # Main help menu
            embed = discord.Embed(
                title="📚 Francesca's Banking System - Help",
                description="Welcome to the trading and business server! Here's how to get started.",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="🏢 Company Management",
                value="`/help company` - Register companies, view balances, manage CEO salary",
                inline=False
            )
            
            embed.add_field(
                name="📊 Financial Reports",
                value="`/help report` - File reports, earn money, view cooldowns",
                inline=False
            )
            
            embed.add_field(
                name="📈 Stock Market",
                value="`/help stock` - Buy/sell stocks, go public, manage portfolio",
                inline=False
            )
            
            embed.add_field(
                name="📉 Short Selling",
                value="`/help short` - Short stocks, cover positions, advanced trading",
                inline=False
            )
            
            embed.add_field(
                name="🏛️ Tax System",
                value="`/help tax` - View tax brackets, calculate taxes",
                inline=False
            )
            
            embed.add_field(
                name="⚙️ Admin Commands",
                value="`/help admin` - Administrative and moderation commands",
                inline=False
            )
            
            embed.add_field(
                name="💬 Francesca Control",
                value="• Say **'Thanks Francesca'** to pause responses in this channel\n"
                      "• Say **'Hey Francesca'** to resume responses\n"
                      "• Say **'Close Francesca'** to close a thread (with proper role)",
                inline=False
            )
            
            embed.set_footer(text="💡 Tip: Use /help [category] for detailed command lists!")
            
            await ctx.send(embed=embed)
            
        elif category.lower() in ["company", "companies"]:
            await self._show_company_help(ctx)
        elif category.lower() in ["report", "reports", "filing"]:
            await self._show_report_help(ctx)
        elif category.lower() in ["stock", "stocks", "market"]:
            await self._show_stock_help(ctx)
        elif category.lower() in ["short", "shorting", "shorts"]:
            await self._show_short_help(ctx)
        elif category.lower() in ["tax", "taxes"]:
            await self._show_tax_help(ctx)
        elif category.lower() in ["admin", "administrator", "mod"]:
            await self._show_admin_help(ctx)
        else:
            await ctx.send(f"❌ Unknown category: `{category}`\nUse `/help` to see all categories.")
    
    async def _show_company_help(self, ctx):
        """Show company management commands"""
        embed = discord.Embed(
            title="🏢 Company Management Commands",
            description="Create and manage your business empire!",
            color=discord.Color.gold()
        )
        
        commands_list = [
            ("ub!register_company <name>", "Register a new company (max 3 by default)"),
            ("ub!my_companies [@user]", "View detailed info about your companies"),
            ("ub!company_balance [name]", "Check your company's balance"),
            ("ub!set_ceo_salary <company> <percent>", "Set your CEO salary percentage (e.g., 7.5)"),
            ("ub!disband_company <name>", "Permanently delete your company (requires confirmation)"),
        ]
        
        for cmd, desc in commands_list:
            embed.add_field(name=f"`{cmd}`", value=desc, inline=False)
        
        embed.add_field(
            name="💡 Getting Started",
            value="1. Register a company with `ub!register_company \"My Company\"`\n"
                  "2. File financial reports to earn money\n"
                  "3. Optionally go public to let others invest",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    async def _show_report_help(self, ctx):
        """Show report filing commands"""
        embed = discord.Embed(
            title="📊 Financial Report Commands",
            description="File reports to earn money for your companies!",
            color=discord.Color.green()
        )
        
        commands_list = [
            ("ub!file_report", "Start filing a financial report (guided process)"),
            ("ub!cancel_report", "Cancel your active report session"),
            ("ub!report_status", "Check your active report session"),
            ("ub!view_reports <company>", "View past reports for a company"),
            ("ub!view_report_cooldown", "Check cooldown status for all your companies"),
        ]
        
        for cmd, desc in commands_list:
            embed.add_field(name=f"`{cmd}`", value=desc, inline=False)
        
        embed.add_field(
            name="📝 How Reports Work",
            value="1. File with `ub!file_report`\n"
                  "2. Enter your company name\n"
                  "3. Set expense percentage\n"
                  "4. Add items with format: `Item Name | Price`\n"
                  "5. Type `done` to process\n"
                  "6. Dice rolls determine sales (1-100 units per item)\n"
                  "7. Corporate tax applied, then CEO salary, then personal tax",
            inline=False
        )
        
        embed.add_field(
            name="⏰ Cooldown",
            value="Each company has a **48-hour cooldown** between reports",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    async def _show_stock_help(self, ctx):
        """Show stock market commands"""
        embed = discord.Embed(
            title="📈 Stock Market Commands",
            description="Trade stocks and grow your wealth!",
            color=discord.Color.blue()
        )
        
        # Split into two embeds if needed
        basic_commands = [
            ("ub!stocks", "View all publicly traded stocks"),
            ("ub!buy <TICKER> <amount>", "Buy shares of a stock"),
            ("ub!sell <TICKER> <amount>", "Sell your shares"),
            ("ub!portfolio [@user]", "View investment portfolio"),
            ("ub!balance [@user]", "Check cash balance"),
            ("ub!transfer_money @user <amount>", "Transfer money to another user"),
        ]
        
        for cmd, desc in basic_commands:
            embed.add_field(name=f"`{cmd}`", value=desc, inline=False)
        
        await ctx.send(embed=embed)
        
        # Second embed for IPO commands
        embed2 = discord.Embed(
            title="📈 Stock Market Commands (continued)",
            color=discord.Color.blue()
        )
        
        ipo_commands = [
            ("ub!go_public <company> <TICKER> <price> <total_shares> <owner_%>", 
             "Take your company public (e.g., `ub!go_public \"My Corp\" MYCORP 100 1000 51`)"),
            ("ub!adjust_shares <TICKER> <new_available>", "Adjust publicly available shares (owners only)"),
        ]
        
        for cmd, desc in ipo_commands:
            embed2.add_field(name=f"`{cmd}`", value=desc, inline=False)
        
        embed2.add_field(
            name="💡 IPO Example",
            value="`ub!go_public \"TechCorp\" TECH 100 1000 51`\n"
                  "• Company: TechCorp\n"
                  "• Ticker: TECH\n"
                  "• Price: $100/share\n"
                  "• Total shares: 1000\n"
                  "• You keep: 51% (510 shares)\n"
                  "• Public gets: 49% (490 shares)",
            inline=False
        )
        
        await ctx.send(embed=embed2)
    
    async def _show_short_help(self, ctx):
        """Show short selling commands"""
        embed = discord.Embed(
            title="📉 Short Selling Commands",
            description="Advanced trading: Profit from falling stock prices!",
            color=discord.Color.red()
        )
        
        commands_list = [
            ("ub!short <TICKER> <amount>", "Open a short position (bet on price falling)"),
            ("ub!cover <TICKER> <amount>", "Close your short position"),
            ("ub!short_positions [@user]", "View active short positions"),
        ]
        
        for cmd, desc in commands_list:
            embed.add_field(name=f"`{cmd}`", value=desc, inline=False)
        
        embed.add_field(
            name="📚 How Shorting Works",
            value="1. **Short**: Borrow and sell shares at current price (pay 3% fee)\n"
                  "2. **Wait**: Hope the price goes down\n"
                  "3. **Cover**: Buy shares back at (hopefully) lower price\n"
                  "4. **Profit**: (entry_price - cover_price) × shares\n\n"
                  "⚠️ **Risk**: If price goes UP, you lose money!",
            inline=False
        )
        
        embed.add_field(
            name="📊 Example",
            value="• Short 10 shares of TECH at $100 (pay $30 fee, get $970)\n"
                  "• Price drops to $80\n"
                  "• Cover 10 shares for $800\n"
                  "• **Profit**: ($100-$80)×10 - fee = $200 - $30 = **$170**",
            inline=False
        )
        
        embed.add_field(
            name="⏰ Trade Cooldown",
            value="5-minute cooldown between trades of the same stock",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    async def _show_tax_help(self, ctx):
        """Show tax system commands"""
        embed = discord.Embed(
            title="🏛️ Tax System Commands",
            description="Progressive personal tax and flat corporate tax",
            color=discord.Color.purple()
        )
        
        commands_list = [
            ("ub!view_tax_brackets", "View personal income tax brackets"),
            ("ub!calculate_tax_example <income>", "Calculate tax on a specific income"),
        ]
        
        for cmd, desc in commands_list:
            embed.add_field(name=f"`{cmd}`", value=desc, inline=False)
        
        embed.add_field(
            name="💼 How Taxes Work",
            value="**Corporate Tax** (flat rate, default 25%):\n"
                  "• Applied to company gross profit\n\n"
                  "**Personal Income Tax** (progressive):\n"
                  "• Applied to CEO salary\n"
                  "• Higher income = higher tax rate\n"
                  "• Tax brackets are customizable by admins",
            inline=False
        )
        
        embed.add_field(
            name="📊 Default Tax Brackets",
            value="$0-$10k: 10%\n"
                  "$10k-$40k: 12%\n"
                  "$40k-$85k: 22%\n"
                  "$85k-$160k: 24%\n"
                  "$160k-$200k: 32%\n"
                  "$200k-$500k: 35%\n"
                  "$500k+: 37%",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    async def _show_admin_help(self, ctx):
        """Show admin commands"""
        embed = discord.Embed(
            title="⚙️ Admin Commands",
            description="Commands for server administrators and bot owners",
            color=discord.Color.orange()
        )
        
        # Company Management
        embed.add_field(
            name="🏢 Company Admin",
            value="`ub!force_disband @user <company>` - Force disband a company\n"
                  "`ub!set_max_companies <number>` - Set max companies per player",
            inline=False
        )
        
        # Stock Market
        embed.add_field(
            name="📈 Stock Market Admin",
            value="`ub!give_money @user <amount>` - Give money\n"
                  "`ub!remove_money @user <amount>` - Remove money\n"
                  "`ub!set_stock_price <TICKER> <price>` - Manually set stock price\n"
                  "`ub!delist_company <TICKER>` - Remove from stock market\n"
                  "`ub!fluctuate` - Trigger price fluctuation",
            inline=False
        )
        
        await ctx.send(embed=embed)
        
        # Second embed for more admin commands
        embed2 = discord.Embed(
            title="⚙️ Admin Commands (continued)",
            color=discord.Color.orange()
        )
        
        # Reports
        embed2.add_field(
            name="📊 Reports Admin",
            value="`ub!set_report_cooldown <hours>` - Set report cooldown\n"
                  "`ub!bypass_cooldown @user <company>` - Reset company cooldown",
            inline=False
        )
        
        # Short Selling
        embed2.add_field(
            name="📉 Short Selling Admin",
            value="`ub!set_short_fee <percent>` - Set short selling fee\n"
                  "`ub!set_trade_cooldown <seconds>` - Set trade cooldown\n"
                  "`ub!force_cover @user <TICKER>` - Force close short position",
            inline=False
        )
        
        # Tax System
        embed2.add_field(
            name="🏛️ Tax System Admin",
            value="`ub!set_corporate_tax <percent>` - Set corporate tax rate\n"
                  "`ub!set_tax_bracket <#> <min> <max> <rate>` - Set tax bracket\n"
                  "`ub!delete_tax_bracket <#>` - Delete tax bracket",
            inline=False
        )
        
        # Francesca
        embed2.add_field(
            name="💬 Francesca Admin",
            value="`ub!set_text_responder <#channel>` - Set auto-response channel\n"
                  "`ub!set_forum_responder <#forum>` - Set auto-response forum\n"
                  "`ub!remove_text_responder` - Remove text responder\n"
                  "`ub!remove_forum_responder` - Remove forum responder\n"
                  "`ub!set_closer_role @role` - Set thread closer role\n"
                  "`ub!unpause_all` - Unpause Francesca everywhere",
            inline=False
        )
        
        await ctx.send(embed=embed2)


async def setup(bot):
    await bot.add_cog(HelpSystem(bot))

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
        - /help loan - View loan system commands
        - /help tax - View tax system commands
        - /help admin - View admin commands
        - /help francesca - View Francesca AI controls
        """
        
        if not category:
            # Main help menu
            await self._show_main_help(ctx)
        elif category.lower() in ["company", "companies"]:
            await self._show_company_help(ctx)
        elif category.lower() in ["report", "reports", "filing"]:
            await self._show_report_help(ctx)
        elif category.lower() in ["stock", "stocks", "market"]:
            await self._show_stock_help(ctx)
        elif category.lower() in ["short", "shorting", "shorts"]:
            await self._show_short_help(ctx)
        elif category.lower() in ["loan", "loans"]:
            await self._show_loan_help(ctx)
        elif category.lower() in ["tax", "taxes"]:
            await self._show_tax_help(ctx)
        elif category.lower() in ["admin", "administrator", "mod"]:
            await self._show_admin_help(ctx)
        elif category.lower() in ["francesca", "ai", "chatgpt"]:
            await self._show_francesca_help(ctx)
        else:
            await ctx.send(f"❌ Unknown category: `{category}`\nUse `/help` to see all categories.")
    
    async def _show_main_help(self, ctx):
        """Main help menu"""
        embed = discord.Embed(
            title="📚 Francesca's Banking System - Complete Help",
            description="Welcome to our Bank! Here's everything you can do.",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🏢 Company Management",
            value="`/help company` - Register companies, manage balances, CEO salary",
            inline=False
        )
        
        embed.add_field(
            name="📊 Financial Reports",
            value="`/help report` - File reports, earn money, track performance",
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
            name="💰 Loan System",
            value="`/help loan` - Personal & company loans, repayment, interest",
            inline=False
        )
        
        embed.add_field(
            name="🛡️ Tax System",
            value="`/help tax` - View tax brackets, calculate taxes",
            inline=False
        )
        
        embed.add_field(
            name="🏆 Leaderboards",
            value="`/leaderboard [total/cash/company]` - View wealth rankings",
            inline=False
        )
        
        embed.add_field(
            name="⚙️ Admin Commands",
            value="`/help admin` - Administrative and moderation commands",
            inline=False
        )
        
        embed.add_field(
            name="🤖 Francesca AI",
            value="`/help francesca` - Control AI responses and features",
            inline=False
        )
        
        embed.set_footer(text="💡 Tip: Use /help [category] for detailed command lists!")
        
        await ctx.send(embed=embed)
    
    async def _show_company_help(self, ctx):
        """Show company management commands"""
        embed = discord.Embed(
            title="🏢 Company Management Commands",
            description="Create and manage your business empire!",
            color=discord.Color.gold()
        )
        
        commands_list = [
            ("ub!register_company \"<name>\"", "Register a new company (max 3 by default)"),
            ("/my-companies [@user]", "View detailed info about your companies (or another user's)"),
            ("ub!company_balance [\"name\"]", "Check your company's balance"),
            ("ub!set_ceo_salary \"<company>\" <percent>", "Set your CEO salary percentage (e.g., 7.5)"),
            ("ub!disband_company \"<name>\"", "Permanently delete your company (requires confirmation)"),
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
        
        embed.add_field(
            name="📋 Company Details",
            value="• Default max companies: 3 per player\n"
                  "• Starting balance: $0\n"
                  "• Default CEO salary: 5%\n"
                  "• Can be public or private",
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
            ("/file-report", "Start filing a financial report (guided interactive process)"),
            ("/cancel-report", "Cancel your active report session"),
            ("/report-status", "Check your active report session details"),
            ("ub!view_reports \"<company>\"", "View past reports for a company"),
            ("/view-report-cooldown", "Check cooldown status for all your companies"),
        ]
        
        for cmd, desc in commands_list:
            embed.add_field(name=f"`{cmd}`", value=desc, inline=False)
        
        embed.add_field(
            name="📝 How Reports Work",
            value="1. Start with `/file-report` or say 'I want to file a report'\n"
                  "2. Enter your company name\n"
                  "3. Set gross expense percentage (operational costs)\n"
                  "4. Add items with format: `Item Name | Price`\n"
                  "5. Type `done` when finished adding items\n"
                  "6. 🎲 Dice rolls (1-100) determine sales per item\n"
                  "7. Taxes applied: Corporate tax → CEO salary → Personal tax\n"
                  "8. Profits distributed to company & CEO",
            inline=False
        )
        
        embed.add_field(
            name="⏰ Cooldown System",
            value="• Default: **48 hours** between reports per company\n"
                  "• Each company has independent cooldown\n"
                  "• Prevents spam and maintains balance",
            inline=False
        )
        
        embed.add_field(
            name="💡 Pro Tips",
            value="• Lower expense % = higher profits\n"
                  "• Higher priced items = bigger potential earnings\n"
                  "• CEO salary affects your personal income\n"
                  "• Public companies' stock prices update after reports",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    async def _show_stock_help(self, ctx):
        """Show stock market commands"""
        # Part 1: Basic commands
        embed = discord.Embed(
            title="📈 Stock Market Commands - Part 1",
            description="Trade stocks and build your investment portfolio!",
            color=discord.Color.blue()
        )
        
        basic_commands = [
            ("/stocks", "View all publicly traded stocks with prices"),
            ("ub!buy <TICKER> <amount>", "Buy shares of a stock"),
            ("ub!sell <TICKER> <amount>", "Sell your shares"),
            ("/portfolio [@user]", "View investment portfolio and holdings"),
            ("/balance [@user]", "Check personal cash balance"),
            ("ub!transfer_money @user <amount>", "Transfer money to another user"),
        ]
        
        for cmd, desc in basic_commands:
            embed.add_field(name=f"`{cmd}`", value=desc, inline=False)
        
        await ctx.send(embed=embed)
        
        # Part 2: IPO and share management
        embed2 = discord.Embed(
            title="📈 Stock Market Commands - Part 2",
            description="Take your company public and manage shares!",
            color=discord.Color.blue()
        )
        
        ipo_commands = [
            ("/go-public", "Take your company public (interactive guided process)"),
            ("/cancel-ipo", "Cancel your active IPO session"),
            ("ub!adjust_shares <TICKER> issue <amount>", "Issue new shares (dilutes ownership, lowers price)"),
            ("ub!adjust_shares <TICKER> buyback <amount>", "Buy back shares (increases price, uses company funds)"),
            ("ub!adjust_shares <TICKER> release <amount>", "Release your shares to market (no dilution)"),
            ("ub!adjust_shares <TICKER> withdraw <amount>", "Take shares back from market"),
        ]
        
        for cmd, desc in ipo_commands:
            embed2.add_field(name=f"`{cmd}`", value=desc, inline=False)
        
        embed2.add_field(
            name="💡 IPO Process",
            value="1. Use `/go-public` to start\n"
                  "2. Select your company\n"
                  "3. Choose a ticker (3-5 letters)\n"
                  "4. Set total shares to issue\n"
                  "5. Choose ownership percentage to keep\n"
                  "6. System calculates IPO price based on company performance",
            inline=False
        )
        
        embed2.add_field(
            name="📊 Share Management",
            value="• **Issue**: Creates new shares, dilutes all shareholders\n"
                  "• **Buyback**: Removes shares, increases scarcity and price\n"
                  "• **Release**: Owner sells personal shares to public\n"
                  "• **Withdraw**: Owner takes shares off market",
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
            ("ub!short <TICKER> <amount>", "Open a short position (bet on price falling, 3% fee)"),
            ("ub!cover <TICKER> <amount>", "Close your short position"),
            ("/short-positions [@user]", "View active short positions with P&L"),
        ]
        
        for cmd, desc in commands_list:
            embed.add_field(name=f"`{cmd}`", value=desc, inline=False)
        
        embed.add_field(
            name="📚 How Shorting Works",
            value="1. **Short**: Borrow and sell shares at current price\n"
                  "   • Pay 3% fee upfront\n"
                  "   • Receive proceeds minus fee\n"
                  "   • Shares removed from market\n\n"
                  "2. **Wait**: Hope the price goes down\n\n"
                  "3. **Cover**: Buy shares back at (hopefully) lower price\n"
                  "   • Pay current price × shares\n"
                  "   • Shares returned to market\n\n"
                  "4. **Profit/Loss**: (entry_price - cover_price) × shares - fee",
            inline=False
        )
        
        embed.add_field(
            name="📊 Example Scenario",
            value="**Profitable Short:**\n"
                  "• Short 10 shares of TECH at $100 (fee: $30, receive: $970)\n"
                  "• Price drops to $80\n"
                  "• Cover 10 shares for $800\n"
                  "• **Profit**: ($100-$80)×10 - $30 = **$170**\n\n"
                  "**Losing Short:**\n"
                  "• Short 10 shares at $100 (fee: $30, receive: $970)\n"
                  "• Price rises to $120\n"
                  "• Cover costs $1,200\n"
                  "• **Loss**: ($100-$120)×10 - $30 = **-$230**",
            inline=False
        )
        
        embed.add_field(
            name="⚠️ Risks & Rules",
            value="• **Unlimited Loss Potential**: If price keeps rising, losses grow\n"
                  "• **Trade Cooldown**: 5 minutes between trades of same stock\n"
                  "• **One Position Per Stock**: Can't have multiple shorts on same ticker\n"
                  "• **Market Impact**: Removes shares from available supply",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    async def _show_loan_help(self, ctx):
        """Show loan system commands"""
        embed = discord.Embed(
            title="💰 Loan System Commands",
            description="Personal and company loans with interest!",
            color=discord.Color.gold()
        )
        
        commands_list = [
            ("/request-loan <amount>", "Request a personal loan (10% interest, 30 days)"),
            ("ub!request_company_loan \"<company>\" <amount>", "Request company loan (8% interest, 30 days)"),
            ("/repay-loan [amount]", "Repay personal loan (full or partial)"),
            ("ub!repay_company_loan \"<company>\" [amount]", "Repay company loan (full or partial)"),
            ("/my-loans", "View all your personal and company loans with status"),
        ]
        
        for cmd, desc in commands_list:
            embed.add_field(name=f"`{cmd}`", value=desc, inline=False)
        
        embed.add_field(
            name="💵 Loan Limits",
            value="• **Personal Loans**: Max $100,000 at 10% interest\n"
                  "• **Company Loans**: Max $500,000 at 8% interest\n"
                  "• **Loan Term**: 30 days to repay\n"
                  "• **Restrictions**: One active loan per type",
            inline=False
        )
        
        embed.add_field(
            name="⚠️ Late Fees",
            value="• **Rate**: 5% of principal per day overdue\n"
                  "• **Cap**: Maximum 200% of original principal\n"
                  "• **Automatic**: Fees calculated every 6 hours\n"
                  "• **Compounds**: Fees add to total owed",
            inline=False
        )
        
        embed.add_field(
            name="📊 Example",
            value="**Personal Loan:**\n"
                  "• Borrow: $50,000\n"
                  "• Interest (10%): $5,000\n"
                  "• Total Owed: $55,000\n"
                  "• Due: 30 days from now\n\n"
                  "**If Late (5 days):**\n"
                  "• Late Fee: $50,000 × 5% × 5 = $12,500\n"
                  "• New Total: $67,500",
            inline=False
        )
        
        embed.add_field(
            name="💡 Tips",
            value="• Use `/my-loans` to track due dates\n"
                  "• Partial payments reduce total owed\n"
                  "• Company loans have lower interest rates\n"
                  "• Pay before due date to avoid late fees",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    async def _show_tax_help(self, ctx):
        """Show tax system commands"""
        embed = discord.Embed(
            title="🛡️ Tax System Commands",
            description="Progressive personal tax and flat corporate tax",
            color=discord.Color.purple()
        )
        
        commands_list = [
            ("/view-tax-brackets", "View personal income tax brackets"),
            ("ub!calculate_tax_example <income>", "Calculate tax on specific income amount"),
        ]
        
        for cmd, desc in commands_list:
            embed.add_field(name=f"`{cmd}`", value=desc, inline=False)
        
        embed.add_field(
            name="💼 How Taxes Work",
            value="**Corporate Tax** (flat rate, default 25%):\n"
                  "• Applied to company gross profit\n"
                  "• Calculated: Gross Revenue - Expenses\n"
                  "• Deducted before CEO salary\n\n"
                  "**Personal Income Tax** (progressive):\n"
                  "• Applied to CEO salary\n"
                  "• Higher income = higher marginal rates\n"
                  "• Tax brackets are customizable by admins",
            inline=False
        )
        
        embed.add_field(
            name="📊 Default Tax Brackets",
            value="```\n"
                  "$0     - $10k   : 10%\n"
                  "$10k   - $40k   : 12%\n"
                  "$40k   - $85k   : 22%\n"
                  "$85k   - $160k  : 24%\n"
                  "$160k  - $200k  : 32%\n"
                  "$200k  - $500k  : 35%\n"
                  "$500k+          : 37%\n"
                  "```",
            inline=False
        )
        
        embed.add_field(
            name="📈 Tax Example",
            value="**Income: $100,000**\n"
                  "• First $10k @ 10% = $1,000\n"
                  "• Next $30k @ 12% = $3,600\n"
                  "• Next $45k @ 22% = $9,900\n"
                  "• Last $15k @ 24% = $3,600\n"
                  "• **Total Tax: $18,100 (18.1% effective)**\n"
                  "• **After Tax: $81,900**",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    async def _show_francesca_help(self, ctx):
        """Show Francesca AI control commands"""
        embed = discord.Embed(
            title="🤖 Francesca AI Controls",
            description="Manage the AI banking assistant",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="💬 User Commands",
            value="• Say **'Thanks Francesca'** - Pause AI responses in this channel\n"
                  "• Say **'Hey Francesca'** - Resume AI responses\n"
                  "• Say **'Close Francesca'** - Close thread (requires role)\n"
                  "• `/clear-chat` - Clear your conversation history with AI",
            inline=False
        )
        
        embed.add_field(
            name="⚙️ Admin Commands",
            value="`/set-text-responder <#channel>` - Set AI auto-response channel\n"
                  "`/set-forum-responder <#forum>` - Set AI auto-response forum\n"
                  "`/remove-text-responder` - Remove text channel responder\n"
                  "`/remove-forum-responder` - Remove forum responder\n"
                  "`/set-closer-role @role` - Set role that can close threads\n"
                  "`/unpause-all` - Unpause AI in all channels\n"
                  "`/responder-stats` - View AI statistics",
            inline=False
        )
        
        embed.add_field(
            name="💡 How It Works",
            value="• Francesca responds automatically in configured channels\n"
                  "• Maintains conversation history (last 10 messages)\n"
                  "• Stays silent during report filing and IPO processes\n"
                  "• Can be paused per-channel by users\n"
                  "• Uses GPT-4o-mini for responses",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    async def _show_admin_help(self, ctx):
        """Show admin commands"""
        # Part 1: Finance & Companies
        embed = discord.Embed(
            title="⚙️ Admin Commands - Part 1",
            description="Finance and Company Management",
            color=discord.Color.orange()
        )
        
        embed.add_field(
            name="💰 User Finance",
            value="`ub!give_money @user <amount>` - Give money to user\n"
                  "`ub!remove_money @user <amount>` - Remove money from user",
            inline=False
        )
        
        embed.add_field(
            name="🏢 Company Finance",
            value="`/give-company-money @user \"Company\" <amount>` - Add company funds\n"
                  "`/remove-company-money @user \"Company\" <amount>` - Remove company funds",
            inline=False
        )
        
        embed.add_field(
            name="🏭 Company Management",
            value="`ub!force_disband @user \"Company\"` - Force disband a company\n"
                  "`/set-max-companies <number>` - Set max companies per player\n"
                  "`/set-ceo-caps <private> <public>` - Set CEO salary caps\n"
                  "`/view-ceo-caps` - View current CEO caps",
            inline=False
        )
        
        await ctx.send(embed=embed)
        
        # Part 2: Stock Market
        embed2 = discord.Embed(
            title="⚙️ Admin Commands - Part 2",
            description="Stock Market & Trading",
            color=discord.Color.orange()
        )
        
        embed2.add_field(
            name="📈 Stock Market",
            value="`ub!set_stock_price <TICKER> <price>` - Manually set stock price\n"
                  "`ub!delist_company <TICKER>` - Remove from stock market\n"
                  "`ub!fluctuate` - Trigger manual price fluctuation",
            inline=False
        )
        
        embed2.add_field(
            name="📉 Short Selling",
            value="`/set-short-fee <percent>` - Set short selling fee percentage\n"
                  "`/set-trade-cooldown <seconds>` - Set trade cooldown duration\n"
                  "`ub!force_cover @user <TICKER>` - Force close short position",
            inline=False
        )
        
        await ctx.send(embed=embed2)
        
        # Part 3: Reports, Taxes, Loans
        embed3 = discord.Embed(
            title="⚙️ Admin Commands - Part 3",
            description="Reports, Taxes, and Loans",
            color=discord.Color.orange()
        )
        
        embed3.add_field(
            name="📊 Reports",
            value="`/set-report-cooldown <hours>` - Set report cooldown duration\n"
                  "`/bypass-cooldown @user \"Company\"` - Reset company cooldown",
            inline=False
        )
        
        embed3.add_field(
            name="🛡️ Tax System",
            value="`/set-corporate-tax <percent>` - Set corporate tax rate\n"
                  "`/set-tax-bracket <#> <min> <max> <rate>` - Configure tax bracket\n"
                  "`/delete-tax-bracket <#>` - Delete tax bracket",
            inline=False
        )
        
        embed3.add_field(
            name="💰 Loan System",
            value="`/loan-settings` - View loan system configuration\n"
                  "`/set-loan-interest <personal|company> <percent>` - Set interest rates\n"
                  "`/set-max-loan <personal|company> <amount>` - Set max loan amounts\n"
                  "`/forgive-loan @user <personal|company>` - Forgive a loan\n"
                  "`/check-overdue` - Manually check and apply late fees",
            inline=False
        )
        
        await ctx.send(embed=embed3)
    
    @commands.hybrid_command(name="commands")
    async def list_all_commands(self, ctx):
        """Quick reference list of ALL commands"""
        embed = discord.Embed(
            title="📋 Complete Command List",
            description="All available commands (use /help [category] for details)",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🏢 Company (7)",
            value="`register_company` `my-companies` `company_balance` `set_ceo_salary` `disband_company` `force_disband` `set_max_companies`",
            inline=False
        )
        
        embed.add_field(
            name="📊 Reports (6)",
            value="`file-report` `cancel-report` `report-status` `view_reports` `view-report-cooldown` `set-report-cooldown`",
            inline=False
        )
        
        embed.add_field(
            name="📈 Stocks (12)",
            value="`stocks` `buy` `sell` `portfolio` `balance` `transfer_money` `go-public` `cancel-ipo` `adjust_shares` `fluctuate` `set_stock_price` `delist_company`",
            inline=False
        )
        
        embed.add_field(
            name="📉 Shorts (6)",
            value="`short` `cover` `short-positions` `set-short-fee` `set-trade-cooldown` `force_cover`",
            inline=False
        )
        
        embed.add_field(
            name="💰 Loans (10)",
            value="`request-loan` `request_company_loan` `repay-loan` `repay_company_loan` `my-loans` `loan-settings` `set-loan-interest` `set-max-loan` `forgive-loan` `check-overdue`",
            inline=False
        )
        
        embed.add_field(
            name="🛡️ Taxes (5)",
            value="`view-tax-brackets` `calculate_tax_example` `set-corporate-tax` `set-tax-bracket` `delete-tax-bracket`",
            inline=False
        )
        
        embed.add_field(
            name="🏆 Other (5)",
            value="`leaderboard` `help` `clear-chat` `give_money` `remove_money`",
            inline=False
        )
        
        embed.add_field(
            name="🤖 Francesca (7)",
            value="`set-text-responder` `set-forum-responder` `remove-text-responder` `remove-forum-responder` `set-closer-role` `unpause-all` `responder-stats`",
            inline=False
        )
        
        embed.set_footer(text="Total: 58+ commands | Use /help [category] for detailed information")
        
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(HelpSystem(bot))

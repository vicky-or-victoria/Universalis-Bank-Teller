import discord
from discord.ext import commands
from discord.ui import Button, View

class HelpGuideView(View):
    """Interactive help guide with category buttons"""
    
    def __init__(self):
        super().__init__(timeout=None)  # Persistent view
    
    @discord.ui.button(label="🏢 Companies", style=discord.ButtonStyle.primary, custom_id="help_companies")
    async def companies_button(self, interaction: discord.Interaction, button: Button):
        embed = self.get_companies_embed()
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="📊 Reports", style=discord.ButtonStyle.primary, custom_id="help_reports")
    async def reports_button(self, interaction: discord.Interaction, button: Button):
        embed = self.get_reports_embed()
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="📈 Stocks", style=discord.ButtonStyle.primary, custom_id="help_stocks")
    async def stocks_button(self, interaction: discord.Interaction, button: Button):
        embed = self.get_stocks_embed()
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="📉 Short Selling", style=discord.ButtonStyle.primary, custom_id="help_shorts")
    async def shorts_button(self, interaction: discord.Interaction, button: Button):
        embed = self.get_shorts_embed()
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="💰 Loans", style=discord.ButtonStyle.success, custom_id="help_loans")
    async def loans_button(self, interaction: discord.Interaction, button: Button):
        embed = self.get_loans_embed()
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="🛡️ Taxes", style=discord.ButtonStyle.success, custom_id="help_taxes")
    async def taxes_button(self, interaction: discord.Interaction, button: Button):
        embed = self.get_taxes_embed()
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="🏆 Leaderboards", style=discord.ButtonStyle.success, custom_id="help_leaderboards")
    async def leaderboards_button(self, interaction: discord.Interaction, button: Button):
        embed = self.get_leaderboards_embed()
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="⚙️ Admin", style=discord.ButtonStyle.danger, custom_id="help_admin")
    async def admin_button(self, interaction: discord.Interaction, button: Button):
        embed = self.get_admin_embed()
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @staticmethod
    def get_main_embed():
        """Main help guide embed"""
        embed = discord.Embed(
            title="� Welcome to Francesca's Banking System!",
            description=(
                "**Your friendly Discord economy bot for managing companies, trading stocks, and building wealth!**\n\n"
                "Hi there! I'm Francesca (Franky for short), your personal bank teller. "
                "I'm here to help you succeed in this financial adventure! 💼✨"
            ),
            color=0x667eea
        )
        
        embed.add_field(
            name="🚀 Quick Start Guide",
            value=(
                "**1️⃣ Create a Company**\n"
                "`ub!register_company \"Your Company\"`\n\n"
                "**2️⃣ File Reports to Earn Money**\n"
                "Just say: *\"I want to file a report\"*\n\n"
                "**3️⃣ Go Public (Optional)**\n"
                "Say: *\"I want to go public\"* or use `ub!go_public`\n\n"
                "**4️⃣ Trade Stocks**\n"
                "`ub!buy TICKER amount` or `ub!sell TICKER amount`"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💬 Getting Help",
            value=(
                "**Talk to me naturally!** Just ask questions like:\n"
                "• \"How do I file a report?\"\n"
                "• \"I want to buy stocks\"\n"
                "• \"How do loans work?\"\n\n"
                "Or use `/help [category]` for detailed guides!"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📚 Detailed Guides",
            value="**Click the buttons below** to learn more about each feature!",
            inline=False
        )
        
        embed.set_footer(text="💡 Tip: Most commands work with natural language - just ask me!")
        
        return embed
    
    @staticmethod
    def get_companies_embed():
        """Companies detailed embed"""
        embed = discord.Embed(
            title="🏢 Company Management Guide",
            description="Create and manage your business empire!",
            color=0xf59e0b
        )
        
        embed.add_field(
            name="📝 Creating Your Company",
            value=(
                "`ub!register_company \"Company Name\"`\n"
                "• Max **3 companies** per player (default)\n"
                "• Starts with **$0 balance**\n"
                "• Default CEO salary: **5%**"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💼 Managing Your Company",
            value=(
                "`ub!my-companies` - View all your companies\n"
                "`ub!company_balance [\"name\"]` - Check balance\n"
                "`ub!set_ceo_salary \"Company\" 7.5` - Set CEO salary %\n"
                "`ub!disband_company \"Company\"` - Delete company"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💡 Pro Tips",
            value=(
                "• Lower CEO salary = more company growth\n"
                "• Higher CEO salary = more personal income\n"
                "• File reports regularly to earn money\n"
                "• Going public lets others invest in you!"
            ),
            inline=False
        )
        
        embed.set_footer(text="Ready to start? Create your first company today!")
        
        return embed
    
    @staticmethod
    def get_reports_embed():
        """Reports detailed embed"""
        embed = discord.Embed(
            title="📊 Financial Reports Guide",
            description="File reports to earn money for your companies!",
            color=0x10b981
        )
        
        embed.add_field(
            name="🎯 How to File Reports",
            value=(
                "**Just say:** *\"I want to file a report\"*\n\n"
                "The system will guide you through:\n"
                "1️⃣ Select your company\n"
                "2️⃣ Set expense % (operational costs)\n"
                "3️⃣ Add items: `Item Name | Price`\n"
                "4️⃣ Type `done` when finished\n"
                "5️⃣ Watch the dice rolls! 🎲"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💰 How Profits Work",
            value=(
                "**Gross Revenue** (dice rolls × prices)\n"
                "**−** Expenses (your %)\n"
                "**−** Corporate Tax (25%)\n"
                "**−** CEO Salary (your %)\n"
                "**−** Personal Tax (progressive)\n"
                "**=** Company gets remainder"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⏰ Cooldown System",
            value=(
                "• **48 hours** between reports per company\n"
                "• Each company has independent cooldown\n"
                "• Use `/view-report-cooldown` to check status"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📈 Commands",
            value=(
                "`/file-report` - Start filing\n"
                "`/cancel-report` - Cancel active session\n"
                "`/report-status` - Check session status\n"
                "`ub!view_reports \"Company\"` - View past reports"
            ),
            inline=False
        )
        
        embed.set_footer(text="💡 Tip: Higher prices = bigger potential earnings!")
        
        return embed
    
    @staticmethod
    def get_stocks_embed():
        """Stocks detailed embed"""
        embed = discord.Embed(
            title="📈 Stock Market & IPO Guide",
            description="Trade stocks and take your company public!",
            color=0x3b82f6
        )
        
        embed.add_field(
            name="📊 Basic Trading",
            value=(
                "`ub!stocks` - View all available stocks\n"
                "`ub!buy TICKER 10` - Buy 10 shares\n"
                "`ub!sell TICKER 5` - Sell 5 shares\n"
                "`ub!portfolio` - View your holdings\n"
                "`ub!balance` - Check cash balance"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🎉 Going Public (IPO)",
            value=(
                "**Say:** *\"I want to go public\"* or use `ub!go_public`\n\n"
                "The IPO wizard will guide you:\n"
                "• Choose ticker symbol (3-5 letters)\n"
                "• Set total shares to issue\n"
                "• Decide ownership percentage\n"
                "• System calculates IPO price automatically!"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔧 Managing Public Companies",
            value=(
                "`ub!adjust_shares TICKER issue 100` - Issue new shares (dilutes)\n"
                "`ub!adjust_shares TICKER buyback 50` - Buy back shares (raises price)\n"
                "`ub!adjust_shares TICKER release 25` - Release your shares to market\n"
                "`ub!adjust_shares TICKER withdraw 25` - Take shares back"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💡 Stock Price Factors",
            value=(
                "• Company financial reports\n"
                "• Share buybacks/issuances\n"
                "• Daily market fluctuations\n"
                "• Supply and demand"
            ),
            inline=False
        )
        
        embed.set_footer(text="💡 Tip: Keep 51%+ ownership for majority control!")
        
        return embed
    
    @staticmethod
    def get_shorts_embed():
        """Short selling detailed embed"""
        embed = discord.Embed(
            title="📉 Short Selling Guide",
            description="Advanced trading - profit from falling prices!",
            color=0xef4444
        )
        
        embed.add_field(
            name="🎯 How Shorting Works",
            value=(
                "**1. Short:** Borrow & sell shares at current price\n"
                "   • Pay 3% fee upfront\n"
                "   • Shares removed from market\n\n"
                "**2. Wait:** Hope price goes down 📉\n\n"
                "**3. Cover:** Buy back shares at new price\n"
                "   • Shares returned to market\n\n"
                "**Profit = (entry price − cover price) × shares − fee**"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📊 Example: Profitable Short",
            value=(
                "Short 10 shares of TECH at **$100**\n"
                "• Fee: $30 | Receive: $970\n"
                "• Price drops to **$80**\n"
                "• Cover for $800\n"
                "**💰 Profit: $170**"
            ),
            inline=True
        )
        
        embed.add_field(
            name="📊 Example: Losing Short",
            value=(
                "Short 10 shares at **$100**\n"
                "• Fee: $30 | Receive: $970\n"
                "• Price rises to **$120**\n"
                "• Cover costs $1,200\n"
                "**📉 Loss: -$230**"
            ),
            inline=True
        )
        
        embed.add_field(
            name="⚙️ Commands",
            value=(
                "`ub!short TICKER 10` - Open short position\n"
                "`ub!cover TICKER 10` - Close position\n"
                "`ub!short_positions` - View active shorts"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚠️ Important Rules",
            value=(
                "• **5-minute cooldown** between trades\n"
                "• **One position per stock** at a time\n"
                "• **Unlimited loss potential** if price keeps rising\n"
                "• Removes shares from market supply"
            ),
            inline=False
        )
        
        embed.set_footer(text="⚠️ Warning: High risk, high reward!")
        
        return embed
    
    @staticmethod
    def get_loans_embed():
        """Loans detailed embed"""
        embed = discord.Embed(
            title="💰 Loan System Guide",
            description="Personal and company loans with interest!",
            color=0xf59e0b
        )
        
        embed.add_field(
            name="💵 Personal Loans",
            value=(
                "`/request-loan 50000` - Request personal loan\n"
                "• Max: **$100,000**\n"
                "• Interest: **10%**\n"
                "• Duration: **30 days**\n"
                "• One active loan at a time"
            ),
            inline=True
        )
        
        embed.add_field(
            name="🏢 Company Loans",
            value=(
                "`ub!request_company_loan \"Company\" 200000`\n"
                "• Max: **$500,000**\n"
                "• Interest: **8%**\n"
                "• Duration: **30 days**\n"
                "• One per company"
            ),
            inline=True
        )
        
        embed.add_field(
            name="💳 Repayment",
            value=(
                "`/repay-loan [amount]` - Repay personal (full/partial)\n"
                "`ub!repay_company_loan \"Company\" [amount]` - Repay company\n"
                "`/my-loans` - View all loans & status"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚠️ Late Fees",
            value=(
                "• **5% per day** of principal\n"
                "• Capped at **200%** of original loan\n"
                "• Applied automatically every 6 hours\n"
                "• Compounds with total owed"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📊 Example",
            value=(
                "**Personal Loan:**\n"
                "Borrow: $50,000\n"
                "Interest (10%): $5,000\n"
                "**Total Owed: $55,000**\n\n"
                "**If 5 Days Late:**\n"
                "Late Fee: $50k × 5% × 5 = $12,500\n"
                "**New Total: $67,500**"
            ),
            inline=False
        )
        
        embed.set_footer(text="💡 Tip: Use /my-loans to track due dates!")
        
        return embed
    
    @staticmethod
    def get_taxes_embed():
        """Taxes detailed embed"""
        embed = discord.Embed(
            title="🛡️ Tax System Guide",
            description="Progressive personal tax & flat corporate tax",
            color=0x8b5cf6
        )
        
        embed.add_field(
            name="🏢 Corporate Tax",
            value=(
                "• **Flat rate:** 25% (default)\n"
                "• Applied to: Gross Revenue − Expenses\n"
                "• Deducted before CEO salary\n"
                "• Affects company profits"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💼 Personal Income Tax",
            value=(
                "• **Progressive brackets** (higher income = higher rate)\n"
                "• Applied to: CEO salary\n"
                "• Deducted after corporate tax\n"
                "• Use `/view-tax-brackets` to see rates"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📊 Default Tax Brackets",
            value=(
                "```\n"
                "$0 - $10k     : 10%\n"
                "$10k - $40k   : 12%\n"
                "$40k - $85k   : 22%\n"
                "$85k - $160k  : 24%\n"
                "$160k - $200k : 32%\n"
                "$200k - $500k : 35%\n"
                "$500k+        : 37%\n"
                "```"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🧮 Example Calculation",
            value=(
                "**Income: $100,000**\n"
                "• $0-$10k @ 10% = $1,000\n"
                "• $10k-$40k @ 12% = $3,600\n"
                "• $40k-$85k @ 22% = $9,900\n"
                "• $85k-$100k @ 24% = $3,600\n"
                "**Total Tax: $18,100 (18.1%)**\n"
                "**After Tax: $81,900**"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚙️ Commands",
            value=(
                "`/view-tax-brackets` - View current rates\n"
                "`ub!calculate_tax_example 100000` - Calculate tax on income"
            ),
            inline=False
        )
        
        embed.set_footer(text="💡 Tip: Lower CEO salary = less personal tax!")
        
        return embed
    
    @staticmethod
    def get_leaderboards_embed():
        """Leaderboards detailed embed"""
        embed = discord.Embed(
            title="🏆 Leaderboards Guide",
            description="Track wealth rankings and compete with others!",
            color=0xf59e0b
        )
        
        embed.add_field(
            name="📊 Available Leaderboards",
            value=(
                "`/leaderboard` or `ub!leaderboard` - **Total Net Worth**\n"
                "• Shows: Cash + Companies + Stock Holdings\n"
                "• Top 10 wealthiest players overall\n\n"
                "`/leaderboard cash` - **Cash Balance**\n"
                "• Shows: Personal cash only\n"
                "• Top 10 by liquid assets\n\n"
                "`/leaderboard company` - **Company Balance**\n"
                "• Shows: Total company holdings\n"
                "• Top 10 by business wealth"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🥇 How Rankings Work",
            value=(
                "**Total Net Worth includes:**\n"
                "• Personal cash balance\n"
                "• All company balances\n"
                "• Current value of stock holdings\n"
                "• Updated in real-time!"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💡 Tips for Climbing",
            value=(
                "• File reports regularly\n"
                "• Invest in growing stocks\n"
                "• Take smart loans for expansion\n"
                "• Go public to raise capital\n"
                "• Balance CEO salary vs company growth"
            ),
            inline=False
        )
        
        embed.set_footer(text="🎯 Compete to become the wealthiest player!")
        
        return embed
    
    @staticmethod
    def get_admin_embed():
        """Admin commands detailed embed"""
        embed = discord.Embed(
            title="⚙️ Admin Commands Guide",
            description="Administrative and moderation tools",
            color=0xef4444
        )
        
        embed.add_field(
            name="💰 Finance Management",
            value=(
                "`ub!give_money @user 10000` - Give money to user\n"
                "`ub!remove_money @user 5000` - Remove money from user\n"
                "`/give-company-money @user \"Co\" 10000` - Give company funds\n"
                "`/remove-company-money @user \"Co\" 5000` - Remove company funds"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📈 Stock Market Admin",
            value=(
                "`ub!set_stock_price TICKER 150` - Manually set stock price\n"
                "`ub!delist_company TICKER` - Remove from market\n"
                "`ub!fluctuate` - Trigger price fluctuation\n"
                "`/set-short-fee 3.0` - Set short selling fee %\n"
                "`/set-trade-cooldown 300` - Set trade cooldown (seconds)"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🏢 Company Admin",
            value=(
                "`ub!force_disband @user \"Company\"` - Force disband company\n"
                "`/set-max-companies 5` - Set max companies per player\n"
                "`/set-ceo-caps 50000000 60000000` - Set CEO salary caps\n"
                "`/view-ceo-caps` - View current caps"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📊 Reports & Taxes",
            value=(
                "`/set-report-cooldown 48` - Set report cooldown (hours)\n"
                "`/bypass-cooldown @user \"Co\"` - Reset cooldown\n"
                "`/set-corporate-tax 25` - Set corporate tax rate\n"
                "`/set-tax-bracket 1 0 10000 10` - Configure tax bracket"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💰 Loan Admin",
            value=(
                "`/loan-settings` - View loan configuration\n"
                "`/set-loan-interest personal 10` - Set interest rates\n"
                "`/set-max-loan company 500000` - Set max loan amounts\n"
                "`/forgive-loan @user personal` - Forgive a loan\n"
                "`/check-overdue` - Manually apply late fees"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🤖 Francesca Control",
            value=(
                "`/set-text-responder #channel` - Set auto-response channel\n"
                "`/set-forum-responder #forum` - Set forum auto-response\n"
                "`/set-closer-role @role` - Set thread closer role\n"
                "`/unpause-all` - Unpause Francesca everywhere\n"
                "`/responder-stats` - View AI statistics"
            ),
            inline=False
        )
        
        embed.set_footer(text="⚠️ Admin only - Requires Administrator permission or Owner status")
        
        return embed


class GuideSystem(commands.Cog):
    """Interactive help guide system"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name="post_help_guide")
    @commands.is_owner()
    async def post_help_guide(self, ctx):
        """Post the interactive help guide (Owner only)
        
        Usage: ub!post_help_guide
        """
        view = HelpGuideView()
        embed = view.get_main_embed()
        
        await ctx.send(embed=embed, view=view)
        await ctx.message.add_reaction("✅")


async def setup(bot):
    await bot.add_cog(GuideSystem(bot))

import discord
from discord.ext import commands
import re

class FinancialReports(commands.Cog):
    """Parse and process financial reports with progressive tax"""
    
    def __init__(self, bot):
        self.bot = bot
        
        # Progressive tax brackets
        self.tax_brackets = [
            (10000, 0.10),   # First 10k: 10%
            (40000, 0.15),   # Next 40k: 15%
            (50000, 0.20),   # Next 50k: 20%
            (float('inf'), 0.25)  # Above 100k: 25%
        ]
    
    def calculate_progressive_tax(self, profit: float) -> float:
        """Calculate tax using progressive brackets"""
        if profit <= 0:
            return 0
        
        tax = 0
        remaining = profit
        previous_limit = 0
        
        for limit, rate in self.tax_brackets:
            if remaining <= 0:
                break
            
            taxable_in_bracket = min(remaining, limit - previous_limit)
            tax += taxable_in_bracket * rate
            remaining -= taxable_in_bracket
            previous_limit = limit
        
        return round(tax, 2)
    
    def parse_report(self, content: str) -> dict:
        """Parse financial report from message"""
        # Format: Company | Revenue | Expenses
        # Allow variations with different separators
        pattern = r'(.+?)\s*[\|:]\s*(\d+(?:\.\d+)?)\s*[\|:]\s*(\d+(?:\.\d+)?)'
        match = re.search(pattern, content, re.IGNORECASE)
        
        if not match:
            return None
        
        company = match.group(1).strip()
        revenue = float(match.group(2))
        expenses = float(match.group(3))
        
        return {
            'company': company,
            'revenue': revenue,
            'expenses': expenses
        }
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Auto-detect and process financial reports"""
        if message.author.bot:
            return
        
        report = self.parse_report(message.content)
        if not report:
            return
        
        # Calculate profit and tax
        gross_profit = report['revenue'] - report['expenses']
        tax = self.calculate_progressive_tax(gross_profit)
        net_profit = gross_profit - tax
        
        # Get or create company
        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "SELECT id, balance FROM companies WHERE name = ?",
                (report['company'],)
            )
            company_row = await cursor.fetchone()
            
            if not company_row:
                # Auto-register company
                await cursor.execute(
                    "INSERT INTO companies (name, owner_id) VALUES (?, ?)",
                    (report['company'], message.author.id)
                )
                company_id = cursor.lastrowid
                old_balance = 0
            else:
                company_id = company_row[0]
                old_balance = company_row[1]
            
            # Update company balance
            new_balance = old_balance + net_profit
            await cursor.execute(
                "UPDATE companies SET balance = ? WHERE id = ?",
                (new_balance, company_id)
            )
            
            # Save report
            await cursor.execute(
                """INSERT INTO reports (company_id, revenue, expenses, tax, net_profit)
                   VALUES (?, ?, ?, ?, ?)""",
                (company_id, report['revenue'], report['expenses'], tax, net_profit)
            )
            
            await self.bot.db.commit()
        
        # Create response embed
        embed = discord.Embed(
            title=f"📊 Financial Report: {report['company']}",
            color=discord.Color.green() if net_profit > 0 else discord.Color.red()
        )
        
        embed.add_field(name="💰 Revenue", value=f"${report['revenue']:,.2f}", inline=True)
        embed.add_field(name="💸 Expenses", value=f"${report['expenses']:,.2f}", inline=True)
        embed.add_field(name="📈 Gross Profit", value=f"${gross_profit:,.2f}", inline=True)
        
        embed.add_field(name="🏛️ Tax (Progressive)", value=f"${tax:,.2f}", inline=True)
        embed.add_field(name="✅ Net Profit", value=f"${net_profit:,.2f}", inline=True)
        embed.add_field(name="🏦 New Balance", value=f"${new_balance:,.2f}", inline=True)
        
        # Add tax breakdown
        tax_rate = (tax / gross_profit * 100) if gross_profit > 0 else 0
        embed.set_footer(text=f"Effective tax rate: {tax_rate:.2f}%")
        
        await message.reply(embed=embed)
    
    @commands.hybrid_command(name="report")
    async def manual_report(self, ctx, company: str, revenue: float, expenses: float):
        """Submit a financial report manually
        
        Usage: ub!report "Company Name" 50000 30000
        """
        # Create a fake message content to reuse parsing logic
        fake_content = f"{company} | {revenue} | {expenses}"
        report = self.parse_report(fake_content)
        
        if not report:
            await ctx.send("❌ Invalid report format!")
            return
        
        # Process using the same logic
        gross_profit = report['revenue'] - report['expenses']
        tax = self.calculate_progressive_tax(gross_profit)
        net_profit = gross_profit - tax
        
        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "SELECT id, balance FROM companies WHERE name = ?",
                (report['company'],)
            )
            company_row = await cursor.fetchone()
            
            if not company_row:
                await cursor.execute(
                    "INSERT INTO companies (name, owner_id) VALUES (?, ?)",
                    (report['company'], ctx.author.id)
                )
                company_id = cursor.lastrowid
                old_balance = 0
            else:
                company_id = company_row[0]
                old_balance = company_row[1]
            
            new_balance = old_balance + net_profit
            await cursor.execute(
                "UPDATE companies SET balance = ? WHERE id = ?",
                (new_balance, company_id)
            )
            
            await cursor.execute(
                """INSERT INTO reports (company_id, revenue, expenses, tax, net_profit)
                   VALUES (?, ?, ?, ?, ?)""",
                (company_id, report['revenue'], report['expenses'], tax, net_profit)
            )
            
            await self.bot.db.commit()
        
        embed = discord.Embed(
            title=f"📊 Financial Report: {report['company']}",
            color=discord.Color.green() if net_profit > 0 else discord.Color.red()
        )
        
        embed.add_field(name="💰 Revenue", value=f"${revenue:,.2f}", inline=True)
        embed.add_field(name="💸 Expenses", value=f"${expenses:,.2f}", inline=True)
        embed.add_field(name="📈 Gross Profit", value=f"${gross_profit:,.2f}", inline=True)
        embed.add_field(name="🏛️ Tax", value=f"${tax:,.2f}", inline=True)
        embed.add_field(name="✅ Net Profit", value=f"${net_profit:,.2f}", inline=True)
        embed.add_field(name="🏦 New Balance", value=f"${new_balance:,.2f}", inline=True)
        
        tax_rate = (tax / gross_profit * 100) if gross_profit > 0 else 0
        embed.set_footer(text=f"Effective tax rate: {tax_rate:.2f}%")
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(FinancialReports(bot))

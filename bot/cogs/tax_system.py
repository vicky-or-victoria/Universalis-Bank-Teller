import discord
from discord.ext import commands
from typing import Tuple

class TaxSystem(commands.Cog):
    """Progressive personal tax and corporate tax system"""
    
    def __init__(self, bot):
        self.bot = bot
        # Corporate tax rate (flat)
        self.corporate_tax_rate = 0.25  # 25% default
    
    async def calculate_personal_tax(self, income: float) -> Tuple[float, list]:
        """Calculate progressive personal income tax
        
        Returns:
            Tuple of (total_tax, breakdown_list)
        """
        async with self.bot.db.acquire() as conn:
            brackets = await conn.fetch(
                "SELECT min_income, max_income, rate FROM tax_brackets ORDER BY bracket_order"
            )
        
        total_tax = 0
        remaining_income = income
        breakdown = []
        
        for bracket in brackets:
            min_income = float(bracket['min_income'])
            max_income = float(bracket['max_income']) if bracket['max_income'] else float('inf')
            rate = float(bracket['rate'])
            
            if remaining_income <= 0:
                break
            
            # Calculate taxable amount in this bracket
            if income <= min_income:
                continue
            
            bracket_min = min_income
            bracket_max = max_income
            
            # Amount of income that falls in this bracket
            if income <= bracket_max:
                taxable_in_bracket = income - bracket_min
            else:
                taxable_in_bracket = bracket_max - bracket_min
            
            if taxable_in_bracket > 0:
                tax_in_bracket = taxable_in_bracket * rate
                total_tax += tax_in_bracket
                breakdown.append({
                    'min': bracket_min,
                    'max': bracket_max,
                    'rate': rate,
                    'taxable': taxable_in_bracket,
                    'tax': tax_in_bracket
                })
        
        return total_tax, breakdown
    
    def calculate_corporate_tax(self, gross_profit: float) -> float:
        """Calculate corporate tax (flat rate)"""
        return gross_profit * self.corporate_tax_rate
    
    @commands.hybrid_command(name="view_tax_brackets")
    async def view_tax_brackets(self, ctx):
        """View the current progressive personal income tax brackets"""
        async with self.bot.db.acquire() as conn:
            brackets = await conn.fetch(
                "SELECT min_income, max_income, rate FROM tax_brackets ORDER BY bracket_order"
            )
        
        embed = discord.Embed(
            title="📊 Personal Income Tax Brackets",
            description="Progressive tax rates for CEO salaries and personal income",
            color=discord.Color.blue()
        )
        
        for i, bracket in enumerate(brackets, 1):
            min_income = float(bracket['min_income'])
            max_income = float(bracket['max_income']) if bracket['max_income'] else None
            rate = float(bracket['rate'])
            
            if max_income:
                range_str = f"${min_income:,.0f} - ${max_income:,.0f}"
            else:
                range_str = f"${min_income:,.0f}+"
            
            embed.add_field(
                name=f"Bracket {i}: {rate * 100:.1f}%",
                value=range_str,
                inline=False
            )
        
        embed.add_field(
            name="🏢 Corporate Tax Rate",
            value=f"{self.corporate_tax_rate * 100:.1f}%",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="set_tax_bracket")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def set_tax_bracket(self, ctx, bracket_number: int, min_income: float, max_income: float, rate: float):
        """Set or update a personal income tax bracket (Admin/Owner only)
        
        Usage: /set_tax_bracket 1 0 10000 10
        - bracket_number: Which bracket (1-7)
        - min_income: Minimum income for this bracket
        - max_income: Maximum income (use 999999999 for unlimited)
        - rate: Tax rate as percentage (e.g., 10 for 10%)
        """
        if bracket_number < 1 or bracket_number > 10:
            await ctx.send("❌ Bracket number must be between 1 and 10!")
            return
        
        if rate < 0 or rate > 100:
            await ctx.send("❌ Tax rate must be between 0 and 100!")
            return
        
        if min_income < 0 or max_income < min_income:
            await ctx.send("❌ Invalid income range!")
            return
        
        rate_decimal = rate / 100
        max_income_db = None if max_income >= 999999999 else max_income
        
        async with self.bot.db.acquire() as conn:
            # Check if bracket exists
            existing = await conn.fetchrow(
                "SELECT id FROM tax_brackets WHERE bracket_order = $1",
                bracket_number
            )
            
            if existing:
                await conn.execute(
                    "UPDATE tax_brackets SET min_income = $1, max_income = $2, rate = $3 WHERE bracket_order = $4",
                    min_income, max_income_db, rate_decimal, bracket_number
                )
                action = "Updated"
            else:
                await conn.execute(
                    "INSERT INTO tax_brackets (min_income, max_income, rate, bracket_order) VALUES ($1, $2, $3, $4)",
                    min_income, max_income_db, rate_decimal, bracket_number
                )
                action = "Created"
        
        embed = discord.Embed(
            title=f"✅ Tax Bracket {action}",
            color=discord.Color.green()
        )
        embed.add_field(name="Bracket", value=str(bracket_number), inline=True)
        embed.add_field(name="Income Range", value=f"${min_income:,.0f} - ${max_income:,.0f}" if max_income < 999999999 else f"${min_income:,.0f}+", inline=True)
        embed.add_field(name="Rate", value=f"{rate}%", inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="delete_tax_bracket")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def delete_tax_bracket(self, ctx, bracket_number: int):
        """Delete a personal income tax bracket (Admin/Owner only)"""
        async with self.bot.db.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM tax_brackets WHERE bracket_order = $1",
                bracket_number
            )
        
        if result == "DELETE 0":
            await ctx.send(f"❌ Bracket {bracket_number} doesn't exist!")
        else:
            await ctx.send(f"✅ Deleted tax bracket {bracket_number}")
    
    @commands.hybrid_command(name="set_corporate_tax")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def set_corporate_tax(self, ctx, tax_percentage: float):
        """Set the corporate tax rate (Admin/Owner only)
        
        Usage: /set_corporate_tax 25
        """
        if tax_percentage < 0 or tax_percentage > 100:
            await ctx.send("❌ Tax percentage must be between 0 and 100!")
            return
        
        old_rate = self.corporate_tax_rate * 100
        self.corporate_tax_rate = tax_percentage / 100
        
        embed = discord.Embed(
            title="🏛️ Corporate Tax Rate Updated",
            description="The corporate tax rate has been adjusted!",
            color=discord.Color.blue()
        )
        embed.add_field(name="Previous Rate", value=f"{old_rate:.1f}%", inline=True)
        embed.add_field(name="New Rate", value=f"{tax_percentage:.1f}%", inline=True)
        embed.set_footer(text="This will apply to all new financial reports")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="calculate_tax_example")
    async def calculate_tax_example(self, ctx, income: float):
        """Calculate how much personal income tax you'd pay on a given income
        
        Usage: /calculate_tax_example 50000
        """
        if income < 0:
            await ctx.send("❌ Income must be positive!")
            return
        
        total_tax, breakdown = await self.calculate_personal_tax(income)
        after_tax = income - total_tax
        effective_rate = (total_tax / income * 100) if income > 0 else 0
        
        embed = discord.Embed(
            title="🧮 Personal Tax Calculator",
            description=f"Calculating tax on **${income:,.2f}** income",
            color=discord.Color.blue()
        )
        
        # Show breakdown
        breakdown_text = ""
        for b in breakdown:
            max_str = f"${b['max']:,.0f}" if b['max'] != float('inf') else "∞"
            breakdown_text += f"${b['min']:,.0f} - {max_str} @ {b['rate']*100:.1f}%: **${b['tax']:,.2f}**\n"
        
        if breakdown_text:
            embed.add_field(name="📊 Tax Breakdown", value=breakdown_text, inline=False)
        
        embed.add_field(name="Total Tax", value=f"${total_tax:,.2f}", inline=True)
        embed.add_field(name="Effective Rate", value=f"{effective_rate:.2f}%", inline=True)
        embed.add_field(name="After Tax", value=f"${after_tax:,.2f}", inline=True)
        
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(TaxSystem(bot))

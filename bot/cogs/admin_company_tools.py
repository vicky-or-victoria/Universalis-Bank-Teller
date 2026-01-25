import discord
from discord.ext import commands

class AdminCompanyTools(commands.Cog):
    """Admin tools for managing company finances"""
    
    def __init__(self, bot):
        self.bot = bot
        # CEO salary caps (adjustable)
        self.private_ceo_cap = 50000000  # $50 million for private companies
        self.public_ceo_cap = 60000000   # $60 million for public companies
    
    @commands.hybrid_command(name="give_company_money")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def give_company_money(self, ctx, user: discord.User, company_name: str, amount: float):
        """Give money to a player's company (Admin/Owner only)
        
        Usage: /give-company-money @user "Company Name" 10000
        """
        if amount <= 0:
            await ctx.send("❌ Amount must be positive!")
            return
        
        async with self.bot.db.acquire() as conn:
            company = await conn.fetchrow(
                "SELECT id, balance FROM companies WHERE owner_id = $1 AND name = $2",
                user.id, company_name
            )
            
            if not company:
                await ctx.send(f"❌ {user.mention} doesn't own a company named **{company_name}**!")
                return
            
            old_balance = float(company['balance'])
            new_balance = old_balance + amount
            
            await conn.execute(
                "UPDATE companies SET balance = $1 WHERE id = $2",
                new_balance, company['id']
            )
        
        embed = discord.Embed(
            title="✅ Company Funds Added",
            color=discord.Color.green()
        )
        embed.add_field(name="Owner", value=user.mention, inline=True)
        embed.add_field(name="Company", value=company_name, inline=True)
        embed.add_field(name="Amount Added", value=f"${amount:,.2f}", inline=True)
        embed.add_field(name="Previous Balance", value=f"${old_balance:,.2f}", inline=True)
        embed.add_field(name="New Balance", value=f"${new_balance:,.2f}", inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="remove_company_money")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def remove_company_money(self, ctx, user: discord.User, company_name: str, amount: float):
        """Remove money from a player's company (Admin/Owner only)
        
        Usage: /remove-company-money @user "Company Name" 5000
        """
        if amount <= 0:
            await ctx.send("❌ Amount must be positive!")
            return
        
        async with self.bot.db.acquire() as conn:
            company = await conn.fetchrow(
                "SELECT id, balance FROM companies WHERE owner_id = $1 AND name = $2",
                user.id, company_name
            )
            
            if not company:
                await ctx.send(f"❌ {user.mention} doesn't own a company named **{company_name}**!")
                return
            
            old_balance = float(company['balance'])
            new_balance = old_balance - amount
            
            if new_balance < 0:
                await ctx.send(f"⚠️ Warning: This will make the company balance negative (${new_balance:,.2f}). Proceeding anyway...")
            
            await conn.execute(
                "UPDATE companies SET balance = $1 WHERE id = $2",
                new_balance, company['id']
            )
        
        embed = discord.Embed(
            title="✅ Company Funds Removed",
            color=discord.Color.orange()
        )
        embed.add_field(name="Owner", value=user.mention, inline=True)
        embed.add_field(name="Company", value=company_name, inline=True)
        embed.add_field(name="Amount Removed", value=f"${amount:,.2f}", inline=True)
        embed.add_field(name="Previous Balance", value=f"${old_balance:,.2f}", inline=True)
        embed.add_field(name="New Balance", value=f"${new_balance:,.2f}", inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="set_ceo_caps")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def set_ceo_caps(self, ctx, private_cap: float, public_cap: float):
        """Set CEO salary caps for private and public companies (Admin/Owner only)
        
        Usage: /set-ceo-caps 50000000 60000000
        """
        if private_cap <= 0 or public_cap <= 0:
            await ctx.send("❌ Caps must be positive!")
            return
        
        old_private = self.private_ceo_cap
        old_public = self.public_ceo_cap
        
        self.private_ceo_cap = private_cap
        self.public_ceo_cap = public_cap
        
        embed = discord.Embed(
            title="💼 CEO Salary Caps Updated",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Private Companies",
            value=f"${old_private:,.0f} → **${private_cap:,.0f}**",
            inline=False
        )
        embed.add_field(
            name="Public Companies",
            value=f"${old_public:,.0f} → **${public_cap:,.0f}**",
            inline=False
        )
        embed.set_footer(text="These caps will apply to all future CEO salary payouts")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="view_ceo_caps")
    async def view_ceo_caps(self, ctx):
        """View current CEO salary caps"""
        embed = discord.Embed(
            title="💼 CEO Salary Caps",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="🔒 Private Companies",
            value=f"**${self.private_ceo_cap:,.0f}**",
            inline=True
        )
        embed.add_field(
            name="📈 Public Companies",
            value=f"**${self.public_ceo_cap:,.0f}**",
            inline=True
        )
        embed.set_footer(text="These are maximum CEO salaries per report filing")
        
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AdminCompanyTools(bot))

import discord
from discord.ext import commands

class Leaderboard(commands.Cog):
    """Server wealth leaderboards"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.hybrid_command(name="leaderboard")
    async def leaderboard(self, ctx, category: str = "total"):
        """View server wealth leaderboard
        
        Usage: 
        - /leaderboard - View total net worth
        - /leaderboard cash - View cash balances
        - /leaderboard company - View company balances
        
        Categories: total, cash, company
        """
        category = category.lower()
        
        if category not in ["total", "cash", "company"]:
            await ctx.send("❌ Invalid category! Use: `total`, `cash`, or `company`")
            return
        
        async with self.bot.db.acquire() as conn:
            if category == "cash":
                # Cash balance leaderboard
                results = await conn.fetch("""
                    SELECT user_id, balance
                    FROM users
                    WHERE balance > 0
                    ORDER BY balance DESC
                    LIMIT 10
                """)
                
                embed = discord.Embed(
                    title="💰 Cash Balance Leaderboard",
                    description="Top 10 players by personal cash",
                    color=discord.Color.gold()
                )
                
                for idx, row in enumerate(results, 1):
                    user = await self.bot.fetch_user(row['user_id'])
                    balance = float(row['balance'])
                    
                    medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"**{idx}.**"
                    embed.add_field(
                        name=f"{medal} {user.display_name}",
                        value=f"${balance:,.2f}",
                        inline=False
                    )
            
            elif category == "company":
                # Company balance leaderboard
                results = await conn.fetch("""
                    SELECT owner_id, SUM(balance) as total_company_balance
                    FROM companies
                    GROUP BY owner_id
                    HAVING SUM(balance) > 0
                    ORDER BY total_company_balance DESC
                    LIMIT 10
                """)
                
                embed = discord.Embed(
                    title="🏢 Company Balance Leaderboard",
                    description="Top 10 players by total company holdings",
                    color=discord.Color.blue()
                )
                
                for idx, row in enumerate(results, 1):
                    user = await self.bot.fetch_user(row['owner_id'])
                    balance = float(row['total_company_balance'])
                    
                    medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"**{idx}.**"
                    embed.add_field(
                        name=f"{medal} {user.display_name}",
                        value=f"${balance:,.2f}",
                        inline=False
                    )
            
            else:  # total
                # Total net worth (cash + companies + stock holdings)
                user_wealth = {}
                
                # Get cash balances
                cash_results = await conn.fetch("SELECT user_id, balance FROM users")
                for row in cash_results:
                    user_wealth[row['user_id']] = {
                        'cash': float(row['balance']),
                        'companies': 0,
                        'stocks': 0
                    }
                
                # Get company balances
                company_results = await conn.fetch("""
                    SELECT owner_id, SUM(balance) as total
                    FROM companies
                    GROUP BY owner_id
                """)
                for row in company_results:
                    if row['owner_id'] not in user_wealth:
                        user_wealth[row['owner_id']] = {'cash': 0, 'companies': 0, 'stocks': 0}
                    user_wealth[row['owner_id']]['companies'] = float(row['total'])
                
                # Get stock holdings value
                stock_results = await conn.fetch("""
                    SELECT h.user_id, SUM(s.price * h.shares) as total
                    FROM holdings h
                    JOIN stocks s ON h.stock_id = s.id
                    GROUP BY h.user_id
                """)
                for row in stock_results:
                    if row['user_id'] not in user_wealth:
                        user_wealth[row['user_id']] = {'cash': 0, 'companies': 0, 'stocks': 0}
                    user_wealth[row['user_id']]['stocks'] = float(row['total'])
                
                # Calculate total net worth and sort
                leaderboard_data = []
                for user_id, wealth in user_wealth.items():
                    total = wealth['cash'] + wealth['companies'] + wealth['stocks']
                    if total > 0:
                        leaderboard_data.append({
                            'user_id': user_id,
                            'total': total,
                            'cash': wealth['cash'],
                            'companies': wealth['companies'],
                            'stocks': wealth['stocks']
                        })
                
                leaderboard_data.sort(key=lambda x: x['total'], reverse=True)
                leaderboard_data = leaderboard_data[:10]
                
                embed = discord.Embed(
                    title="👑 Total Net Worth Leaderboard",
                    description="Top 10 wealthiest players (Cash + Companies + Stocks)",
                    color=discord.Color.purple()
                )
                
                for idx, data in enumerate(leaderboard_data, 1):
                    user = await self.bot.fetch_user(data['user_id'])
                    
                    medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"**{idx}.**"
                    breakdown = f"💰 Cash: ${data['cash']:,.0f}\n🏢 Companies: ${data['companies']:,.0f}\n📈 Stocks: ${data['stocks']:,.0f}"
                    
                    embed.add_field(
                        name=f"{medal} {user.display_name} - ${data['total']:,.2f}",
                        value=breakdown,
                        inline=False
                    )
        
        if not embed.fields:
            embed.description = "No data available yet!"
        
        embed.set_footer(text=f"Category: {category.title()} | Use /leaderboard [total/cash/company]")
        
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Leaderboard(bot))

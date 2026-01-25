import discord
from discord.ext import commands
import os
import aiohttp
import random
import json
from typing import Optional
from datetime import datetime, timedelta

class ReportFiling(commands.Cog):
    """Financial report filing system with dice rolls and taxes"""
    
    def __init__(self, bot):
        self.bot = bot
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        
        # Report cooldown in hours
        self.report_cooldown_hours = 48
        
        # Active report sessions (user_id -> session_data)
        self.active_sessions = {}
    
    async def call_chatgpt(self, messages: list) -> Optional[str]:
        """Call OpenAI API"""
        if not self.api_key:
            return None
        
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 500,
            "temperature": 0.7
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"ChatGPT API error: {e}")
        
        return None
    
    @commands.hybrid_command(name="file_report")
    async def file_report(self, ctx):
        """Start filing a financial report"""
        if ctx.author.id in self.active_sessions:
            session = self.active_sessions[ctx.author.id]
            channel = self.bot.get_channel(session["channel_id"])
            channel_mention = channel.mention if channel else "another channel"
            await ctx.send(f"⚠️ You already have an active report session in {channel_mention}! Use `/cancel-report` to cancel it first.")
            return
        
        self.active_sessions[ctx.author.id] = {
            "step": "company_name",
            "company_name": None,
            "gross_expenses_percent": None,
            "items": [],
            "channel_id": ctx.channel.id
        }
        
        await ctx.send(
            "*smiles warmly* Of course! I'd be happy to help you file your financial report!\n\n"
            "**Please provide your company name:**"
        )
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle report filing conversation"""
        # Ignore bot messages
        if message.author.bot:
            return
        
        user_id = message.author.id
        
        # Check if user has an active session
        if user_id not in self.active_sessions:
            return
        
        session = self.active_sessions[user_id]
        
        # Only respond in the channel where the session started
        if message.channel.id != session["channel_id"]:
            return
        
        # Don't process commands
        if message.content.startswith("ub!") or message.content.startswith("/"):
            return
        
        # Add debug logging
        print(f"[REPORT FILING] Processing message from {message.author}: {message.content[:50]}")
        print(f"[REPORT FILING] Current step: {session['step']}")
        
        try:
            # Step 1: Get company name
            if session["step"] == "company_name":
                company_name = message.content.strip()
                
                print(f"[REPORT FILING] Looking for company: {company_name}")
                
                async with self.bot.db.acquire() as conn:
                    company = await conn.fetchrow(
                        "SELECT id, ceo_salary_percent FROM companies WHERE owner_id = $1 AND name = $2",
                        user_id, company_name
                    )
                    
                    if not company:
                        await message.reply(f"❌ You don't own a company named **{company_name}**! Create it first with `/register-company`")
                        del self.active_sessions[user_id]
                        return
                    
                    company_id = company['id']
                    
                    # Check cooldown
                    last_report = await conn.fetchrow(
                        """SELECT reported_at FROM reports 
                           WHERE company_id = $1 
                           ORDER BY reported_at DESC 
                           LIMIT 1""",
                        company_id
                    )
                    
                    if last_report:
                        last_report_time = last_report['reported_at']
                        time_since_last = datetime.now() - last_report_time
                        cooldown_duration = timedelta(hours=self.report_cooldown_hours)
                        
                        if time_since_last < cooldown_duration:
                            time_remaining = cooldown_duration - time_since_last
                            hours = int(time_remaining.total_seconds() // 3600)
                            minutes = int((time_remaining.total_seconds() % 3600) // 60)
                            
                            embed = discord.Embed(
                                title="⏰ Company Report Cooldown Active",
                                description=f"**{company_name}** can file another report in **{hours}h {minutes}m**",
                                color=discord.Color.orange()
                            )
                            embed.add_field(name="Last Report", value=f"{last_report_time.strftime('%Y-%m-%d %H:%M UTC')}", inline=True)
                            embed.add_field(name="Cooldown Period", value=f"{self.report_cooldown_hours} hours per company", inline=True)
                            
                            await message.reply(embed=embed)
                            del self.active_sessions[user_id]
                            return
                
                # Update session
                session["company_name"] = company_name
                session["company_id"] = company_id
                session["ceo_salary_percent"] = float(company['ceo_salary_percent'])
                session["step"] = "gross_expenses"
                
                print(f"[REPORT FILING] Company found! Moving to gross_expenses step")
                
                # Send next prompt
                await message.reply(
                    "**What percentage of your gross revenue goes to expenses?**\n"
                    "This represents operational costs like rent, utilities, supplies, etc.\n"
                    "Enter a percentage (e.g., `35` for 35%):"
                )
            
            # Step 2: Get gross expenses
            elif session["step"] == "gross_expenses":
                try:
                    gross_expenses_percent = float(message.content.strip())
                except ValueError:
                    await message.reply("⚠️ Please enter a valid percentage number!")
                    return
                
                if gross_expenses_percent < 0 or gross_expenses_percent > 100:
                    await message.reply("⚠️ Percentage must be between 0 and 100!")
                    return
                
                session["gross_expenses_percent"] = gross_expenses_percent
                session["step"] = "items"
                
                await message.reply(
                    "**Now, let's add your products/items:**\n"
                    "Format: `Item Name | Price per unit`\n"
                    "Example: `Widget | 50` or `Premium Service | 120`\n\n"
                    "Type `done` when you've added all items."
                )
            
            # Step 3: Collect items
            elif session["step"] == "items":
                content = message.content.strip().lower()
                
                if content == "done":
                    if len(session["items"]) == 0:
                        await message.reply("⚠️ You need to add at least one item! Format: `Item Name | Price`")
                        return
                    
                    # Process the report
                    await self.process_report(message, session)
                    del self.active_sessions[user_id]
                else:
                    if "|" not in message.content:
                        await message.reply("⚠️ Invalid format! Use: `Item Name | Price`")
                        return
                    
                    parts = message.content.split("|")
                    if len(parts) != 2:
                        await message.reply("⚠️ Invalid format! Use: `Item Name | Price`")
                        return
                    
                    item_name = parts[0].strip()
                    try:
                        price = float(parts[1].strip())
                    except ValueError:
                        await message.reply("⚠️ Price must be a number!")
                        return
                    
                    if price <= 0:
                        await message.reply("⚠️ Price must be positive!")
                        return
                    
                    session["items"].append({
                        "name": item_name,
                        "price": price
                    })
                    
                    await message.add_reaction("✅")
                    await message.reply(f"Added **{item_name}** at **${price:.2f}** per unit. Add more or type `done`.")
        
        except Exception as e:
            print(f"[REPORT FILING ERROR] {e}")
            await message.reply(f"❌ An error occurred: {e}\nPlease try again or use `/cancel-report`")
            if user_id in self.active_sessions:
                del self.active_sessions[user_id]
    
    async def process_report(self, message: discord.Message, session: dict):
        """Process the financial report with all calculations"""
        company_name = session["company_name"]
        company_id = session["company_id"]
        items = session["items"]
        gross_expenses_percent = session["gross_expenses_percent"]
        ceo_salary_percent = session["ceo_salary_percent"]
        
        # Roll dice for each item
        results = []
        gross_revenue = 0
        
        embed = discord.Embed(
            title=f"🎲 Financial Report: {company_name}",
            description="*Rolling the dice for sales...*",
            color=discord.Color.blue()
        )
        
        for item in items:
            dice_roll = random.randint(1, 100)
            revenue = item["price"] * dice_roll
            gross_revenue += revenue
            
            results.append({
                "name": item["name"],
                "price": item["price"],
                "dice": dice_roll,
                "revenue": revenue
            })
            
            embed.add_field(
                name=f"🎲 {item['name']}",
                value=f"Price: ${item['price']:.2f}\nDice: **{dice_roll}**/100\nRevenue: **${revenue:,.2f}**",
                inline=True
            )
        
        # Calculate financials
        gross_expenses = gross_revenue * (gross_expenses_percent / 100)
        gross_profit = gross_revenue - gross_expenses
        
        # Get tax system
        tax_system = self.bot.get_cog("TaxSystem")
        corporate_tax = tax_system.calculate_corporate_tax(gross_profit) if tax_system else 0
        
        profit_after_corp_tax = gross_profit - corporate_tax
        
        # CEO salary
        ceo_salary_before_tax = profit_after_corp_tax * (ceo_salary_percent / 100)
        
        # Personal tax on CEO salary
        personal_tax = 0
        if tax_system and ceo_salary_before_tax > 0:
            personal_tax, _ = await tax_system.calculate_personal_tax(ceo_salary_before_tax)
        
        ceo_salary_after_tax = ceo_salary_before_tax - personal_tax
        net_profit_to_company = profit_after_corp_tax - ceo_salary_before_tax
        
        # Build embed
        embed.add_field(
            name="📊 Revenue & Expenses",
            value=f"**Gross Revenue:** ${gross_revenue:,.2f}\n"
                  f"**Expenses ({gross_expenses_percent:.1f}%):** -${gross_expenses:,.2f}\n"
                  f"**Gross Profit:** ${gross_profit:,.2f}",
            inline=False
        )
        
        corp_tax_rate = tax_system.corporate_tax_rate * 100 if tax_system else 25
        embed.add_field(
            name="🏛️ Corporate Tax",
            value=f"**Tax ({corp_tax_rate:.1f}%):** -${corporate_tax:,.2f}\n"
                  f"**After Tax:** ${profit_after_corp_tax:,.2f}",
            inline=False
        )
        
        ceo_info = f"**CEO Salary ({ceo_salary_percent:.1f}%):** ${ceo_salary_before_tax:,.2f}\n"
        if personal_tax > 0:
            ceo_info += f"**Personal Tax:** -${personal_tax:,.2f}\n"
        ceo_info += f"**CEO Take-Home:** ${ceo_salary_after_tax:,.2f}"
        
        embed.add_field(name="💼 CEO Compensation", value=ceo_info, inline=False)
        embed.add_field(name="🏢 Company Net Profit", value=f"**${net_profit_to_company:,.2f}**", inline=False)
        
        # Update balances and stock price
        async with self.bot.db.acquire() as conn:
            company = await conn.fetchrow("SELECT balance FROM companies WHERE id = $1", company_id)
            old_balance = float(company['balance'])
            new_balance = old_balance + net_profit_to_company
            
            await conn.execute("UPDATE companies SET balance = $1 WHERE id = $2", new_balance, company_id)
            
            # Pay CEO
            stock_market_cog = self.bot.get_cog("StockMarket")
            if stock_market_cog and ceo_salary_after_tax > 0:
                await stock_market_cog.update_user_balance(message.author.id, ceo_salary_after_tax)
            
            # Save report
            items_json = json.dumps(results)
            await conn.execute(
                """INSERT INTO reports (company_id, items_sold, gross_revenue, gross_expenses_percent, 
                   gross_expenses, gross_profit, corporate_tax, ceo_salary, personal_tax, net_profit) 
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
                company_id, items_json, gross_revenue, gross_expenses_percent,
                gross_expenses, gross_profit, corporate_tax, ceo_salary_before_tax,
                personal_tax, net_profit_to_company
            )
            
            # Update stock price if public
            stock = await conn.fetchrow("SELECT id, price FROM stocks WHERE company_id = $1", company_id)
            
            if stock:
                old_price = float(stock['price'])
                price_change_pct = min(max(net_profit_to_company / 10000, -0.10), 0.10)
                new_price = max(0.01, round(old_price * (1 + price_change_pct), 2))
                
                await conn.execute("UPDATE stocks SET price = $1 WHERE id = $2", new_price, stock['id'])
                
                emoji = "📈" if new_price > old_price else "📉" if new_price < old_price else "➡️"
                embed.add_field(
                    name=f"{emoji} Stock Price Update",
                    value=f"${old_price:.2f} → **${new_price:.2f}** ({price_change_pct * 100:+.2f}%)",
                    inline=False
                )
        
        embed.add_field(
            name="🏦 Company Balance",
            value=f"Previous: ${old_balance:,.2f}\n**New:** ${new_balance:,.2f}",
            inline=False
        )
        
        # ChatGPT commentary
        messages = [{
            "role": "system",
            "content": "You are Francesca (Franky), a friendly bank teller. Provide a brief, encouraging comment on the financial report results in 1-2 sentences."
        }, {
            "role": "user",
            "content": f"The report shows a company net profit of ${net_profit_to_company:,.2f} and CEO take-home of ${ceo_salary_after_tax:,.2f}. Give a brief congratulatory or encouraging message."
        }]
        
        commentary = await self.call_chatgpt(messages)
        if commentary:
            embed.set_footer(text=f"💬 Franky: {commentary}")
        
        await message.reply(embed=embed)
    
    @commands.hybrid_command(name="cancel_report")
    async def cancel_report(self, ctx):
        """Cancel your active financial report session"""
        if ctx.author.id in self.active_sessions:
            del self.active_sessions[ctx.author.id]
            await ctx.send("✅ Report session cancelled.")
        else:
            await ctx.send("ℹ️ You don't have an active report session.")
    
    @commands.hybrid_command(name="report_status")
    async def report_status(self, ctx):
        """Check if you have an active financial report session"""
        if ctx.author.id not in self.active_sessions:
            await ctx.send("ℹ️ You don't have an active report session.")
            return
        
        session = self.active_sessions[ctx.author.id]
        channel = self.bot.get_channel(session["channel_id"])
        
        embed = discord.Embed(title="📊 Active Report Session", color=discord.Color.blue())
        
        if session["step"] == "company_name":
            embed.add_field(name="Status", value="Waiting for company name", inline=False)
        elif session["step"] == "gross_expenses":
            embed.add_field(name="Company", value=session["company_name"], inline=False)
            embed.add_field(name="Status", value="Waiting for gross expenses percentage", inline=False)
        elif session["step"] == "items":
            embed.add_field(name="Company", value=session["company_name"], inline=False)
            embed.add_field(name="Gross Expenses", value=f"{session['gross_expenses_percent']:.1f}%", inline=True)
            embed.add_field(name="Items Added", value=str(len(session["items"])), inline=True)
            embed.add_field(name="Status", value="Adding items (type 'done' when finished)", inline=False)
        
        embed.add_field(name="Channel", value=channel.mention if channel else "Unknown", inline=False)
        embed.set_footer(text="Use /cancel-report to cancel")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="view_reports")
    async def view_reports(self, ctx, company_name: str):
        """View financial reports for your company"""
        async with self.bot.db.acquire() as conn:
            company = await conn.fetchrow(
                "SELECT id FROM companies WHERE owner_id = $1 AND name = $2",
                ctx.author.id, company_name
            )
            
            if not company:
                await ctx.send("❌ Company not found!")
                return
            
            reports = await conn.fetch(
                """SELECT items_sold, gross_revenue, gross_profit, corporate_tax, 
                   ceo_salary, personal_tax, net_profit, reported_at 
                   FROM reports WHERE company_id = $1 
                   ORDER BY reported_at DESC LIMIT 5""",
                company['id']
            )
        
        if not reports:
            await ctx.send("📋 No reports filed yet!")
            return
        
        embed = discord.Embed(title=f"📊 Recent Reports: {company_name}", color=discord.Color.blue())
        
        for idx, row in enumerate(reports, 1):
            items = json.loads(row['items_sold'])
            items_summary = ", ".join([f"{i['name']} (🎲{i['dice']})" for i in items[:3]])
            if len(items) > 3:
                items_summary += f" +{len(items) - 3} more"
            
            embed.add_field(
                name=f"Report #{idx} - {row['reported_at'].strftime('%Y-%m-%d')}",
                value=f"Items: {items_summary}\n"
                      f"Revenue: ${float(row['gross_revenue']):,.2f} | Gross: ${float(row['gross_profit']):,.2f}\n"
                      f"Corp Tax: ${float(row['corporate_tax']):,.2f} | CEO: ${float(row['ceo_salary']):,.2f}\n"
                      f"Net: ${float(row['net_profit']):,.2f}",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="view_report_cooldown")
    async def view_report_cooldown(self, ctx):
        """View the current report cooldown for your companies"""
        embed = discord.Embed(
            title="⏰ Report Cooldown Status",
            description=f"Cooldown: **{self.report_cooldown_hours} hours** per company",
            color=discord.Color.blue()
        )
        
        async with self.bot.db.acquire() as conn:
            companies = await conn.fetch(
                "SELECT id, name FROM companies WHERE owner_id = $1 ORDER BY name",
                ctx.author.id
            )
            
            if not companies:
                embed.add_field(name="No Companies", value="You don't own any companies yet!", inline=False)
            else:
                for company in companies:
                    last_report = await conn.fetchrow(
                        """SELECT reported_at FROM reports 
                           WHERE company_id = $1 
                           ORDER BY reported_at DESC 
                           LIMIT 1""",
                        company['id']
                    )
                    
                    if last_report:
                        next_available = last_report['reported_at'] + timedelta(hours=self.report_cooldown_hours)
                        time_remaining = next_available - datetime.now()
                        
                        if time_remaining.total_seconds() > 0:
                            hours = int(time_remaining.total_seconds() // 3600)
                            minutes = int((time_remaining.total_seconds() % 3600) // 60)
                            status = f"⏳ **{hours}h {minutes}m**"
                        else:
                            status = "✅ **Available now!**"
                    else:
                        status = "✅ **Available now!**"
                    
                    embed.add_field(name=company['name'], value=status, inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="set_report_cooldown")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def set_report_cooldown(self, ctx, hours: int):
        """Set report cooldown (Admin/Owner only)"""
        if hours < 0 or hours > 168:
            await ctx.send("❌ Must be between 0 and 168 hours!")
            return
        
        old = self.report_cooldown_hours
        self.report_cooldown_hours = hours
        
        await ctx.send(f"✅ Report cooldown: {old}h → **{hours}h**")
    
    @commands.hybrid_command(name="bypass_cooldown")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def bypass_cooldown(self, ctx, user: discord.User, company_name: str):
        """Reset report cooldown (Admin/Owner only)"""
        async with self.bot.db.acquire() as conn:
            company = await conn.fetchrow(
                "SELECT id FROM companies WHERE owner_id = $1 AND name = $2",
                user.id, company_name
            )
            
            if not company:
                await ctx.send(f"❌ {user.mention} doesn't own **{company_name}**!")
                return
            
            last_report = await conn.fetchrow(
                "SELECT id FROM reports WHERE company_id = $1 ORDER BY reported_at DESC LIMIT 1",
                company['id']
            )
            
            if not last_report:
                await ctx.send(f"ℹ️ **{company_name}** hasn't filed any reports!")
                return
            
            old_time = datetime.now() - timedelta(hours=self.report_cooldown_hours + 1)
            await conn.execute("UPDATE reports SET reported_at = $1 WHERE id = $2", old_time, last_report['id'])
        
        await ctx.send(f"✅ {user.mention}'s **{company_name}** cooldown bypassed!")


async def setup(bot):
    await bot.add_cog(ReportFiling(bot))

import discord
from discord.ext import commands
import os
import aiohttp
import random
import json
from typing import Optional

class FinancialReports(commands.Cog):
    """ChatGPT-assisted financial reports with dice rolls"""
    
    def __init__(self, bot):
        self.bot = bot
        self.api_key = os.getenv("OPENAI_API_KEY")
        # Default to gpt-4o-mini if not specified
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        
        # Tax rate (can be adjusted by admins)
        self.tax_rate = 0.25  # 25% default
        
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
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle report filing conversation and trigger phrases"""
        if message.author.bot:
            return
        
        content_lower = message.content.strip().lower()
        user_id = message.author.id
        
        # Check if user has an active session
        has_active_session = user_id in self.active_sessions
        
        # If they have an active session, handle it
        if has_active_session:
            session = self.active_sessions[user_id]
            
            # IMPORTANT: Only respond in the channel where the session started
            if message.channel.id != session["channel_id"]:
                return  # Ignore messages in other channels
            
            # Don't process commands
            if message.content.startswith("!"):
                return
            
            # Step 1: Get company name
            if session["step"] == "company_name":
                company_name = message.content.strip()
                
                # Check if company exists
                async with self.bot.db.acquire() as conn:
                    company = await conn.fetchrow(
                        "SELECT id FROM companies WHERE owner_id = $1 AND name = $2",
                        user_id, company_name
                    )
                    
                    if not company:
                        # Create company
                        await conn.execute(
                            "INSERT INTO companies (name, owner_id) VALUES ($1, $2)",
                            company_name, user_id
                        )
                        await message.reply(f"✅ Company **{company_name}** has been registered!")
                
                session["company_name"] = company_name
                session["step"] = "items"
                
                await message.reply(
                    "**Now, let's add your products/items:**\n"
                    "Format: `Item Name | Price per unit`\n"
                    "Example: `Widget | 50` or `Premium Service | 120`\n\n"
                    "Type `done` when you've added all items."
                )
            
            # Step 2: Collect items
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
                    # Parse item
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
            
            return  # Exit after handling active session
        
        # If no active session, check for trigger phrases to start filing
        # Trigger phrases that indicate user wants to file a report
        file_triggers = [
            "file report", "file a report", "make a report", "create a report",
            "submit report", "submit a report", "i want to file", "id like to file",
            "file my report", "start a report", "new report"
        ]
        
        # Check if message contains any trigger phrase
        should_start_filing = any(trigger in content_lower for trigger in file_triggers)
        
        if should_start_filing:
            # Don't start if it's a command
            if message.content.startswith("!"):
                return
            
            # Check if in responder channel - if so, let ChatGPT handle the greeting naturally
            chatgpt_cog = self.bot.get_cog("ChatGPTResponder")
            in_responder_channel = False
            
            if chatgpt_cog:
                if message.channel.id == chatgpt_cog.responder_channel_id:
                    in_responder_channel = True
                elif isinstance(message.channel, discord.Thread) and message.channel.parent_id == chatgpt_cog.forum_channel_id:
                    in_responder_channel = True
            
            # Initialize session
            self.active_sessions[user_id] = {
                "step": "company_name",
                "company_name": None,
                "items": [],
                "channel_id": message.channel.id
            }
            
            # Only send manual greeting if NOT in a responder channel
            if not in_responder_channel:
                await message.reply(
                    "*smiles warmly* Of course! I'd be happy to help you file your financial report!\n\n"
                    "**Please provide your company name:**"
                )
    
    async def process_report(self, message: discord.Message, session: dict):
        """Process the financial report with dice rolls"""
        company_name = session["company_name"]
        items = session["items"]
        
        # Roll dice for each item
        results = []
        total_gross = 0
        
        embed = discord.Embed(
            title=f"🎲 Financial Report: {company_name}",
            description="*Rolling the dice for sales...*",
            color=discord.Color.blue()
        )
        
        for item in items:
            dice_roll = random.randint(1, 100)
            gross_profit = item["price"] * dice_roll
            total_gross += gross_profit
            
            results.append({
                "name": item["name"],
                "price": item["price"],
                "dice": dice_roll,
                "profit": gross_profit
            })
            
            embed.add_field(
                name=f"🎲 {item['name']}",
                value=f"Price: ${item['price']:.2f}\nDice Roll: **{dice_roll}**/100\nGross: **${gross_profit:,.2f}**",
                inline=True
            )
        
        # Calculate tax
        tax = total_gross * self.tax_rate
        net_profit = total_gross - tax
        
        embed.add_field(
            name="📊 Summary",
            value=f"**Gross Profit:** ${total_gross:,.2f}\n**Tax ({self.tax_rate * 100:.1f}%):** ${tax:,.2f}\n**Net Profit:** ${net_profit:,.2f}",
            inline=False
        )
        
        # Update company balance
        async with self.bot.db.acquire() as conn:
            company = await conn.fetchrow(
                "SELECT id, balance FROM companies WHERE name = $1 AND owner_id = $2",
                company_name, message.author.id
            )
            company_id = company['id']
            old_balance = float(company['balance'])
            new_balance = old_balance + net_profit
            
            await conn.execute(
                "UPDATE companies SET balance = $1 WHERE id = $2",
                new_balance, company_id
            )
            
            # Save report
            items_json = json.dumps(results)
            await conn.execute(
                "INSERT INTO reports (company_id, items_sold, gross_profit, net_profit) VALUES ($1, $2, $3, $4)",
                company_id, items_json, total_gross, net_profit
            )
        
        embed.add_field(
            name="🏦 Company Balance",
            value=f"Previous: ${old_balance:,.2f}\n**New Balance:** ${new_balance:,.2f}",
            inline=False
        )
        
        # ChatGPT commentary
        messages = [{
            "role": "system",
            "content": "You are Francesca (Franky), a friendly bank teller. Provide a brief, encouraging comment on the financial report results in 1-2 sentences."
        }, {
            "role": "user",
            "content": f"The report shows a net profit of ${net_profit:,.2f}. Give a brief congratulatory or encouraging message."
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
        
        embed = discord.Embed(
            title="📊 Active Report Session",
            color=discord.Color.blue()
        )
        
        if session["step"] == "company_name":
            embed.add_field(name="Status", value="Waiting for company name", inline=False)
        elif session["step"] == "items":
            embed.add_field(name="Company", value=session["company_name"], inline=False)
            embed.add_field(name="Items Added", value=str(len(session["items"])), inline=True)
            embed.add_field(name="Status", value="Adding items (type 'done' when finished)", inline=False)
        
        embed.add_field(name="Channel", value=channel.mention if channel else "Unknown", inline=False)
        embed.set_footer(text="Use !cancel_report to cancel this session")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="company_balance")
    async def company_balance(self, ctx, *, company_name: str = None):
        """Check your company's balance"""
        async with self.bot.db.acquire() as conn:
            if company_name:
                companies = await conn.fetch(
                    "SELECT name, balance FROM companies WHERE owner_id = $1 AND name = $2",
                    ctx.author.id, company_name
                )
            else:
                companies = await conn.fetch(
                    "SELECT name, balance FROM companies WHERE owner_id = $1",
                    ctx.author.id
                )
        
        if not companies:
            await ctx.send("❌ You don't own any companies!")
            return
        
        embed = discord.Embed(
            title="🏢 Your Companies",
            color=discord.Color.gold()
        )
        
        for row in companies:
            name = row['name']
            balance = float(row['balance'])
            embed.add_field(
                name=name,
                value=f"Balance: **${balance:,.2f}**",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="set_tax")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def set_tax(self, ctx, tax_percentage: float):
        """Set the tax rate for financial reports (Admin/Owner only)
        
        Usage: !set_tax 20 (for 20%)
        """
        if tax_percentage < 0 or tax_percentage > 100:
            await ctx.send("❌ Tax percentage must be between 0 and 100!")
            return
        
        old_rate = self.tax_rate * 100
        self.tax_rate = tax_percentage / 100
        
        embed = discord.Embed(
            title="🏛️ Tax Rate Updated",
            description=f"The corporate tax rate has been adjusted!",
            color=discord.Color.blue()
        )
        embed.add_field(name="Previous Rate", value=f"{old_rate:.1f}%", inline=True)
        embed.add_field(name="New Rate", value=f"{tax_percentage:.1f}%", inline=True)
        embed.set_footer(text="This will apply to all new financial reports")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="view_tax")
    async def view_tax(self, ctx):
        """View the current tax rate"""
        embed = discord.Embed(
            title="🏛️ Current Tax Rate",
            description=f"**{self.tax_rate * 100:.1f}%**",
            color=discord.Color.blue()
        )
        embed.set_footer(text="This rate applies to all financial reports")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="view_reports")
    async def view_reports(self, ctx, *, company_name: str):
        """View financial reports for your company"""
        async with self.bot.db.acquire() as conn:
            company = await conn.fetchrow(
                "SELECT id FROM companies WHERE owner_id = $1 AND name = $2",
                ctx.author.id, company_name
            )
            
            if not company:
                await ctx.send("❌ Company not found!")
                return
            
            company_id = company['id']
            
            reports = await conn.fetch(
                "SELECT items_sold, gross_profit, net_profit, reported_at FROM reports WHERE company_id = $1 ORDER BY reported_at DESC LIMIT 5",
                company_id
            )
        
        if not reports:
            await ctx.send("📋 No reports filed yet!")
            return
        
        embed = discord.Embed(
            title=f"📊 Recent Reports: {company_name}",
            color=discord.Color.blue()
        )
        
        for idx, row in enumerate(reports, 1):
            items_json = row['items_sold']
            gross = float(row['gross_profit'])
            net = float(row['net_profit'])
            timestamp = row['reported_at']
            
            items = json.loads(items_json)
            items_summary = ", ".join([f"{item['name']} (🎲{item['dice']})" for item in items[:3]])
            if len(items) > 3:
                items_summary += f" +{len(items) - 3} more"
            
            embed.add_field(
                name=f"Report #{idx}",
                value=f"Items: {items_summary}\nGross: ${gross:,.2f}\nNet: ${net:,.2f}\n{timestamp}",
                inline=False
            )
        
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(FinancialReports(bot))

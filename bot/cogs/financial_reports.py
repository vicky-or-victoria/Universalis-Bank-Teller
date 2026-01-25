import discord
from discord.ext import commands
import os
import aiohttp
import random
import json
import asyncio
from typing import Optional
from datetime import datetime, timedelta

class FinancialReports(commands.Cog):
    """ChatGPT-assisted financial reports with dice rolls"""
    
    def __init__(self, bot):
        self.bot = bot
        self.api_key = os.getenv("OPENAI_API_KEY")
        # Default to gpt-4o-mini if not specified
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        
        # Tax rate (can be adjusted by admins)
        self.tax_rate = 0.25  # 25% default
        
        # Report cooldown in hours (can be adjusted by admins)
        self.report_cooldown_hours = 48  # 48 hours (2 days) default
        
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
        """Start filing a financial report
        
        Usage: ub!file_report
        """
        # Check for active session
        if ctx.author.id in self.active_sessions:
            session = self.active_sessions[ctx.author.id]
            channel = self.bot.get_channel(session["channel_id"])
            channel_mention = channel.mention if channel else "another channel"
            await ctx.send(f"⚠️ You already have an active report session in {channel_mention}! Use ub!cancel_report to cancel it first.")
            return
        
        # Initialize session - we'll check cooldown after they select a company
        self.active_sessions[ctx.author.id] = {
            "step": "company_name",
            "company_name": None,
            "items": [],
            "channel_id": ctx.channel.id
        }
        
        await ctx.send(
            "*smiles warmly* Of course! I'd be happy to help you file your financial report!\n\n"
            "**Please provide your company name:**"
        )
    
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
            if message.content.startswith("ub!"):
                return
            
            # Step 1: Get company name
            if session["step"] == "company_name":
                company_name = message.content.strip()
                
                # Check if company exists and get its ID
                async with self.bot.db.acquire() as conn:
                    company = await conn.fetchrow(
                        "SELECT id FROM companies WHERE owner_id = $1 AND name = $2",
                        user_id, company_name
                    )
                    
                    if not company:
                        await message.reply(f"❌ You don't own a company named **{company_name}**! Create it first with `ub!register_company \"{company_name}\"`")
                        del self.active_sessions[user_id]
                        return
                    
                    company_id = company['id']
                    
                    # NOW check cooldown for THIS specific company
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
                            embed.set_footer(text=f"Total Company Balance: ${total_balance:,.2f}")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="set_report_cooldown")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def set_report_cooldown(self, ctx, hours: int):
        """Set the cooldown period between financial reports (Admin/Owner only)
        
        Usage: ub!set_report_cooldown 48 (for 48 hours)
        """
        if hours < 0:
            await ctx.send("❌ Cooldown hours must be 0 or greater!")
            return
        
        if hours > 168:  # 1 week
            await ctx.send("❌ Cooldown cannot exceed 168 hours (1 week)!")
            return
        
        old_cooldown = self.report_cooldown_hours
        self.report_cooldown_hours = hours
        
        embed = discord.Embed(
            title="⏰ Report Cooldown Updated",
            description=f"Each company can now file reports every **{hours} hours**",
            color=discord.Color.blue()
        )
        embed.add_field(name="Previous Cooldown", value=f"{old_cooldown} hours", inline=True)
        embed.add_field(name="New Cooldown", value=f"{hours} hours", inline=True)
        
        if hours == 0:
            embed.add_field(name="⚠️ Warning", value="Cooldown is disabled! Companies can file unlimited reports.", inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="view_report_cooldown")
    async def view_report_cooldown(self, ctx):
        """View the current report cooldown period for each of your companies"""
        embed = discord.Embed(
            title="⏰ Report Cooldown Status",
            description=f"Cooldown period: **{self.report_cooldown_hours} hours** ({self.report_cooldown_hours / 24:.1f} days) per company",
            color=discord.Color.blue()
        )
        
        if self.report_cooldown_hours == 0:
            embed.add_field(name="Status", value="⚠️ Cooldown is disabled", inline=False)
        
        # Get all user's companies and their cooldown status
        async with self.bot.db.acquire() as conn:
            companies = await conn.fetch(
                "SELECT id, name FROM companies WHERE owner_id = $1 ORDER BY name",
                ctx.author.id
            )
            
            if not companies:
                embed.add_field(name="No Companies", value="You don't own any companies yet!", inline=False)
            else:
                for company in companies:
                    company_id = company['id']
                    company_name = company['name']
                    
                    last_report = await conn.fetchrow(
                        """SELECT reported_at FROM reports 
                           WHERE company_id = $1 
                           ORDER BY reported_at DESC 
                           LIMIT 1""",
                        company_id
                    )
                    
                    if last_report:
                        last_report_time = last_report['reported_at']
                        next_available = last_report_time + timedelta(hours=self.report_cooldown_hours)
                        time_remaining = next_available - datetime.now()
                        
                        if time_remaining.total_seconds() > 0:
                            hours = int(time_remaining.total_seconds() // 3600)
                            minutes = int((time_remaining.total_seconds() % 3600) // 60)
                            status = f"⏳ Available in **{hours}h {minutes}m**"
                        else:
                            status = "✅ **Available now!**"
                    else:
                        status = "✅ **Available now!** (Never filed)"
                    
                    embed.add_field(
                        name=company_name,
                        value=status,
                        inline=False
                    )
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="bypass_cooldown")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def bypass_cooldown(self, ctx, user: discord.User, *, company_name: str):
        """Reset a company's report cooldown (Admin/Owner only)
        
        Usage: ub!bypass_cooldown @user "Company Name"
        """
        async with self.bot.db.acquire() as conn:
            # Get the company
            company = await conn.fetchrow(
                "SELECT id, name FROM companies WHERE owner_id = $1 AND name = $2",
                user.id, company_name
            )
            
            if not company:
                await ctx.send(f"❌ {user.mention} doesn't own a company named **{company_name}**!")
                return
            
            company_id = company['id']
            
            # Get the company's most recent report
            last_report = await conn.fetchrow(
                """SELECT id, reported_at FROM reports 
                   WHERE company_id = $1 
                   ORDER BY reported_at DESC 
                   LIMIT 1""",
                company_id
            )
            
            if not last_report:
                await ctx.send(f"ℹ️ **{company_name}** hasn't filed any reports yet!")
                return
            
            # Update the timestamp to be old enough to bypass cooldown
            old_timestamp = datetime.now() - timedelta(hours=self.report_cooldown_hours + 1)
            
            await conn.execute(
                "UPDATE reports SET reported_at = $1 WHERE id = $2",
                old_timestamp, last_report['id']
            )
        
        embed = discord.Embed(
            title="✅ Cooldown Bypassed",
            description=f"{user.mention}'s company **{company_name}** can now file a report immediately!",
            color=discord.Color.green()
        )
        embed.add_field(name="Previous Report", value=last_report['reported_at'].strftime('%Y-%m-%d %H:%M UTC'), inline=True)
        
        await ctx.send(embed=embed)
        
        # Notify the user
        try:
            notify_embed = discord.Embed(
                title="⏰ Report Cooldown Reset",
                description=f"An administrator has reset the report cooldown for your company **{company_name}** in {ctx.guild.name}. You can file a report now!",
                color=discord.Color.green()
            )
            await user.send(embed=notify_embed)
        except:
            pass  # DMs disabled


async def setup(bot):
    await bot.add_cog(FinancialReports(bot))_footer(text="Try a different company or wait for the cooldown to expire")
                            
                            await message.reply(embed=embed)
                            del self.active_sessions[user_id]
                            return
                
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
            if message.content.startswith("ub!"):
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
        embed.set_footer(text="Use ub!cancel_report to cancel this session")
        
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
        
        Usage: ub!set_tax 20 (for 20%)
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
    
    @commands.hybrid_command(name="disband_company")
    async def disband_company(self, ctx, *, company_name: str):
        """Disband your company (WARNING: This is permanent!)
        
        Usage: ub!disband_company "Company Name"
        """
        async with self.bot.db.acquire() as conn:
            # Check if user owns this company
            company = await conn.fetchrow(
                "SELECT id, balance, is_public FROM companies WHERE owner_id = $1 AND name = $2",
                ctx.author.id, company_name
            )
            
            if not company:
                await ctx.send("❌ You don't own a company with that name!")
                return
            
            company_id = company['id']
            balance = float(company['balance'])
            is_public = company['is_public']
            
            # Check if company is public
            if is_public:
                await ctx.send("❌ You cannot disband a public company! Use `ub!delist_company` first (Admin only).")
                return
            
            # Confirmation embed
            confirm_embed = discord.Embed(
                title="⚠️ Confirm Company Disbandment",
                description=f"Are you sure you want to disband **{company_name}**?",
                color=discord.Color.orange()
            )
            confirm_embed.add_field(name="Company Balance", value=f"${balance:,.2f} (will be lost)", inline=False)
            confirm_embed.add_field(name="Reports", value="All financial reports will be deleted", inline=False)
            confirm_embed.set_footer(text="React with ✅ to confirm or ❌ to cancel (60 seconds)")
            
            msg = await ctx.send(embed=confirm_embed)
            await msg.add_reaction("✅")
            await msg.add_reaction("❌")
            
            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == msg.id
            
            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=60.0, check=check)
                
                if str(reaction.emoji) == "❌":
                    await ctx.send("❌ Company disbandment cancelled.")
                    return
                
                # Delete reports first (foreign key constraint)
                await conn.execute("DELETE FROM reports WHERE company_id = $1", company_id)
                
                # Delete company
                await conn.execute("DELETE FROM companies WHERE id = $1", company_id)
                
                success_embed = discord.Embed(
                    title="🗑️ Company Disbanded",
                    description=f"**{company_name}** has been permanently disbanded.",
                    color=discord.Color.red()
                )
                success_embed.add_field(name="Balance Lost", value=f"${balance:,.2f}", inline=True)
                
                await ctx.send(embed=success_embed)
                
            except asyncio.TimeoutError:
                await ctx.send("⏱️ Confirmation timed out. Company disbandment cancelled.")
            except Exception as e:
                await ctx.send(f"❌ Error disbanding company: {e}")
    
    @commands.hybrid_command(name="force_disband")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def force_disband(self, ctx, user: discord.User, *, company_name: str):
        """Forcefully disband a player's company (Admin/Owner only)
        
        Usage: ub!force_disband @user "Company Name"
        """
        async with self.bot.db.acquire() as conn:
            # Check if company exists
            company = await conn.fetchrow(
                "SELECT id, balance, is_public FROM companies WHERE owner_id = $1 AND name = $2",
                user.id, company_name
            )
            
            if not company:
                await ctx.send(f"❌ {user.mention} doesn't own a company named **{company_name}**!")
                return
            
            company_id = company['id']
            balance = float(company['balance'])
            is_public = company['is_public']
            
            # If public, delist first
            if is_public:
                # Get stock info
                stock = await conn.fetchrow(
                    "SELECT id, ticker FROM stocks WHERE company_id = $1",
                    company_id
                )
                
                if stock:
                    stock_id = stock['id']
                    ticker = stock['ticker']
                    
                    # Delete holdings
                    await conn.execute("DELETE FROM holdings WHERE stock_id = $1", stock_id)
                    
                    # Delete stock
                    await conn.execute("DELETE FROM stocks WHERE id = $1", stock_id)
                    
                    await ctx.send(f"📉 Delisted **{ticker}** before disbanding...")
            
            # Delete reports
            await conn.execute("DELETE FROM reports WHERE company_id = $1", company_id)
            
            # Delete company
            await conn.execute("DELETE FROM companies WHERE id = $1", company_id)
        
        embed = discord.Embed(
            title="🔨 Company Forcefully Disbanded",
            description=f"**{company_name}** (owned by {user.mention}) has been disbanded by an administrator.",
            color=discord.Color.red()
        )
        embed.add_field(name="Balance Lost", value=f"${balance:,.2f}", inline=True)
        embed.add_field(name="Was Public", value="Yes" if is_public else "No", inline=True)
        
        await ctx.send(embed=embed)
        
        # Notify the user
        try:
            notify_embed = discord.Embed(
                title="⚠️ Company Disbanded",
                description=f"Your company **{company_name}** has been disbanded by an administrator in {ctx.guild.name}.",
                color=discord.Color.orange()
            )
            notify_embed.add_field(name="Balance Lost", value=f"${balance:,.2f}", inline=True)
            await user.send(embed=notify_embed)
        except:
            pass  # DMs disabled
    
    @commands.hybrid_command(name="register_company")
    async def register_company(self, ctx, *, company_name: str):
        """Register a new company
        
        Usage: ub!register_company "My Company Name"
        """
        # Get max companies from StockMarket cog
        stock_market_cog = self.bot.get_cog("StockMarket")
        max_companies = stock_market_cog.max_companies if stock_market_cog else 3
        
        async with self.bot.db.acquire() as conn:
            # Check how many companies user owns
            company_count = await conn.fetchval(
                "SELECT COUNT(*) FROM companies WHERE owner_id = $1",
                ctx.author.id
            )
            
            if company_count >= max_companies:
                await ctx.send(f"❌ You've reached the maximum of **{max_companies}** companies! Disband one to create another.")
                return
            
            # Check if company name already exists
            existing = await conn.fetchrow(
                "SELECT id FROM companies WHERE name = $1",
                company_name
            )
            
            if existing:
                await ctx.send(f"❌ A company named **{company_name}** already exists!")
                return
            
            # Create company
            await conn.execute(
                "INSERT INTO companies (name, owner_id) VALUES ($1, $2)",
                company_name, ctx.author.id
            )
        
        embed = discord.Embed(
            title="🏢 Company Registered!",
            description=f"**{company_name}** has been successfully registered!",
            color=discord.Color.green()
        )
        embed.add_field(name="Owner", value=ctx.author.mention, inline=True)
        embed.add_field(name="Starting Balance", value="$0.00", inline=True)
        embed.add_field(name="Companies Owned", value=f"{company_count + 1}/{max_companies}", inline=True)
        embed.set_footer(text="Use ub!file_report to start earning money!")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="my_companies")
    async def my_companies(self, ctx, user: discord.User = None):
        """View detailed information about your companies (or another user's)
        
        Usage: ub!my_companies [@user]
        """
        target_user = user or ctx.author
        
        async with self.bot.db.acquire() as conn:
            companies = await conn.fetch(
                "SELECT name, balance, is_public, created_at FROM companies WHERE owner_id = $1 ORDER BY created_at DESC",
                target_user.id
            )
        
        if not companies:
            if target_user == ctx.author:
                await ctx.send("❌ You don't own any companies! Use `ub!register_company` to create one.")
            else:
                await ctx.send(f"❌ {target_user.mention} doesn't own any companies.")
            return
        
        # Get max companies
        stock_market_cog = self.bot.get_cog("StockMarket")
        max_companies = stock_market_cog.max_companies if stock_market_cog else 3
        
        if target_user == ctx.author:
            title = f"🏢 Your Companies ({len(companies)}/{max_companies})"
        else:
            title = f"🏢 {target_user.display_name}'s Companies ({len(companies)}/{max_companies})"
        
        embed = discord.Embed(
            title=title,
            color=discord.Color.blue()
        )
        
        total_balance = 0
        
        for company in companies:
            name = company['name']
            balance = float(company['balance'])
            is_public = company['is_public']
            created_at = company['created_at']
            
            total_balance += balance
            
            status = "📈 Public" if is_public else "🔒 Private"
            
            # Get stock info if public
            stock_info = ""
            if is_public:
                async with self.bot.db.acquire() as conn:
                    stock = await conn.fetchrow(
                        "SELECT ticker, price FROM stocks s JOIN companies c ON s.company_id = c.id WHERE c.name = $1",
                        name
                    )
                    if stock:
                        ticker = stock['ticker']
                        price = float(stock['price'])
                        stock_info = f"\nTicker: **{ticker}** | Stock Price: **${price:,.2f}**"
            
            embed.add_field(
                name=f"{status} {name}",
                value=f"Balance: **${balance:,.2f}**{stock_info}\nFounded: {created_at.strftime('%Y-%m-%d')}",
                inline=False
            )
        
        embed.set

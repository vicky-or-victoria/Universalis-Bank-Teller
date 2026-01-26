import discord
from discord.ext import commands
import os
import aiohttp
import random
import json
from typing import Optional
from datetime import datetime, timedelta
from cogs.company_events import CompanyEvents

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
        
        # Pagination for viewing reports
        self.report_views = {}
    
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
            
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Auto-respond to all messages in the responder channel or forum threads"""
        if message.author.bot:
            return
        
        # Check if in responder channel or forum thread
        in_responder_channel = message.channel.id == self.responder_channel_id
        in_forum_thread = False
        if isinstance(message.channel, discord.Thread):
            if message.channel.parent_id == self.forum_channel_id:
                in_forum_thread = True
        
        if not (in_responder_channel or in_forum_thread):
            return
        
        # CHECK 1: Don't respond to control phrases
        content_lower = message.content.strip().lower()
        if any(phrase in content_lower for phrase in [
            "thanks francesca", "thank you francesca",
            "hey francesca", "hi francesca", "hello francesca",
            "close francesca"
        ]):
            return
        
        # CHECK 2: Check if user wants to file a report
        # IMPORTANT: We need to check this BEFORE creating the session
        # to avoid the trigger message being processed as input
        file_triggers = [
            "file report", "file a report", "make a report", "create a report",
            "submit report", "submit a report", "i want to file", "id like to file",
            "i'd like to file", "file my report", "start a report", "new report",
            "i wanna file", "want to file a report"
        ]
        
        # Check if this message is a filing trigger
        is_filing_trigger = any(trigger in content_lower for trigger in file_triggers)
        
        if is_filing_trigger:
            report_cog = self.bot.get_cog("ReportFiling")
            if report_cog:
                # Check if user already has an active session
                if message.author.id in report_cog.active_sessions:
                    session = report_cog.active_sessions[message.author.id]
                    channel = self.bot.get_channel(session["channel_id"])
                    channel_mention = channel.mention if channel else "another channel"
                    await message.reply(
                        f"⚠️ You already have an active report session in {channel_mention}! "
                        f"Use `/cancel-report` to cancel it first."
                    )
                    return
                
                # Create the session
                report_cog.active_sessions[message.author.id] = {
                    "step": "company_name",
                    "company_name": None,
                    "gross_expenses_percent": None,
                    "items": [],
                    "channel_id": message.channel.id
                }
                
                print(f"[CHATGPT RESPONDER] Started report session for {message.author}")
                
                # Send the initial prompt
                await message.reply(
                    "*smiles warmly* Of course! I'd be happy to help you file your financial report!\n\n"
                    "**Please provide your company name:**"
                )
                
                # CRITICAL: Return immediately so this trigger message is NOT processed further
                # This prevents "i want to file a report" from being treated as the company name
                return
        
        # CHECK 3: DON'T respond if user is filing a report
        # The report filing system handles its own input - Francesca should stay silent
        report_cog = self.bot.get_cog("ReportFiling")
        if report_cog and message.author.id in report_cog.active_sessions:
            session = report_cog.active_sessions[message.author.id]
            if message.channel.id == session.get("channel_id"):
                # User is actively filing - let the report system handle it
                # Francesca should NOT respond during the filing process
                print(f"[CHATGPT RESPONDER] User {message.author} is filing, staying silent")
                return
        
        # CHECK 4: Don't respond if paused in this channel
        francesca_control_cog = self.bot.get_cog("FrancescaControl")
        if francesca_control_cog and francesca_control_cog.is_channel_paused(message.channel.id):
            return
        
        # Don't respond to commands
        if message.content.startswith("ub!") or message.content.startswith("/"):
            return
        
        async with message.channel.typing():
            messages = self.get_conversation_history(message.author.id)
            self.add_to_conversation(message.author.id, "user", message.content)
            messages = self.get_conversation_history(message.author.id)
            
            response = await self.call_chatgpt(messages)
            
            if response:
                self.add_to_conversation(message.author.id, "assistant", response)
                
                if len(response) > 2000:
                    chunks = [response[i:i+2000] for i in range(0, len(response), 2000)]
                    for chunk in chunks:
                        await message.reply(chunk)
                else:
                    await message.reply(response)
                    
        # Step 1: Get company name
        if session["step"] == "company_name":
            company_name = message.content.strip()
            
            async with self.bot.db.acquire() as conn:
                company = await conn.fetchrow(
                    "SELECT id, ceo_salary_percent FROM companies WHERE owner_id = $1 AND name = $2",
                    user_id, company_name
                )
                
                if not company:
                    await message.reply(f"❌ You don't own a company named **{company_name}**!")
                    del self.active_sessions[user_id]
                    return
                
                # Check cooldown
                last_report = await conn.fetchrow(
                    "SELECT reported_at FROM reports WHERE company_id = $1 ORDER BY reported_at DESC LIMIT 1",
                    company['id']
                )
                
                if last_report:
                    time_since = datetime.now() - last_report['reported_at']
                    cooldown_hours = self.report_cooldown_hours
                    
                    if time_since < timedelta(hours=cooldown_hours):
                        remaining = timedelta(hours=cooldown_hours) - time_since
                        hours = int(remaining.total_seconds() // 3600)
                        minutes = int((remaining.total_seconds() % 3600) // 60)
                        
                        await message.reply(
                            f"⏰ **{company_name}** is on cooldown!\n"
                            f"Time remaining: **{hours}h {minutes}m**"
                        )
                        del self.active_sessions[user_id]
                        return
            
            session["company_name"] = company_name
            session["company_id"] = company['id']
            session["ceo_salary_percent"] = float(company['ceo_salary_percent'])
            session["step"] = "expenses"
            
            await message.reply(
                f"Great! Filing report for **{company_name}**.\n\n"
                "**What percentage of revenue goes to expenses?**\n"
                "_(Enter a number between 0-100, e.g., 35 for 35%)_"
            )
        
        # Step 2: Get expense percentage
        elif session["step"] == "expenses":
            try:
                expenses = float(message.content.strip())
            except ValueError:
                await message.reply("⚠️ Please enter a valid number!")
                return
            
            if expenses < 0 or expenses > 100:
                await message.reply("⚠️ Percentage must be between 0 and 100!")
                return
            
            session["gross_expenses_percent"] = expenses
            session["step"] = "items"
            
            await message.reply(
                f"**Expense percentage set to {expenses}%**\n\n"
                "Now, let's add your products/services!\n\n"
                "**Format:** `Product Name | Price`\n"
                "**Example:** `Premium Widget | 299.99`\n\n"
                "Add as many items as you want, then type **`done`** when finished."
            )
        
        # Step 3: Collect items
        elif session["step"] == "items":
            content = message.content.strip()
            
            if content.lower() == "done":
                if len(session["items"]) == 0:
                    await message.reply("⚠️ You need to add at least one item! Type the item in format: `Name | Price`")
                    return
                
                # Process the report
                await self.process_report(message, session)
                del self.active_sessions[user_id]
                return
            
            # Parse item
            if "|" not in content:
                await message.reply("⚠️ Invalid format! Use: `Product Name | Price`")
                return
            
            parts = content.split("|")
            if len(parts) != 2:
                await message.reply("⚠️ Invalid format! Use: `Product Name | Price`")
                return
            
            item_name = parts[0].strip()
            try:
                price = float(parts[1].strip())
            except ValueError:
                await message.reply("⚠️ Invalid price! Please enter a number.")
                return
            
            if price <= 0:
                await message.reply("⚠️ Price must be positive!")
                return
            
            session["items"].append({"name": item_name, "price": price})
            
            await message.reply(
                f"✅ Added **{item_name}** at **${price:,.2f}**\n"
                f"Total items: {len(session['items'])}\n\n"
                f"Add another item or type **`done`** to process the report."
            )
    
    async def process_report(self, message: discord.Message, session: dict):
        """Process the financial report with all calculations, events, and CEO caps"""
        company_name = session["company_name"]
        company_id = session["company_id"]
        items = session["items"]
        gross_expenses_percent = session["gross_expenses_percent"]
        ceo_salary_percent = session["ceo_salary_percent"]
        
        # Check if company is public
        async with self.bot.db.acquire() as conn:
            is_public = await conn.fetchval(
                "SELECT is_public FROM companies WHERE id = $1",
                company_id
            )
        
        # Get CEO salary caps
        admin_tools = self.bot.get_cog("AdminCompanyTools")
        ceo_cap = admin_tools.public_ceo_cap if (admin_tools and is_public) else (admin_tools.private_ceo_cap if admin_tools else 50000000)
        
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
        
        # CEO salary with cap
        ceo_salary_before_tax = profit_after_corp_tax * (ceo_salary_percent / 100)
        ceo_salary_capped = min(ceo_salary_before_tax, ceo_cap)
        was_capped = ceo_salary_before_tax > ceo_cap
        
        # Personal tax on CEO salary
        personal_tax = 0
        if tax_system and ceo_salary_capped > 0:
            personal_tax, _ = await tax_system.calculate_personal_tax(ceo_salary_capped)
        
        ceo_salary_after_tax = ceo_salary_capped - personal_tax
        net_profit_to_company = profit_after_corp_tax - ceo_salary_capped
        
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
        
        # CEO salary info with cap indicator
        ceo_info = f"**CEO Salary ({ceo_salary_percent:.1f}%):** ${ceo_salary_before_tax:,.2f}\n"
        if was_capped:
            ceo_info += f"⚠️ **Capped at:** ${ceo_salary_capped:,.2f}\n"
        if personal_tax > 0:
            ceo_info += f"**Personal Tax:** -${personal_tax:,.2f}\n"
        ceo_info += f"**CEO Take-Home:** ${ceo_salary_after_tax:,.2f}"
        
        embed.add_field(name="💼 CEO Compensation", value=ceo_info, inline=False)
        embed.add_field(name="🏢 Company Net Profit", value=f"**${net_profit_to_company:,.2f}**", inline=False)
        
        # Update balances
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
                gross_expenses, gross_profit, corporate_tax, ceo_salary_capped,
                personal_tax, net_profit_to_company
            )
            
            # Check for random company event (if public)
            event = None
            if is_public:
                event = CompanyEvents.get_random_event(net_profit_to_company)
            
            # Update stock price if public
            stock = await conn.fetchrow("SELECT id, price FROM stocks WHERE company_id = $1", company_id)
            
            if stock:
                old_price = float(stock['price'])
                
                # Base price change from net profit
                base_change = min(max(net_profit_to_company / 10000, -0.10), 0.10)
                
                # Apply event impact if any
                total_change = base_change
                if event:
                    total_change += event['impact']
                    # Keep within reasonable bounds
                    total_change = min(max(total_change, -0.25), 0.25)
                
                new_price = max(0.01, round(old_price * (1 + total_change), 2))
                
                await conn.execute("UPDATE stocks SET price = $1 WHERE id = $2", new_price, stock['id'])
                
                # Stock price update embed
                emoji = "📈" if new_price > old_price else "📉" if new_price < old_price else "➡️"
                stock_info = f"${old_price:.2f} → **${new_price:.2f}** ({total_change * 100:+.2f}%)"
                
                if event:
                    event_emoji = "✨" if event['is_positive'] else "⚠️"
                    stock_info += f"\n{event_emoji} **{event['name']}**\n_{event['description']}_"
                    stock_info += f"\nEvent Impact: {event['impact'] * 100:+.2f}%"
                
                embed.add_field(
                    name=f"{emoji} Stock Price Update",
                    value=stock_info,
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
        """Cancel your active report filing session"""
        if ctx.author.id in self.active_sessions:
            del self.active_sessions[ctx.author.id]
            await ctx.send("✅ Report filing session cancelled.")
        else:
            await ctx.send("ℹ️ You don't have an active report session.")
    
    @commands.hybrid_command(name="report_status")
    async def report_status(self, ctx):
        """Check your active report filing session"""
        if ctx.author.id not in self.active_sessions:
            await ctx.send("ℹ️ You don't have an active report session.")
            return
        
        session = self.active_sessions[ctx.author.id]
        step_names = {
            "company_name": "Waiting for company name",
            "expenses": "Waiting for expense percentage",
            "items": "Adding items"
        }
        
        embed = discord.Embed(
            title="📋 Report Filing Status",
            color=discord.Color.blue()
        )
        embed.add_field(name="Current Step", value=step_names.get(session["step"], "Unknown"), inline=False)
        
        if session.get("company_name"):
            embed.add_field(name="Company", value=session["company_name"], inline=True)
        
        if session.get("gross_expenses_percent"):
            embed.add_field(name="Expenses", value=f"{session['gross_expenses_percent']}%", inline=True)
        
        if session.get("items"):
            embed.add_field(name="Items Added", value=str(len(session["items"])), inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="view_report_cooldown")
    async def view_report_cooldown(self, ctx):
        """Check report cooldown status for all your companies"""
        async with self.bot.db.acquire() as conn:
            companies = await conn.fetch(
                "SELECT id, name FROM companies WHERE owner_id = $1",
                ctx.author.id
            )
            
            if not companies:
                await ctx.send("❌ You don't own any companies!")
                return
            
            embed = discord.Embed(
                title="⏰ Report Cooldown Status",
                description=f"Cooldown period: **{self.report_cooldown_hours} hours**",
                color=discord.Color.blue()
            )
            
            for company in companies:
                company_id = company['id']
                company_name = company['name']
                
                last_report = await conn.fetchrow(
                    "SELECT reported_at FROM reports WHERE company_id = $1 ORDER BY reported_at DESC LIMIT 1",
                    company_id
                )
                
                if not last_report:
                    status = "✅ **Ready to file!**"
                else:
                    time_since = datetime.now() - last_report['reported_at']
                    cooldown_time = timedelta(hours=self.report_cooldown_hours)
                    
                    if time_since >= cooldown_time:
                        status = "✅ **Ready to file!**"
                    else:
                        remaining = cooldown_time - time_since
                        hours = int(remaining.total_seconds() // 3600)
                        minutes = int((remaining.total_seconds() % 3600) // 60)
                        status = f"⏳ **{hours}h {minutes}m** remaining"
                
                embed.add_field(name=company_name, value=status, inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="view_reports")
    async def view_reports(self, ctx, company_name: str):
        """View financial reports for your company (paginated)"""
        async with self.bot.db.acquire() as conn:
            company = await conn.fetchrow(
                "SELECT id FROM companies WHERE owner_id = $1 AND name = $2",
                ctx.author.id, company_name
            )
            
            if not company:
                await ctx.send("❌ Company not found!")
                return
            
            company_id = company['id']
            
            # Get total count
            total_reports = await conn.fetchval(
                "SELECT COUNT(*) FROM reports WHERE company_id = $1",
                company_id
            )
            
            if total_reports == 0:
                await ctx.send("📋 No reports filed yet!")
                return
            
            # Pagination: 5 reports per page
            reports_per_page = 5
            total_pages = (total_reports + reports_per_page - 1) // reports_per_page
            current_page = 1
            
            # Create the view
            view = ReportsPaginationView(self.bot, company_id, company_name, current_page, total_pages, reports_per_page)
            embed = await view.create_embed()
            
            await ctx.send(embed=embed, view=view)
    
    @commands.hybrid_command(name="set_report_cooldown")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def set_report_cooldown(self, ctx, hours: int):
        """Set the report cooldown in hours (Admin/Owner only)"""
        if hours < 0:
            await ctx.send("❌ Cooldown must be non-negative!")
            return
        
        old_cooldown = self.report_cooldown_hours
        self.report_cooldown_hours = hours
        
        embed = discord.Embed(
            title="⏰ Report Cooldown Updated",
            color=discord.Color.blue()
        )
        embed.add_field(name="Previous", value=f"{old_cooldown} hours", inline=True)
        embed.add_field(name="New", value=f"{hours} hours", inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="bypass_cooldown")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def bypass_cooldown(self, ctx, user: discord.User, company_name: str):
        """Reset report cooldown for a company (Admin/Owner only)"""
        async with self.bot.db.acquire() as conn:
            company = await conn.fetchrow(
                "SELECT id FROM companies WHERE owner_id = $1 AND name = $2",
                user.id, company_name
            )
            
            if not company:
                await ctx.send(f"❌ {user.mention} doesn't own a company named **{company_name}**!")
                return
            
            # Delete all reports to reset cooldown (or you could just delete the latest one)
            # For safety, let's just inform them the company is ready
            last_report = await conn.fetchrow(
                "SELECT reported_at FROM reports WHERE company_id = $1 ORDER BY reported_at DESC LIMIT 1",
                company['id']
            )
            
            if not last_report:
                await ctx.send(f"ℹ️ **{company_name}** has no reports to reset!")
                return
            
            # Delete the most recent report to reset cooldown
            await conn.execute(
                "DELETE FROM reports WHERE company_id = $1 AND reported_at = $2",
                company['id'], last_report['reported_at']
            )
        
        embed = discord.Embed(
            title="✅ Cooldown Bypassed",
            description=f"**{company_name}** (owned by {user.mention}) can now file a report immediately!",
            color=discord.Color.green()
        )
        
        await ctx.send(embed=embed)


class ReportsPaginationView(discord.ui.View):
    """Pagination view for company reports"""
    
    def __init__(self, bot, company_id: int, company_name: str, current_page: int, total_pages: int, reports_per_page: int):
        super().__init__(timeout=180)
        self.bot = bot
        self.company_id = company_id
        self.company_name = company_name
        self.current_page = current_page
        self.total_pages = total_pages
        self.reports_per_page = reports_per_page
        
        self.update_buttons()
    
    def update_buttons(self):
        """Enable/disable buttons based on current page"""
        self.first_page.disabled = (self.current_page == 1)
        self.prev_page.disabled = (self.current_page == 1)
        self.next_page.disabled = (self.current_page == self.total_pages)
        self.last_page.disabled = (self.current_page == self.total_pages)
    
    async def create_embed(self):
        """Create embed for current page"""
        offset = (self.current_page - 1) * self.reports_per_page
        
        async with self.bot.db.acquire() as conn:
            reports = await conn.fetch(
                """SELECT items_sold, gross_revenue, gross_profit, corporate_tax, 
                   ceo_salary, personal_tax, net_profit, reported_at 
                   FROM reports WHERE company_id = $1 
                   ORDER BY reported_at DESC 
                   LIMIT $2 OFFSET $3""",
                self.company_id, self.reports_per_page, offset
            )
        
        embed = discord.Embed(
            title=f"📊 Financial Reports: {self.company_name}",
            description=f"Page {self.current_page}/{self.total_pages}",
            color=discord.Color.blue()
        )
        
        start_idx = offset + 1
        for idx, row in enumerate(reports, start=start_idx):
            items = json.loads(row['items_sold'])
            items_summary = ", ".join([f"{i['name']} (🎲{i['dice']})" for i in items[:3]])
            if len(items) > 3:
                items_summary += f" +{len(items) - 3} more"
            
            embed.add_field(
                name=f"Report #{idx} - {row['reported_at'].strftime('%Y-%m-%d %H:%M')}",
                value=f"Items: {items_summary}\n"
                      f"Revenue: ${float(row['gross_revenue']):,.2f} | Gross: ${float(row['gross_profit']):,.2f}\n"
                      f"Corp Tax: ${float(row['corporate_tax']):,.2f} | CEO: ${float(row['ceo_salary']):,.2f}\n"
                      f"Net: ${float(row['net_profit']):,.2f}",
                inline=False
            )
        
        total_reports = await self.bot.db.fetchval(
            "SELECT COUNT(*) FROM reports WHERE company_id = $1",
            self.company_id
        )
        
        embed.set_footer(text=f"Showing reports {start_idx}-{min(start_idx + len(reports) - 1, total_reports)} of {total_reports}")
        
        return embed
    
    @discord.ui.button(label="<<", style=discord.ButtonStyle.gray)
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to first page"""
        self.current_page = 1
        self.update_buttons()
        embed = await self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="<", style=discord.ButtonStyle.primary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous page"""
        self.current_page -= 1
        self.update_buttons()
        embed = await self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label=">", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next page"""
        self.current_page += 1
        self.update_buttons()
        embed = await self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label=">>", style=discord.ButtonStyle.gray)
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to last page"""
        self.current_page = self.total_pages
        self.update_buttons()
        embed = await self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="🗑️", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close the pagination view"""
        await interaction.response.edit_message(view=None)
        self.stop()


async def setup(bot):
    await bot.add_cog(ReportFiling(bot))

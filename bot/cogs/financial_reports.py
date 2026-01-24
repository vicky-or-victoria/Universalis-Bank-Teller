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
        self.model = os.getenv("OPENAI_MODEL", "gpt-4")
        
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
            "max_tokens": 300,
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
        """Start filing a financial report with Franky's assistance"""
        # Check if user already has an active session
        if ctx.author.id in self.active_sessions:
            await ctx.send("⚠️ You already have an active report session! Use `!cancel_report` to cancel it.")
            return
        
        # Initialize session
        self.active_sessions[ctx.author.id] = {
            "step": "company_name",
            "company_name": None,
            "items": []
        }
        
        # ChatGPT greeting
        messages = [{
            "role": "system",
            "content": "You are Franky, a friendly bank teller helping a customer file their financial report. Be warm and professional."
        }, {
            "role": "user",
            "content": "I want to file a financial report"
        }]
        
        response = await self.call_chatgpt(messages)
        
        if response:
            await ctx.send(f"{response}\n\n**Please provide your company name:**")
        else:
            await ctx.send("**Please provide your company name:**")
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle report filing conversation"""
        if message.author.bot:
            return
        
        if message.content.startswith("!"):
            return
        
        user_id = message.author.id
        
        # Check if user has an active session
        if user_id not in self.active_sessions:
            return
        
        session = self.active_sessions[user_id]
        
        # Step 1: Get company name
        if session["step"] == "company_name":
            company_name = message.content.strip()
            
            # Check if company exists
            async with self.bot.db.cursor() as cursor:
                await cursor.execute(
                    "SELECT id FROM companies WHERE owner_id = ? AND name = ?",
                    (user_id, company_name)
                )
                company = await cursor.fetchone()
                
                if not company:
                    # Create company
                    await cursor.execute(
                        "INSERT INTO companies (name, owner_id) VALUES (?, ?)",
                        (company_name, user_id)
                    )
                    await self.bot.db.commit()
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
        
        # Calculate tax (simple 15% flat tax)
        tax = total_gross * 0.15
        net_profit = total_gross - tax
        
        embed.add_field(
            name="📊 Summary",
            value=f"**Gross Profit:** ${total_gross:,.2f}\n**Tax (15%):** ${tax:,.2f}\n**Net Profit:** ${net_profit:,.2f}",
            inline=False
        )
        
        # Update company balance
        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "SELECT id, balance FROM companies WHERE name = ? AND owner_id = ?",
                (company_name, message.author.id)
            )
            company = await cursor.fetchone()
            company_id = company[0]
            old_balance = company[1]
            new_balance = old_balance + net_profit
            
            await cursor.execute(
                "UPDATE companies SET balance = ? WHERE id = ?",
                (new_balance, company_id)
            )
            
            # Save report
            items_json = json.dumps(results)
            await cursor.execute(
                "INSERT INTO reports (company_id, items_sold, gross_profit, net_profit) VALUES (?, ?, ?, ?)",
                (company_id, items_json, total_gross, net_profit)
            )
            
            await self.bot.db.commit()
        
        embed.add_field(
            name="🏦 Company Balance",
            value=f"Previous: ${old_balance:,.2f}\n**New Balance:** ${new_balance:,.2f}",
            inline=False
        )
        
        # ChatGPT commentary
        messages = [{
            "role": "system",
            "content": "You are Franky, a friendly bank teller. Provide a brief, encouraging comment on the financial report results."
        }, {
            "role": "user",
            "content": f"The report shows a net profit of ${net_profit:,.2f}. Give a brief congratulatory or encouraging message."
        }]
        
        commentary = await self.call_chatgpt(messages)
        if commentary:
            embed.set_footer(text=f"Franky says: {commentary}")
        
        await message.reply(embed=embed)
    
    @commands.hybrid_command(name="cancel_report")
    async def cancel_report(self, ctx):
        """Cancel your active financial report session"""
        if ctx.author.id in self.active_sessions:
            del self.active_sessions[ctx.author.id]
            await ctx.send("✅ Report session cancelled.")
        else:
            await ctx.send("ℹ️ You don't have an active report session.")
    
    @commands.hybrid_command(name="company_balance")
    async def company_balance(self, ctx, *, company_name: str = None):
        """Check your company's balance"""
        async with self.bot.db.cursor() as cursor:
            if company_name:
                await cursor.execute(
                    "SELECT name, balance FROM companies WHERE owner_id = ? AND name = ?",
                    (ctx.author.id, company_name)
                )
            else:
                await cursor.execute(
                    "SELECT name, balance FROM companies WHERE owner_id = ?",
                    (ctx.author.id,)
                )
            
            companies = await cursor.fetchall()
        
        if not companies:
            await ctx.send("❌ You don't own any companies!")
            return
        
        embed = discord.Embed(
            title="🏢 Your Companies",
            color=discord.Color.gold()
        )
        
        for name, balance in companies:
            embed.add_field(
                name=name,
                value=f"Balance: **${balance:,.2f}**",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="view_reports")
    async def view_reports(self, ctx, *, company_name: str):
        """View financial reports for your company"""
        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "SELECT id FROM companies WHERE owner_id = ? AND name = ?",
                (ctx.author.id, company_name)
            )
            company = await cursor.fetchone()
            
            if not company:
                await ctx.send("❌ Company not found!")
                return
            
            company_id = company[0]
            
            await cursor.execute(
                "SELECT items_sold, gross_profit, net_profit, reported_at FROM reports WHERE company_id = ? ORDER BY reported_at DESC LIMIT 5",
                (company_id,)
            )
            reports = await cursor.fetchall()
        
        if not reports:
            await ctx.send("📋 No reports filed yet!")
            return
        
        embed = discord.Embed(
            title=f"📊 Recent Reports: {company_name}",
            color=discord.Color.blue()
        )
        
        for idx, (items_json, gross, net, timestamp) in enumerate(reports, 1):
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

import discord
from discord import app_commands, ui
from discord.ext import commands
import json
import os
import random
import asyncio
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime, timedelta

SETTINGS_FILE = "settings.json"

DEFAULT_SETTINGS = {
    "tax_brackets": [
        {"min": 0, "max": 50000, "rate": 10.0},
        {"min": 50000, "max": 100000, "rate": 15.0},
        {"min": 100000, "max": 500000, "rate": 20.0},
        {"min": 500000, "max": None, "rate": 25.0}
    ],
    "ceo_salary_percent": 10.0,
    "ceo_tax_brackets": [
        {"min": 0, "max": 10000, "rate": 5.0},
        {"min": 10000, "max": 50000, "rate": 10.0},
        {"min": 50000, "max": 100000, "rate": 15.0},
        {"min": 100000, "max": None, "rate": 20.0}
    ]
}

DICE_OPTIONS = [10, 12, 20, 25, 50, 100]

def load_settings():
    if Path(SETTINGS_FILE).exists():
        try:
            with open(SETTINGS_FILE, "r") as f:
                data = json.load(f)
                if "tax_brackets" not in data:
                    data["tax_brackets"] = DEFAULT_SETTINGS["tax_brackets"]
                if "ceo_tax_brackets" not in data:
                    data["ceo_tax_brackets"] = DEFAULT_SETTINGS["ceo_tax_brackets"]
                if "ceo_salary_percent" not in data:
                    data["ceo_salary_percent"] = DEFAULT_SETTINGS["ceo_salary_percent"]
                return data
        except (json.JSONDecodeError, IOError):
            print("Warning: Could not read settings file. Using defaults.")
            return DEFAULT_SETTINGS.copy()
    return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)

def is_admin(interaction: discord.Interaction) -> bool:
    if not interaction.guild:
        return False
    if isinstance(interaction.user, discord.Member):
        return interaction.user.guild_permissions.administrator
    return False

def calculate_progressive_tax(amount: float, brackets: list) -> tuple:
    if amount <= 0:
        return 0.0, []
    
    total_tax = 0.0
    breakdown = []
    
    sorted_brackets = sorted(brackets, key=lambda x: x["min"])
    
    for bracket in sorted_brackets:
        bracket_min = bracket["min"]
        bracket_max = bracket["max"] if bracket["max"] is not None else float('inf')
        rate = bracket["rate"]
        
        if amount <= bracket_min:
            continue
        
        if bracket_max == float('inf'):
            taxable_in_bracket = max(0, amount - bracket_min)
        else:
            upper = min(amount, bracket_max)
            taxable_in_bracket = max(0, upper - bracket_min)
        
        if taxable_in_bracket > 0:
            tax_for_bracket = taxable_in_bracket * (rate / 100)
            total_tax += tax_for_bracket
            breakdown.append({
                "min": bracket_min,
                "max": bracket_max,
                "rate": rate,
                "taxable": taxable_in_bracket,
                "tax": tax_for_bracket
            })
    
    return total_tax, breakdown

def format_bracket_range(min_val: float, max_val) -> str:
    if max_val is None or max_val == float('inf'):
        return f"${min_val:,.0f}+"
    return f"${min_val:,.0f} - ${max_val:,.0f}"

def format_money(amount: float) -> str:
    return f"${amount:,.2f}"

def create_divider() -> str:
    return "─" * 30

def roll_dice(sides: int) -> int:
    return random.randint(1, sides)

settings = load_settings()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

class CalculatorSession:
    def __init__(self, user_id: int, channel_id: int, interaction: discord.Interaction):
        self.user_id = user_id
        self.channel_id = channel_id
        self.interaction = interaction
        self.include_ceo_salary = True
        self.ceo_salary_multiplier = 100
        self.items: List[dict] = []
        self.expenses: float = 0.0
        self.input_state: Optional[str] = None
        self.pending_item: Optional[dict] = None
        self.dialogue = "*The bank teller greets you with a warm smile...*\n\n*\"Welcome! Let's calculate your business finances. Use the buttons below to build your financial report!\"*"
        self.created_at = datetime.utcnow()
        self.timeout_minutes = 10
    
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.created_at + timedelta(minutes=self.timeout_minutes)

class SessionManager:
    def __init__(self):
        self.sessions: Dict[int, CalculatorSession] = {}
    
    def create_session(self, user_id: int, channel_id: int, interaction: discord.Interaction) -> CalculatorSession:
        session = CalculatorSession(user_id, channel_id, interaction)
        self.sessions[user_id] = session
        return session
    
    def get_session(self, user_id: int) -> Optional[CalculatorSession]:
        session = self.sessions.get(user_id)
        if session and session.is_expired():
            self.remove_session(user_id)
            return None
        return session
    
    def remove_session(self, user_id: int):
        if user_id in self.sessions:
            del self.sessions[user_id]
    
    def get_session_by_channel(self, user_id: int, channel_id: int) -> Optional[CalculatorSession]:
        session = self.get_session(user_id)
        if session and session.channel_id == channel_id:
            return session
        return None

session_manager = SessionManager()

class CalculatorView(ui.View):
    def __init__(self, session: CalculatorSession):
        super().__init__(timeout=600)
        self.session = session
    
    def create_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="Universalis Bank - Financial Calculator",
            description=self.session.dialogue,
            color=discord.Color.from_rgb(0, 123, 255)
        )
        
        if self.session.include_ceo_salary:
            ceo_base = settings["ceo_salary_percent"]
            effective_ceo = ceo_base * (self.session.ceo_salary_multiplier / 100)
            ceo_status = f"Yes ({self.session.ceo_salary_multiplier}% of {ceo_base}% = {effective_ceo:.1f}%)"
        else:
            ceo_status = "No"
        
        embed.add_field(
            name="CEO Salary",
            value=f"```{ceo_status}```",
            inline=True
        )
        
        embed.add_field(
            name="Business Expenses",
            value=f"```{format_money(self.session.expenses)}```",
            inline=True
        )
        
        if self.session.items:
            items_text = ""
            total_revenue = 0.0
            for item in self.session.items:
                revenue = item["price"] * item["quantity"]
                total_revenue += revenue
                items_text += f"**{item['name']}**\n"
                items_text += f"  {format_money(item['price'])} × {item['quantity']} (d{item['dice']}) = {format_money(revenue)}\n"
            
            embed.add_field(
                name=f"Items/Services ({len(self.session.items)})",
                value=items_text,
                inline=False
            )
            
            embed.add_field(
                name="Total Gross Revenue",
                value=f"```{format_money(total_revenue)}```",
                inline=False
            )
        else:
            embed.add_field(
                name="Items/Services",
                value="*No items added yet. Click \"Add Item\" to get started!*",
                inline=False
            )
        
        if self.session.input_state:
            state_messages = {
                "awaiting_item_name": "Type the **item/service name** in the chat below:",
                "awaiting_item_price": f"Now type the **price** for **{self.session.pending_item['name'] if self.session.pending_item else 'item'}**:",
                "awaiting_dice": f"Type the **dice type** (10, 12, 20, 25, 50, or 100) for **{self.session.pending_item['name'] if self.session.pending_item else 'item'}**:",
                "awaiting_expenses": "Type your **total business expenses** in the chat below:",
                "awaiting_ceo_percent": "Type the **percentage of CEO salary** you want to take (1-100):"
            }
            prompt = state_messages.get(self.session.input_state, "Waiting for input...")
            embed.add_field(
                name="Awaiting Your Input",
                value=f"```\n{prompt}\n```\n*Type your response in this channel and I'll read it!*",
                inline=False
            )
        
        embed.set_footer(text="Your messages will be automatically deleted after I read them!")
        return embed
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message(
                "*\"I'm sorry, but this calculator session belongs to someone else!\"*",
                ephemeral=True
            )
            return False
        return True
    
    async def update_embed(self, interaction: discord.Interaction):
        try:
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        except discord.errors.InteractionResponded:
            await interaction.edit_original_response(embed=self.create_embed(), view=self)
    
    @ui.button(label="Toggle CEO Salary", style=discord.ButtonStyle.secondary, emoji="👔", row=0)
    async def toggle_ceo(self, interaction: discord.Interaction, button: ui.Button):
        if self.session.input_state:
            self.session.dialogue = "*\"Please finish your current input first, dear!\"*"
            await self.update_embed(interaction)
            return
        
        self.session.include_ceo_salary = not self.session.include_ceo_salary
        if self.session.include_ceo_salary:
            self.session.dialogue = "*The bank teller nods approvingly...*\n\n*\"CEO salary is now enabled! Would you like to adjust the percentage?\"*"
        else:
            self.session.dialogue = "*The bank teller makes a note...*\n\n*\"Understood! No CEO salary will be calculated this time.\"*"
        await self.update_embed(interaction)
    
    @ui.button(label="Set CEO %", style=discord.ButtonStyle.secondary, emoji="💼", row=0)
    async def set_ceo_percent(self, interaction: discord.Interaction, button: ui.Button):
        if self.session.input_state:
            self.session.dialogue = "*\"Please finish your current input first, dear!\"*"
            await self.update_embed(interaction)
            return
        
        if not self.session.include_ceo_salary:
            self.session.dialogue = "*\"CEO salary is currently disabled. Enable it first with the toggle button!\"*"
            await self.update_embed(interaction)
            return
        
        self.session.input_state = "awaiting_ceo_percent"
        self.session.dialogue = f"*The bank teller pulls out a form...*\n\n*\"The maximum CEO salary is {settings['ceo_salary_percent']}% of post-tax profit. What percentage of this would you like to take? Type a number from 1 to 100.\"*"
        await self.update_embed(interaction)
    
    @ui.button(label="Add Item", style=discord.ButtonStyle.primary, emoji="📦", row=1)
    async def add_item(self, interaction: discord.Interaction, button: ui.Button):
        if self.session.input_state:
            self.session.dialogue = "*\"Please finish your current input first, dear!\"*"
            await self.update_embed(interaction)
            return
        
        if len(self.session.items) >= 10:
            self.session.dialogue = "*\"Oh my, that's quite a lot! We can only handle up to 10 items at a time.\"*"
            await self.update_embed(interaction)
            return
        
        self.session.input_state = "awaiting_item_name"
        self.session.pending_item = {}
        self.session.dialogue = "*The bank teller prepares her ledger...*\n\n*\"What item or service did you sell? Type the name in the chat below!\"*"
        await self.update_embed(interaction)
    
    @ui.button(label="Set Expenses", style=discord.ButtonStyle.secondary, emoji="💸", row=1)
    async def set_expenses(self, interaction: discord.Interaction, button: ui.Button):
        if self.session.input_state:
            self.session.dialogue = "*\"Please finish your current input first, dear!\"*"
            await self.update_embed(interaction)
            return
        
        self.session.input_state = "awaiting_expenses"
        self.session.dialogue = "*The bank teller looks up from her desk...*\n\n*\"What were your total business expenses? Type the amount in the chat below!\"*"
        await self.update_embed(interaction)
    
    @ui.button(label="Clear All", style=discord.ButtonStyle.danger, emoji="🗑️", row=2)
    async def clear_all(self, interaction: discord.Interaction, button: ui.Button):
        self.session.items = []
        self.session.expenses = 0.0
        self.session.include_ceo_salary = True
        self.session.ceo_salary_multiplier = 100
        self.session.pending_item = None
        self.session.input_state = None
        self.session.dialogue = "*The bank teller clears her ledger...*\n\n*\"All cleared! Let's start fresh. What would you like to do?\"*"
        await self.update_embed(interaction)
    
    @ui.button(label="Cancel Input", style=discord.ButtonStyle.secondary, emoji="❌", row=2)
    async def cancel_input(self, interaction: discord.Interaction, button: ui.Button):
        if self.session.input_state:
            self.session.input_state = None
            self.session.pending_item = None
            self.session.dialogue = "*The bank teller nods understandingly...*\n\n*\"No problem! Input cancelled. What would you like to do next?\"*"
        else:
            self.session.dialogue = "*\"There's nothing to cancel right now, dear!\"*"
        await self.update_embed(interaction)
    
    @ui.button(label="Calculate", style=discord.ButtonStyle.success, emoji="🧮", row=2)
    async def calculate(self, interaction: discord.Interaction, button: ui.Button):
        if self.session.input_state:
            self.session.dialogue = "*\"Please finish your current input first, dear!\"*"
            await self.update_embed(interaction)
            return
        
        if not self.session.items:
            self.session.dialogue = "*\"Oh dear, you haven't added any items yet! Please add at least one item or service first.\"*"
            await self.update_embed(interaction)
            return
        
        gross_profit = sum(item["price"] * item["quantity"] for item in self.session.items)
        
        result_embed = await self.generate_financial_report(gross_profit, self.session.expenses)
        result_embed.set_footer(text=f"Report generated for {interaction.user.display_name} | Universalis Bank | Here to help your business thrive")
        
        session_manager.remove_session(self.session.user_id)
        self.stop()
        
        await interaction.response.defer()
        await interaction.channel.send(embed=result_embed)
    
    async def generate_financial_report(self, gross_profit: float, gross_expenses: float) -> discord.Embed:
        ceo_base_rate = settings["ceo_salary_percent"]
        effective_ceo_rate = ceo_base_rate * (self.session.ceo_salary_multiplier / 100) if self.session.include_ceo_salary else 0
        business_brackets = settings["tax_brackets"]
        ceo_brackets = settings["ceo_tax_brackets"]
        
        net_profit = gross_profit - gross_expenses
        
        if net_profit <= 0:
            embed = discord.Embed(
                title="Universalis Bank",
                description="*The bank teller looks over her glasses with a gentle, sympathetic smile...*",
                color=discord.Color.from_rgb(220, 53, 69)
            )
            
            sales_text = ""
            for item in self.session.items:
                revenue = item["price"] * item["quantity"]
                sales_text += f"{item['name']}: {item['quantity']} sold @ {format_money(item['price'])} = {format_money(revenue)}\n"
            
            embed.add_field(
                name="Sales Breakdown",
                value=f"```\n{sales_text}```",
                inline=False
            )
            
            embed.add_field(
                name="Financial Summary",
                value=(
                    f"```\n"
                    f"Gross Revenue:   {format_money(gross_profit):>15}\n"
                    f"Gross Expenses:  {format_money(gross_expenses):>15}\n"
                    f"{create_divider()}\n"
                    f"Net Profit:      {format_money(net_profit):>15}\n"
                    f"```"
                ),
                inline=False
            )
            embed.add_field(
                name="Assessment",
                value="*\"Oh dear, it looks like your expenses exceeded your earnings this period. Don't worry though - no taxes or salary deductions apply when there's no profit. Let me know if you need any help planning for next quarter!\"*",
                inline=False
            )
            embed.set_footer(text="Universalis Bank | Here to help your business thrive")
            return embed
        
        business_tax, business_breakdown = calculate_progressive_tax(net_profit, business_brackets)
        profit_after_tax = net_profit - business_tax
        
        if self.session.include_ceo_salary:
            gross_ceo_salary = profit_after_tax * (effective_ceo_rate / 100)
            ceo_tax, ceo_breakdown = calculate_progressive_tax(gross_ceo_salary, ceo_brackets)
            net_ceo_salary = gross_ceo_salary - ceo_tax
            final_profit = profit_after_tax - gross_ceo_salary
        else:
            gross_ceo_salary = 0
            ceo_tax = 0
            net_ceo_salary = 0
            ceo_breakdown = []
            final_profit = profit_after_tax
        
        business_effective_rate = (business_tax / net_profit * 100) if net_profit > 0 else 0
        ceo_effective_rate = (ceo_tax / gross_ceo_salary * 100) if gross_ceo_salary > 0 else 0
        
        embed = discord.Embed(
            title="Universalis Bank",
            description="*The bank teller smiles warmly as she prepares your detailed financial report...*",
            color=discord.Color.from_rgb(255, 193, 7)
        )
        
        sales_text = ""
        for item in self.session.items:
            revenue = item["price"] * item["quantity"]
            sales_text += f"🎲 {item['name']}\n"
            sales_text += f"   d{item['dice']} → {item['quantity']} units @ {format_money(item['price'])} = {format_money(revenue)}\n"
        
        embed.add_field(
            name="Sales Results (Dice Rolls)",
            value=sales_text,
            inline=False
        )
        
        embed.add_field(
            name="Revenue Overview",
            value=(
                f"```\n"
                f"Gross Revenue:   {format_money(gross_profit):>15}\n"
                f"Gross Expenses:  {format_money(gross_expenses):>15}\n"
                f"{create_divider()}\n"
                f"Net Profit:      {format_money(net_profit):>15}\n"
                f"```"
            ),
            inline=False
        )
        
        business_tax_text = ""
        for item in business_breakdown:
            bracket_range = format_bracket_range(item["min"], item["max"])
            business_tax_text += f"{bracket_range} @ {item['rate']}%\n   Tax: {format_money(item['tax'])}\n"
        business_tax_text += f"\nTotal: {format_money(business_tax)} (Effective: {business_effective_rate:.1f}%)"
        
        embed.add_field(
            name="Business Income Tax",
            value=f"```\n{business_tax_text}\n```",
            inline=False
        )
        
        embed.add_field(
            name="After Business Tax",
            value=(
                f"```\n"
                f"Net Profit:      {format_money(net_profit):>15}\n"
                f"Business Tax:   -{format_money(business_tax):>15}\n"
                f"{create_divider()}\n"
                f"Remaining:       {format_money(profit_after_tax):>15}\n"
                f"```"
            ),
            inline=False
        )
        
        if self.session.include_ceo_salary:
            embed.add_field(
                name=f"CEO Compensation ({self.session.ceo_salary_multiplier}% of {ceo_base_rate}% = {effective_ceo_rate:.1f}%)",
                value=(
                    f"```\n"
                    f"Gross CEO Salary: {format_money(gross_ceo_salary):>14}\n"
                    f"```"
                ),
                inline=False
            )
            
            ceo_tax_text = ""
            for item in ceo_breakdown:
                bracket_range = format_bracket_range(item["min"], item["max"])
                ceo_tax_text += f"{bracket_range} @ {item['rate']}%\n   Tax: {format_money(item['tax'])}\n"
            ceo_tax_text += f"\nTotal: {format_money(ceo_tax)} (Effective: {ceo_effective_rate:.1f}%)"
            
            embed.add_field(
                name="CEO Income Tax",
                value=f"```\n{ceo_tax_text}\n```",
                inline=False
            )
            
            embed.add_field(
                name="CEO Take-Home",
                value=(
                    f"```\n"
                    f"Gross Salary:    {format_money(gross_ceo_salary):>15}\n"
                    f"CEO Tax:        -{format_money(ceo_tax):>15}\n"
                    f"{create_divider()}\n"
                    f"Net Salary:      {format_money(net_ceo_salary):>15}\n"
                    f"```"
                ),
                inline=False
            )
            
            embed.add_field(
                name="Final Business Summary",
                value=(
                    f"```\n"
                    f"Profit After Tax: {format_money(profit_after_tax):>14}\n"
                    f"CEO Salary:      -{format_money(gross_ceo_salary):>14}\n"
                    f"{create_divider()}\n"
                    f"Business Profit:  {format_money(final_profit):>14}\n"
                    f"```"
                ),
                inline=False
            )
            
            total_taxes = business_tax + ceo_tax
            embed.add_field(
                name="Summary",
                value=(
                    f"*\"Wonderful news! Here's your complete breakdown:*\n\n"
                    f"*Business paid **{format_money(business_tax)}** in taxes.*\n"
                    f"*CEO receives **{format_money(net_ceo_salary)}** after their personal tax of **{format_money(ceo_tax)}**.*\n"
                    f"*The business retains **{format_money(final_profit)}**.*\n\n"
                    f"*Total taxes collected: **{format_money(total_taxes)}**. You're doing great!\"*"
                ),
                inline=False
            )
        else:
            embed.add_field(
                name="Final Business Summary (No CEO Salary)",
                value=(
                    f"```\n"
                    f"Profit After Tax: {format_money(profit_after_tax):>14}\n"
                    f"CEO Salary:       {format_money(0):>14}\n"
                    f"{create_divider()}\n"
                    f"Business Profit:  {format_money(final_profit):>14}\n"
                    f"```"
                ),
                inline=False
            )
            
            embed.add_field(
                name="Summary",
                value=(
                    f"*\"Here's your complete breakdown:*\n\n"
                    f"*Business paid **{format_money(business_tax)}** in taxes.*\n"
                    f"*No CEO salary was allocated this period.*\n"
                    f"*The business retains **{format_money(final_profit)}**.*\n\n"
                    f"*Great work managing your finances!\"*"
                ),
                inline=False
            )
        
        embed.set_footer(text="Universalis Bank | Here to help your business thrive")
        
        return embed

@bot.event
async def on_ready():
    print(f"{bot.user} is now open for business!")
    print(f"Connected to {len(bot.guilds)} guild(s)")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    
    session = session_manager.get_session_by_channel(message.author.id, message.channel.id)
    
    if not session or not session.input_state:
        return
    
    content = message.content.strip()
    
    try:
        await message.delete()
    except discord.errors.Forbidden:
        pass
    except discord.errors.NotFound:
        pass
    
    view = CalculatorView(session)
    
    if session.input_state == "awaiting_item_name":
        if len(content) > 100:
            session.dialogue = "*\"That name is a bit too long, dear. Please keep it under 100 characters!\"*"
        elif len(content) == 0:
            session.dialogue = "*\"I didn't catch that. Please type a name for your item or service!\"*"
        else:
            session.pending_item = {"name": content}
            session.input_state = "awaiting_item_price"
            session.dialogue = f"*The bank teller writes down \"{content}\"...*\n\n*\"Great! Now, what's the price per unit for this item?\"*"
    
    elif session.input_state == "awaiting_item_price":
        try:
            price = float(content.replace(',', '').replace('$', ''))
            if price <= 0:
                session.dialogue = "*\"The price needs to be a positive number, dear!\"*"
            else:
                session.pending_item["price"] = price
                session.input_state = "awaiting_dice"
                session.dialogue = f"*The bank teller notes the price of {format_money(price)}...*\n\n*\"Now, which dice shall we roll to determine how many units were sold? Type 10, 12, 20, 25, 50, or 100!\"*"
        except ValueError:
            session.dialogue = "*\"That doesn't look like a valid price. Please enter a number like 25.99!\"*"
    
    elif session.input_state == "awaiting_dice":
        try:
            dice = int(content.replace('d', '').replace('D', ''))
            if dice not in DICE_OPTIONS:
                session.dialogue = f"*\"I only have d10, d12, d20, d25, d50, and d100 dice available. Please choose one of those!\"*"
            else:
                roll_result = roll_dice(dice)
                session.pending_item["dice"] = dice
                session.pending_item["quantity"] = roll_result
                session.items.append(session.pending_item)
                session.pending_item = None
                session.input_state = None
                item_name = session.items[-1]["name"]
                session.dialogue = f"*The bank teller rolls the d{dice}...*\n\n🎲 **Rolled a {roll_result}!**\n\n*\"{item_name} sold {roll_result} units! I've added it to your ledger. Anything else?\"*"
        except ValueError:
            session.dialogue = "*\"Please enter a valid dice number: 10, 12, 20, 25, 50, or 100!\"*"
    
    elif session.input_state == "awaiting_expenses":
        try:
            amount = float(content.replace(',', '').replace('$', ''))
            if amount < 0:
                session.dialogue = "*\"Expenses can't be negative, dear!\"*"
            else:
                session.expenses = amount
                session.input_state = None
                session.dialogue = f"*The bank teller records the expenses...*\n\n*\"Got it! Business expenses set to {format_money(amount)}. What's next?\"*"
        except ValueError:
            session.dialogue = "*\"That doesn't look like a valid amount. Please enter a number like 5000.00!\"*"
    
    elif session.input_state == "awaiting_ceo_percent":
        try:
            percent = int(content.replace('%', ''))
            if percent < 1 or percent > 100:
                session.dialogue = "*\"Please enter a percentage between 1 and 100!\"*"
            else:
                session.ceo_salary_multiplier = percent
                session.input_state = None
                effective = settings["ceo_salary_percent"] * (percent / 100)
                session.dialogue = f"*The bank teller updates the compensation form...*\n\n*\"Perfect! You'll take {percent}% of the allowed {settings['ceo_salary_percent']}% CEO salary, which is {effective:.1f}% of post-tax profit.\"*"
        except ValueError:
            session.dialogue = "*\"Please enter a valid percentage number between 1 and 100!\"*"
    
    try:
        await session.interaction.edit_original_response(embed=view.create_embed(), view=view)
    except discord.errors.NotFound:
        session_manager.remove_session(session.user_id)
    except Exception as e:
        print(f"Error updating session: {e}")

@bot.tree.command(name="calculate", description="Open the interactive financial calculator")
async def calculate(interaction: discord.Interaction):
    existing_session = session_manager.get_session(interaction.user.id)
    if existing_session:
        session_manager.remove_session(interaction.user.id)
    
    session = session_manager.create_session(interaction.user.id, interaction.channel.id, interaction)
    view = CalculatorView(session)
    
    await interaction.response.send_message(
        embed=view.create_embed(),
        view=view,
        ephemeral=True
    )

@bot.tree.command(name="view_rates", description="View the current tax brackets and CEO salary rates")
async def view_rates(interaction: discord.Interaction):
    business_brackets = settings["tax_brackets"]
    ceo_brackets = settings["ceo_tax_brackets"]
    ceo_rate = settings["ceo_salary_percent"]
    
    embed = discord.Embed(
        title="Universalis Bank - Tax Rate Schedule",
        description="*The bank teller pulls up the current rates with a helpful smile...*\n\n*\"Here's our complete tax structure!\"*",
        color=discord.Color.from_rgb(0, 123, 255)
    )
    
    business_text = ""
    sorted_business = sorted(business_brackets, key=lambda x: x["min"])
    for bracket in sorted_business:
        bracket_range = format_bracket_range(bracket["min"], bracket["max"])
        business_text += f"{bracket_range}: {bracket['rate']}%\n"
    
    embed.add_field(
        name="Business Income Tax Brackets",
        value=f"```\n{business_text}```",
        inline=False
    )
    
    ceo_text = ""
    sorted_ceo = sorted(ceo_brackets, key=lambda x: x["min"])
    for bracket in sorted_ceo:
        bracket_range = format_bracket_range(bracket["min"], bracket["max"])
        ceo_text += f"{bracket_range}: {bracket['rate']}%\n"
    
    embed.add_field(
        name="CEO Income Tax Brackets",
        value=f"```\n{ceo_text}```",
        inline=False
    )
    
    embed.add_field(
        name="CEO Salary Rate",
        value=f"```\n{ceo_rate}% of post-tax business profit (adjustable per calculation)\n```",
        inline=False
    )
    
    embed.add_field(
        name="How Progressive Tax Works",
        value=(
            "*Each bracket only applies to income within that range.*\n\n"
            "**Example:** $75,000 income with brackets:\n"
            "- $0-$50k @ 10% and $50k-$100k @ 15%\n"
            "- First $50,000 taxed at 10% = $5,000\n"
            "- Remaining $25,000 taxed at 15% = $3,750\n"
            "- **Total tax: $8,750** (Effective rate: 11.7%)"
        ),
        inline=False
    )
    
    embed.set_footer(text="Use /calculate to run your numbers!")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="set_bracket", description="[ADMIN] Set or update a business tax bracket")
@app_commands.describe(
    bracket_min="Minimum amount for this bracket (e.g., 0, 50000, 100000)",
    bracket_max="Maximum amount for this bracket (leave empty for unlimited)",
    rate="Tax rate percentage for this bracket (0-100)"
)
@app_commands.default_permissions(administrator=True)
async def set_bracket(interaction: discord.Interaction, bracket_min: float, rate: float, bracket_max: Optional[float] = None):
    if not is_admin(interaction):
        embed = discord.Embed(
            title="Access Restricted",
            description="*The bank teller gives an apologetic smile...*\n\n*\"I'm so sorry, but only authorized administrators can adjust tax brackets. Is there anything else I can help you with today?\"*",
            color=discord.Color.from_rgb(220, 53, 69)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if rate < 0 or rate > 100:
        embed = discord.Embed(
            title="Invalid Entry",
            description="*The bank teller tilts her head kindly...*\n\n*\"Oh, that doesn't seem quite right! The tax rate needs to be between 0% and 100%. Would you like to try again?\"*",
            color=discord.Color.from_rgb(255, 193, 7)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if bracket_min < 0:
        embed = discord.Embed(
            title="Invalid Entry",
            description="*The bank teller shakes her head gently...*\n\n*\"The minimum amount can't be negative, dear. Let's try again with a positive number!\"*",
            color=discord.Color.from_rgb(255, 193, 7)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if bracket_max is not None and bracket_max <= bracket_min:
        embed = discord.Embed(
            title="Invalid Entry",
            description="*The bank teller looks puzzled...*\n\n*\"The maximum needs to be higher than the minimum. Would you like to try again?\"*",
            color=discord.Color.from_rgb(255, 193, 7)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    brackets = settings["tax_brackets"]
    updated = False
    for i, bracket in enumerate(brackets):
        if bracket["min"] == bracket_min:
            brackets[i] = {"min": bracket_min, "max": bracket_max, "rate": rate}
            updated = True
            break
    
    if not updated:
        brackets.append({"min": bracket_min, "max": bracket_max, "rate": rate})
    
    settings["tax_brackets"] = sorted(brackets, key=lambda x: x["min"])
    save_settings(settings)
    
    action = "updated" if updated else "added"
    bracket_range = format_bracket_range(bracket_min, bracket_max)
    
    embed = discord.Embed(
        title="Business Tax Bracket Updated",
        description="*The bank teller updates the system with a cheerful nod...*",
        color=discord.Color.from_rgb(40, 167, 69)
    )
    embed.add_field(
        name="Changes Applied",
        value=f"```\nBracket: {bracket_range}\nRate: {rate}%\nAction: {action.title()}\n```",
        inline=False
    )
    embed.add_field(
        name="Confirmation",
        value=f"*\"All done! I've {action} the business tax bracket for {bracket_range} at {rate}%. Is there anything else you need?\"*",
        inline=False
    )
    embed.set_footer(text=f"Authorized by {interaction.user.display_name}")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="remove_bracket", description="[ADMIN] Remove a business tax bracket")
@app_commands.describe(bracket_min="The minimum amount of the bracket to remove")
@app_commands.default_permissions(administrator=True)
async def remove_bracket(interaction: discord.Interaction, bracket_min: float):
    if not is_admin(interaction):
        embed = discord.Embed(
            title="Access Restricted",
            description="*The bank teller gives an apologetic smile...*\n\n*\"I'm so sorry, but only authorized administrators can remove tax brackets. Is there anything else I can help you with today?\"*",
            color=discord.Color.from_rgb(220, 53, 69)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    brackets = settings["tax_brackets"]
    
    if len(brackets) <= 1:
        embed = discord.Embed(
            title="Cannot Remove",
            description="*The bank teller looks concerned...*\n\n*\"Oh dear, we need at least one tax bracket in the system. I can't remove the last one!\"*",
            color=discord.Color.from_rgb(255, 193, 7)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    found = None
    for i, bracket in enumerate(brackets):
        if bracket["min"] == bracket_min:
            found = brackets.pop(i)
            break
    
    if not found:
        embed = discord.Embed(
            title="Not Found",
            description=f"*The bank teller checks her records...*\n\n*\"Hmm, I don't see a bracket starting at ${bracket_min:,.0f}. Would you like to check /view_rates to see the current brackets?\"*",
            color=discord.Color.from_rgb(255, 193, 7)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    settings["tax_brackets"] = brackets
    save_settings(settings)
    
    bracket_range = format_bracket_range(found["min"], found["max"])
    
    embed = discord.Embed(
        title="Business Tax Bracket Removed",
        description="*The bank teller updates the records...*",
        color=discord.Color.from_rgb(40, 167, 69)
    )
    embed.add_field(
        name="Removed Bracket",
        value=f"```\nBracket: {bracket_range}\nRate: {found['rate']}%\n```",
        inline=False
    )
    embed.add_field(
        name="Confirmation",
        value=f"*\"Done! I've removed the {bracket_range} bracket from our system. The remaining brackets are still in place.\"*",
        inline=False
    )
    embed.set_footer(text=f"Authorized by {interaction.user.display_name}")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="set_ceo_bracket", description="[ADMIN] Set or update a CEO income tax bracket")
@app_commands.describe(
    bracket_min="Minimum amount for this bracket (e.g., 0, 10000, 50000)",
    bracket_max="Maximum amount for this bracket (leave empty for unlimited)",
    rate="Tax rate percentage for this bracket (0-100)"
)
@app_commands.default_permissions(administrator=True)
async def set_ceo_bracket(interaction: discord.Interaction, bracket_min: float, rate: float, bracket_max: Optional[float] = None):
    if not is_admin(interaction):
        embed = discord.Embed(
            title="Access Restricted",
            description="*The bank teller gives an apologetic smile...*\n\n*\"I'm so sorry, but only authorized administrators can adjust CEO tax brackets. Is there anything else I can help you with today?\"*",
            color=discord.Color.from_rgb(220, 53, 69)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if rate < 0 or rate > 100:
        embed = discord.Embed(
            title="Invalid Entry",
            description="*The bank teller tilts her head kindly...*\n\n*\"Oh, that doesn't seem quite right! The tax rate needs to be between 0% and 100%. Would you like to try again?\"*",
            color=discord.Color.from_rgb(255, 193, 7)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if bracket_min < 0:
        embed = discord.Embed(
            title="Invalid Entry",
            description="*The bank teller shakes her head gently...*\n\n*\"The minimum amount can't be negative, dear. Let's try again with a positive number!\"*",
            color=discord.Color.from_rgb(255, 193, 7)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if bracket_max is not None and bracket_max <= bracket_min:
        embed = discord.Embed(
            title="Invalid Entry",
            description="*The bank teller looks puzzled...*\n\n*\"The maximum needs to be higher than the minimum. Would you like to try again?\"*",
            color=discord.Color.from_rgb(255, 193, 7)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    brackets = settings["ceo_tax_brackets"]
    updated = False
    for i, bracket in enumerate(brackets):
        if bracket["min"] == bracket_min:
            brackets[i] = {"min": bracket_min, "max": bracket_max, "rate": rate}
            updated = True
            break
    
    if not updated:
        brackets.append({"min": bracket_min, "max": bracket_max, "rate": rate})
    
    settings["ceo_tax_brackets"] = sorted(brackets, key=lambda x: x["min"])
    save_settings(settings)
    
    action = "updated" if updated else "added"
    bracket_range = format_bracket_range(bracket_min, bracket_max)
    
    embed = discord.Embed(
        title="CEO Tax Bracket Updated",
        description="*The bank teller updates the system with a cheerful nod...*",
        color=discord.Color.from_rgb(40, 167, 69)
    )
    embed.add_field(
        name="Changes Applied",
        value=f"```\nBracket: {bracket_range}\nRate: {rate}%\nAction: {action.title()}\n```",
        inline=False
    )
    embed.add_field(
        name="Confirmation",
        value=f"*\"All done! I've {action} the CEO tax bracket for {bracket_range} at {rate}%. Is there anything else you need?\"*",
        inline=False
    )
    embed.set_footer(text=f"Authorized by {interaction.user.display_name}")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="remove_ceo_bracket", description="[ADMIN] Remove a CEO income tax bracket")
@app_commands.describe(bracket_min="The minimum amount of the bracket to remove")
@app_commands.default_permissions(administrator=True)
async def remove_ceo_bracket(interaction: discord.Interaction, bracket_min: float):
    if not is_admin(interaction):
        embed = discord.Embed(
            title="Access Restricted",
            description="*The bank teller gives an apologetic smile...*\n\n*\"I'm so sorry, but only authorized administrators can remove CEO tax brackets. Is there anything else I can help you with today?\"*",
            color=discord.Color.from_rgb(220, 53, 69)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    brackets = settings["ceo_tax_brackets"]
    
    if len(brackets) <= 1:
        embed = discord.Embed(
            title="Cannot Remove",
            description="*The bank teller looks concerned...*\n\n*\"Oh dear, we need at least one CEO tax bracket in the system. I can't remove the last one!\"*",
            color=discord.Color.from_rgb(255, 193, 7)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    found = None
    for i, bracket in enumerate(brackets):
        if bracket["min"] == bracket_min:
            found = brackets.pop(i)
            break
    
    if not found:
        embed = discord.Embed(
            title="Not Found",
            description=f"*The bank teller checks her records...*\n\n*\"Hmm, I don't see a CEO tax bracket starting at ${bracket_min:,.0f}. Would you like to check /view_rates to see the current brackets?\"*",
            color=discord.Color.from_rgb(255, 193, 7)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    settings["ceo_tax_brackets"] = brackets
    save_settings(settings)
    
    bracket_range = format_bracket_range(found["min"], found["max"])
    
    embed = discord.Embed(
        title="CEO Tax Bracket Removed",
        description="*The bank teller updates the records...*",
        color=discord.Color.from_rgb(40, 167, 69)
    )
    embed.add_field(
        name="Removed Bracket",
        value=f"```\nBracket: {bracket_range}\nRate: {found['rate']}%\n```",
        inline=False
    )
    embed.add_field(
        name="Confirmation",
        value=f"*\"Done! I've removed the {bracket_range} CEO tax bracket from our system. The remaining brackets are still in place.\"*",
        inline=False
    )
    embed.set_footer(text=f"Authorized by {interaction.user.display_name}")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="set_ceo_salary", description="[ADMIN] Set the CEO salary percentage")
@app_commands.describe(percentage="The new CEO salary percentage (0-100)")
@app_commands.default_permissions(administrator=True)
async def set_ceo_salary(interaction: discord.Interaction, percentage: float):
    if not is_admin(interaction):
        embed = discord.Embed(
            title="Access Restricted",
            description="*The bank teller gives an apologetic smile...*\n\n*\"I'm so sorry, but only authorized administrators can adjust CEO compensation rates. Is there anything else I can help you with today?\"*",
            color=discord.Color.from_rgb(220, 53, 69)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if percentage < 0 or percentage > 100:
        embed = discord.Embed(
            title="Invalid Entry",
            description="*The bank teller tilts her head kindly...*\n\n*\"Hmm, that number doesn't look right! The salary rate should be between 0% and 100%. Want to give it another try?\"*",
            color=discord.Color.from_rgb(255, 193, 7)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    old_rate = settings["ceo_salary_percent"]
    settings["ceo_salary_percent"] = percentage
    save_settings(settings)
    
    embed = discord.Embed(
        title="CEO Salary Rate Updated",
        description="*The bank teller updates the compensation schedule...*",
        color=discord.Color.from_rgb(40, 167, 69)
    )
    embed.add_field(
        name="Changes Applied",
        value=f"```\nPrevious Rate: {old_rate}%\nNew Rate: {percentage}%\n```",
        inline=False
    )
    embed.add_field(
        name="Confirmation",
        value=f"*\"Perfect! I've updated the CEO salary rate from {old_rate}% to {percentage}% of post-tax profit. This will apply to all future calculations.\"*",
        inline=False
    )
    embed.set_footer(text=f"Authorized by {interaction.user.display_name}")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="help_finance", description="View the help guide for the finance calculator")
async def help_finance(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Universalis Bank - Help Guide",
        description="*The bank teller hands you a helpful brochure...*\n\n*\"Here's everything you need to know about our services!\"*",
        color=discord.Color.from_rgb(111, 66, 193)
    )
    
    embed.add_field(
        name="Basic Commands",
        value=(
            "**`/calculate`** - Open the interactive financial calculator\n"
            "**`/view_rates`** - See all current tax brackets and rates\n"
            "**`/help_finance`** - View this help guide"
        ),
        inline=False
    )
    
    embed.add_field(
        name="How to Use /calculate",
        value=(
            "1. Run `/calculate` to open your private calculator\n"
            "2. Click **Add Item** and type item name in chat\n"
            "3. Type the price when prompted\n"
            "4. Type dice type (10, 12, 20, 25, 50, or 100)\n"
            "5. The dice rolls and determines quantity sold!\n"
            "6. Toggle **CEO Salary** and set percentage\n"
            "7. Set your **Business Expenses**\n"
            "8. Click **Calculate** for your financial report\n\n"
            "*Your chat messages are automatically deleted!*"
        ),
        inline=False
    )
    
    embed.add_field(
        name="Admin Commands - Business Tax",
        value=(
            "**`/set_bracket`** - Add/update a business tax bracket\n"
            "**`/remove_bracket`** - Remove a business tax bracket"
        ),
        inline=False
    )
    
    embed.add_field(
        name="Admin Commands - CEO Tax",
        value=(
            "**`/set_ceo_bracket`** - Add/update a CEO income tax bracket\n"
            "**`/remove_ceo_bracket`** - Remove a CEO income tax bracket\n"
            "**`/set_ceo_salary`** - Set maximum CEO salary percentage"
        ),
        inline=False
    )
    
    embed.add_field(
        name="How It Works",
        value=(
            "```\n"
            "1. Add items/services with prices\n"
            "2. Roll dice to determine quantities sold\n"
            "3. Total Revenue = Sum of (price × quantity)\n"
            "4. Net Profit = Revenue - Expenses\n"
            "5. Business Tax (progressive brackets)\n"
            "6. CEO Salary = Your % of allowed rate\n"
            "7. CEO Tax (progressive brackets)\n"
            "8. Final totals calculated\n"
            "```"
        ),
        inline=False
    )
    
    embed.add_field(
        name="Dice Types",
        value=(
            "Choose from these dice for quantity rolls:\n"
            "**d10**: 1-10 units | **d12**: 1-12 units\n"
            "**d20**: 1-20 units | **d25**: 1-25 units\n"
            "**d50**: 1-50 units | **d100**: 1-100 units"
        ),
        inline=False
    )
    
    embed.set_footer(text="Universalis Bank | Here to help your business thrive")
    
    await interaction.response.send_message(embed=embed)

if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("Error: DISCORD_BOT_TOKEN not found in environment variables!")
        print("Please set your Discord bot token in the Secrets tab.")
        exit(1)
    
    print("Starting the Universalis Bank Bot...")
    bot.run(token)

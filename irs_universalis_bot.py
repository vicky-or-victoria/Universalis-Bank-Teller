# Universalis Bank Teller "Kirztin" - v4.7
import os
import json
import asyncio
import random
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict

import discord
from discord.ext import commands, tasks

# ENVIRONMENT
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
FORUM_ID = int(os.getenv("FORUM_ID"))
FINANCE_ROLE_ID = int(os.getenv("FINANCE_ROLE_ID", 0))  # Optional ping role

if not DISCORD_TOKEN or not FORUM_ID:
    raise RuntimeError("Missing required environment variables")

# CONSTANTS
TELLER_NAME = "Kirztin"
INACTIVITY_MINUTES = 10
MAX_MEMORY = 50
DATA_DIR = Path("./data")
DATA_DIR.mkdir(exist_ok=True)

MEMORY_FILE = DATA_DIR / "thread_memory.json"
STATUS_FILE = DATA_DIR / "thread_status.json"
COMPANY_FILE = DATA_DIR / "companies.json"
COMPANY_FILE.touch(exist_ok=True)

memory_lock = asyncio.Lock()
status_lock = asyncio.Lock()
company_lock = asyncio.Lock()

# TAX & CALCULATIONS
TAX_BRACKETS = [
    {"min": 0, "max": 24000, "rate": 0},
    {"min": 24001, "max": 50000, "rate": 5},
    {"min": 50001, "max": 100000, "rate": 15},
    {"min": 100001, "max": 200000, "rate": 25},
    {"min": 200001, "max": 500000, "rate": 30},
    {"min": 500001, "max": None, "rate": 35},
]

def calculate_progressive_tax(amount: float) -> Dict:
    remaining = amount
    total_tax = 0.0
    breakdown = []
    for bracket in TAX_BRACKETS:
        low = bracket["min"]
        high = bracket["max"] or float("inf")
        if amount <= low:
            continue
        taxable = min(remaining, high - low)
        tax = taxable * (bracket["rate"] / 100)
        breakdown.append(f"{taxable:,.2f} @ {bracket['rate']}% = {tax:,.2f}")
        total_tax += tax
        remaining -= taxable
        if remaining <= 0:
            break
    return {"total_tax": total_tax, "breakdown": breakdown}

# UTILITIES
def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r") as f:
        return json.load(f)

def save_json(path: Path, data: dict):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

# EMBED BUILDERS
def generate_financial_embed(company_name, revenue, expenses, tax_info):
    net_profit = revenue - expenses - tax_info["total_tax"]
    embed = discord.Embed(
        title=f"📊 Financial Report: {company_name}",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Gross Revenue", value=f"${revenue:,.2f}", inline=True)
    embed.add_field(name="Expenses", value=f"${expenses:,.2f}", inline=True)
    embed.add_field(name="Taxes", value=f"${tax_info['total_tax']:,.2f}", inline=True)
    embed.add_field(name="Net Profit", value=f"${net_profit:,.2f}", inline=True)
    embed.add_field(name="Tax Breakdown", value="\n".join(tax_info["breakdown"]), inline=False)
    embed.set_footer(text=f"Prepared by {TELLER_NAME}")
    return embed

def generate_stock_embed(company: dict) -> discord.Embed:
    embed = discord.Embed(
        title=f"📈 {company['name']} Stock Info",
        color=discord.Color.green(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Owner", value=f"<@{company['owner_id']}>", inline=True)
    embed.add_field(name="Total Stocks", value=company['total_stocks'], inline=True)
    embed.add_field(name="Owner Stocks", value=company['owner_stocks'], inline=True)
    embed.add_field(name="Available Stocks", value=company['available_stocks'], inline=True)
    embed.add_field(name="Current Stock Price", value=f"${company['stock_price']:.2f}", inline=True)
    buyers = "\n".join([f"<@{uid}>: {qty}" for uid, qty in company.get("buyers", {}).items()]) or "None"
    embed.add_field(name="Stockholders", value=buyers, inline=False)
    return embed

# DISCORD BOT
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="ub!", intents=intents)

# THREAD EVENTS
@bot.event
async def on_thread_create(thread: discord.Thread):
    if thread.parent_id != FORUM_ID:
        return
    async with status_lock:
        status = load_json(STATUS_FILE)
        status[str(thread.id)] = {"last_activity": datetime.utcnow().isoformat(), "closed": False}
        save_json(STATUS_FILE, status)
    async with memory_lock:
        memory = load_json(MEMORY_FILE)
        memory[str(thread.id)] = {"history": [], "mode": "data_collection", "inputs": {}}
        save_json(MEMORY_FILE, memory)
    await thread.send(
        f"**{TELLER_NAME}**: Welcome. Provide your financial request.\n"
        f"Format: Company | Revenue | Expenses\n"
        f"Type **all done** to finalize."
    )

# THREAD MESSAGE HANDLING
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if not isinstance(message.channel, discord.Thread):
        return
    if message.channel.parent_id != FORUM_ID:
        return

    thread_id = str(message.channel.id)

    async with status_lock:
        status = load_json(STATUS_FILE)
        status[thread_id]["last_activity"] = datetime.utcnow().isoformat()
        save_json(STATUS_FILE, status)

    if message.content.lower().strip() == "all done":
        # Ask if the player wants to ping finance role
        await message.channel.send(f"**{TELLER_NAME}**: Would you like to ping the finance role? Reply Yes or No.")

        def check(m):
            return m.author == message.author and m.channel == message.channel

        try:
            reply_msg = await bot.wait_for("message", check=check, timeout=60)
            if reply_msg.content.lower() in ["yes", "y"] and FINANCE_ROLE_ID:
                await message.channel.send(f"<@&{FINANCE_ROLE_ID}>")

            # Rename thread to [CLOSED]
            new_name = f"[CLOSED] {message.channel.name}"
            await message.channel.edit(name=new_name, locked=True)
            async with status_lock:
                status[thread_id]["closed"] = True
                save_json(STATUS_FILE, status)

            await message.channel.send(f"**{TELLER_NAME}**: Request finalized.")
        except:
            await message.channel.send(f"**{TELLER_NAME}**: No response received. Thread finalized without ping.")
        return

    # Financial report processing
    async with memory_lock:
        memory = load_json(MEMORY_FILE)
        thread_memory = memory.get(thread_id, {"history": [], "mode": "data_collection", "inputs": {}})
        history = thread_memory["history"]
        history.append({"role": "user", "content": message.content})
        history = history[-MAX_MEMORY:]
        thread_memory["history"] = history
        memory[thread_id] = thread_memory
        save_json(MEMORY_FILE, memory)

    # Parse input for financial report
    try:
        parts = [p.strip() for p in message.content.split("|")]
        if len(parts) >= 3:
            company_name = parts[0]
            revenue = float(parts[1].replace(",", ""))
            expenses = float(parts[2].replace(",", ""))
            tax_info = calculate_progressive_tax(revenue - expenses)
            embed = generate_financial_embed(company_name, revenue, expenses, tax_info)
            await message.channel.send(embed=embed)
    except:
        pass

# STOCK MARKET COMMANDS
@bot.command(name="ipo")
async def ipo(ctx):
    await ctx.message.delete()
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel
    try:
        await ctx.send(f"**{TELLER_NAME}**: Enter company name for IPO:")
        name_msg = await bot.wait_for("message", check=check, timeout=120)
        company_name = name_msg.content.strip()

        await ctx.send("Enter total number of stocks:")
        total_msg = await bot.wait_for("message", check=check, timeout=120)
        total_stocks = int(total_msg.content.strip())

        await ctx.send("Enter percentage of company you own (e.g., 60):")
        percent_msg = await bot.wait_for("message", check=check, timeout=120)
        owner_percent = float(percent_msg.content.strip())
        owner_stocks = int(total_stocks * (owner_percent / 100))
        available_stocks = total_stocks - owner_stocks

        await ctx.send("Enter initial stock price:")
        price_msg = await bot.wait_for("message", check=check, timeout=120)
        stock_price = float(price_msg.content.strip())

        async with company_lock:
            companies = load_json(COMPANY_FILE)
            companies[company_name] = {
                "name": company_name,
                "owner_id": ctx.author.id,
                "total_stocks": total_stocks,
                "owner_stocks": owner_stocks,
                "available_stocks": available_stocks,
                "stock_price": stock_price,
                "buyers": {}
            }
            save_json(COMPANY_FILE, companies)

        embed = generate_stock_embed(companies[company_name])
        await ctx.send(f"**{TELLER_NAME}**: Company listed successfully.", embed=embed)

    except Exception as e:
        await ctx.send("IPO setup failed. Please try again.")
        print(e)

@bot.command(name="buy")
async def buy_stock(ctx, company_name: str, amount: int):
    async with company_lock:
        companies = load_json(COMPANY_FILE)
        company = companies.get(company_name)
        if not company:
            await ctx.send(f"Company `{company_name}` not found.")
            return
        if amount > company["available_stocks"]:
            await ctx.send(f"Only {company['available_stocks']} stocks available.")
            return
        company["available_stocks"] -= amount
        buyers = company.get("buyers", {})
        buyers[str(ctx.author.id)] = buyers.get(str(ctx.author.id), 0) + amount
        company["buyers"] = buyers
        save_json(COMPANY_FILE, companies)
        embed = generate_stock_embed(company)
        await ctx.send(f"**{TELLER_NAME}**: Stocks purchased successfully.", embed=embed)

@bot.command(name="stocks")
async def stock_info(ctx, company_name: str):
    async with company_lock:
        companies = load_json(COMPANY_FILE)
        company = companies.get(company_name)
        if not company:
            await ctx.send(f"Company `{company_name}` not found.")
            return
        embed = generate_stock_embed(company)
        await ctx.send(embed=embed)

# AUTO-LOCK THREADS
@tasks.loop(minutes=1)
async def auto_lock_threads():
    async with status_lock:
        status = load_json(STATUS_FILE)
        now = datetime.utcnow()
        for thread_id, info in status.items():
            if info.get("closed"):
                continue
            last = datetime.fromisoformat(info["last_activity"])
            if now - last > timedelta(minutes=INACTIVITY_MINUTES):
                thread = bot.get_channel(int(thread_id))
                if thread:
                    await thread.edit(locked=True)
                info["closed"] = True
        save_json(STATUS_FILE, status)

# DAILY STOCK FLUCTUATION
@tasks.loop(hours=24)
async def fluctuate_stock_prices():
    async with company_lock:
        companies = load_json(COMPANY_FILE)
        for company in companies.values():
            change_percent = random.uniform(-0.05, 0.05)
            company["stock_price"] *= 1 + change_percent
        save_json(COMPANY_FILE, companies)

# READY EVENT
@bot.event
async def on_ready():
    auto_lock_threads.start()
    fluctuate_stock_prices.start()
    print(f"{TELLER_NAME} online as {bot.user}")

# RUN
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)

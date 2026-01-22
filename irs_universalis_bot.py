# Universalis Bank Bot v4.5
# Company Financial Reporter + Simple Stock Market

import os
import json
import asyncio
import random
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict

import discord
from discord.ext import commands, tasks

# ------------------ ENVIRONMENT ------------------

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
FORUM_ID = int(os.getenv("FORUM_ID"))
ROLE_ID = int(os.getenv("ROLE_ID"))  # optional role ping when finalized

if not DISCORD_TOKEN or not FORUM_ID:
    raise RuntimeError("Missing required environment variables")

# ------------------ CONSTANTS ------------------

TELLER_NAME = "Kirztin"
INACTIVITY_MINUTES = 10
MAX_MEMORY = 50
STOCK_FLUCTUATION = 0.05  # ±5% per day

DATA_DIR = Path("./data")
DATA_DIR.mkdir(exist_ok=True)

MEMORY_FILE = DATA_DIR / "thread_memory.json"
STATUS_FILE = DATA_DIR / "thread_status.json"
STOCK_FILE = DATA_DIR / "stock_market.json"

memory_lock = asyncio.Lock()
status_lock = asyncio.Lock()
stock_lock = asyncio.Lock()

# ------------------ UTILITIES ------------------

def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r") as f:
        return json.load(f)

def save_json(path: Path, data: dict):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

# ------------------ TAX CALCULATION ------------------

TAX_BRACKETS = [
    {"min": 0, "max": 24_000, "rate": 0},
    {"min": 24_001, "max": 50_000, "rate": 5},
    {"min": 50_001, "max": 100_000, "rate": 15},
    {"min": 100_001, "max": 200_000, "rate": 25},
    {"min": 200_001, "max": 500_000, "rate": 30},
    {"min": 500_001, "max": None, "rate": 35},
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

# ------------------ STOCK MARKET ------------------

DEFAULT_STOCKS = {
    "AAPL": 150.0,
    "TSLA": 700.0,
    "GME": 50.0,
    "ACME": 100.0
}

def initialize_stock_market():
    stocks = load_json(STOCK_FILE)
    if not stocks:
        save_json(STOCK_FILE, DEFAULT_STOCKS)
        return DEFAULT_STOCKS
    return stocks

async def update_stock_market_daily():
    async with stock_lock:
        stocks = load_json(STOCK_FILE)
        for symbol, price in stocks.items():
            change = random.uniform(-STOCK_FLUCTUATION, STOCK_FLUCTUATION)
            stocks[symbol] = round(price * (1 + change), 2)
        save_json(STOCK_FILE, stocks)
        return stocks

def calculate_portfolio_value(holdings: Dict[str, int], stocks: Dict[str, float]) -> float:
    total = 0.0
    for symbol, qty in holdings.items():
        total += qty * stocks.get(symbol, 0)
    return total

# ------------------ EMBED BUILDERS ------------------

def generate_financial_embed(company: str, revenue: float, expenses: float, stocks: Dict[str, int], stock_prices: Dict[str, float]) -> discord.Embed:
    net_income = revenue - expenses
    tax_info = calculate_progressive_tax(net_income)
    stock_value = calculate_portfolio_value(stocks, stock_prices)

    embed = discord.Embed(
        title=f"📊 Financial Report: {company}",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )

    embed.add_field(name="Revenue", value=f"```{revenue:,.2f}```", inline=True)
    embed.add_field(name="Expenses", value=f"```{expenses:,.2f}```", inline=True)
    embed.add_field(name="Net Income", value=f"```{net_income:,.2f}```", inline=False)

    embed.add_field(name="Taxes Breakdown", value="\n".join(tax_info["breakdown"]) + f"\n**Total Tax:** {tax_info['total_tax']:,.2f}", inline=False)

    if stocks:
        portfolio_lines = []
        for sym, qty in stocks.items():
            price = stock_prices.get(sym, 0)
            portfolio_lines.append(f"{sym}: {qty} shares × {price:,.2f} = {qty*price:,.2f}")
        portfolio_lines.append(f"**Total Portfolio Value:** {stock_value:,.2f}")
        embed.add_field(name="Stock Holdings", value="\n".join(portfolio_lines), inline=False)

    embed.set_footer(text=f"Prepared by {TELLER_NAME}")
    return embed

# ------------------ BOT SETUP ------------------

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="ub!", intents=intents)

# ------------------ THREAD MANAGEMENT ------------------

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
        memory[str(thread.id)] = {"history": [], "inputs": {}}
        save_json(MEMORY_FILE, memory)
    await thread.send(f"**{TELLER_NAME}**: Welcome. Please provide your company financial info.\nFormat: `Company | Revenue | Expenses | STOCK:Qty,...`\nType **all done** to finalize.")

# ------------------ MESSAGE HANDLING ------------------

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if not isinstance(message.channel, discord.Thread) or message.channel.parent_id != FORUM_ID:
        return

    thread_id = str(message.channel.id)

    async with status_lock:
        status = load_json(STATUS_FILE)
        status[thread_id]["last_activity"] = datetime.utcnow().isoformat()
        save_json(STATUS_FILE, status)

    # ------------------ FINALIZE ------------------
    if message.content.lower().strip() == "all done":
        # Optional role ping
        await message.channel.send(f"**{TELLER_NAME}**: Would you like to ping the finance role? Reply Yes or No.")

        def check(m):
            return m.author == message.author and m.channel == message.channel

        try:
            reply = await bot.wait_for('message', timeout=60.0, check=check)
            ping_text = f"<@&{ROLE_ID}>" if reply.content.lower() in ["yes", "y"] else ""
        except:
            ping_text = ""

        # Rename thread with [CLOSED]
        new_name = f"[CLOSED] {message.channel.name}" if not message.channel.name.startswith("[CLOSED]") else message.channel.name
        await message.channel.edit(name=new_name, locked=True)
        async with status_lock:
            status[thread_id]["closed"] = True
            save_json(STATUS_FILE, status)
        await message.channel.send(f"**{TELLER_NAME}**: Request finalized. {ping_text}")
        return

    # ------------------ STORE INPUT ------------------
    async with memory_lock:
        memory = load_json(MEMORY_FILE)
        history = memory.get(thread_id, {"history": [], "inputs": {}})
        history["history"].append({"role": "user", "content": message.content})
        history["history"] = history["history"][-MAX_MEMORY:]

        # Parse input for calculation
        try:
            parts = message.content.split("|")
            company = parts[0].strip()
            revenue = float(parts[1].strip())
            expenses = float(parts[2].strip())
            stocks_input = {}
            if len(parts) > 3:
                for s in parts[3].split(","):
                    sym, qty = s.split(":")
                    stocks_input[sym.strip()] = int(qty.strip())
            history["inputs"] = {"company": company, "revenue": revenue, "expenses": expenses, "stocks": stocks_input}
        except:
            pass

        memory[thread_id] = history
        save_json(MEMORY_FILE, memory)

    # ------------------ GENERATE REPORT ------------------
    inputs = history.get("inputs", {})
    if inputs:
        stock_prices = initialize_stock_market()
        embed = generate_financial_embed(
            company=inputs.get("company", "N/A"),
            revenue=inputs.get("revenue", 0),
            expenses=inputs.get("expenses", 0),
            stocks=inputs.get("stocks", {}),
            stock_prices=stock_prices
        )
        await message.channel.send(embed=embed)

# ------------------ AUTO-LOCK THREADS ------------------

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

# ------------------ BOT READY ------------------

@bot.event
async def on_ready():
    await update_stock_market_daily()  # Update stock prices at start
    auto_lock_threads.start()
    print(f"{TELLER_NAME} online as {bot.user}")

# ------------------ START BOT ------------------

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)

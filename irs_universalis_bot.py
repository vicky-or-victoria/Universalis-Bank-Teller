# Universalis Bank Bot "Kirztin" v4.4
# Rigid now

import os
import json
import asyncio
import random
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List

import discord
from discord.ext import commands, tasks

# ENVIRONMENT
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
FORUM_ID = int(os.getenv("FORUM_ID"))
ROLE_ID = int(os.getenv("ROLE_ID"))  # Role to ping when report finalized

if not DISCORD_TOKEN or not FORUM_ID or not ROLE_ID:
    raise RuntimeError("Missing environment variables")

# CONSTANTS
TELLER_NAME = "Kirztin"
INACTIVITY_MINUTES = 10
MAX_MEMORY = 50

DATA_DIR = Path("./data")
DATA_DIR.mkdir(exist_ok=True)

MEMORY_FILE = DATA_DIR / "thread_memory.json"
STATUS_FILE = DATA_DIR / "thread_status.json"
TAX_FILE = DATA_DIR / "tax_brackets.json"
CRYPTO_FILE = DATA_DIR / "crypto_market.json"

memory_lock = asyncio.Lock()
status_lock = asyncio.Lock()
market_lock = asyncio.Lock()

# DEFAULT TAX BRACKETS
DEFAULT_TAX_BRACKETS = [
    {"min": 0, "max": 24000, "rate": 0},
    {"min": 24001, "max": 50000, "rate": 5},
    {"min": 50001, "max": 100000, "rate": 15},
    {"min": 100001, "max": 200000, "rate": 25},
    {"min": 200001, "max": 500000, "rate": 30},
    {"min": 500001, "max": None, "rate": 35},
]

# DEFAULT CRYPTO MARKET
DEFAULT_CRYPTO = {
    "CoinA": {"price": 100.0, "last_update": None},
    "CoinB": {"price": 50.0, "last_update": None},
    "CoinC": {"price": 250.0, "last_update": None},
}

# UTILITIES
def load_json(path: Path):
    if not path.exists():
        return {}
    with open(path, "r") as f:
        return json.load(f)

def save_json(path: Path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

# TAX
def load_tax_brackets():
    data = load_json(TAX_FILE)
    if not data:
        save_json(TAX_FILE, DEFAULT_TAX_BRACKETS)
        return DEFAULT_TAX_BRACKETS
    return data

def calculate_progressive_tax(amount: float, brackets=None):
    brackets = brackets or load_tax_brackets()
    remaining = amount
    total_tax = 0.0
    breakdown = []
    for bracket in brackets:
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

# LOANS
def calculate_loan(principal: float, rate: float, months: int):
    monthly_rate = rate / 100 / 12
    monthly_payment = principal * monthly_rate / (1 - (1 + monthly_rate) ** -months)
    total_paid = monthly_payment * months
    interest_paid = total_paid - principal
    return {
        "monthly_rate": monthly_rate,
        "monthly_payment": monthly_payment,
        "total_paid": total_paid,
        "interest_paid": interest_paid
    }

# CRYPTO MARKET
def load_crypto():
    data = load_json(CRYPTO_FILE)
    if not data:
        save_json(CRYPTO_FILE, DEFAULT_CRYPTO)
        return DEFAULT_CRYPTO
    return data

def save_crypto(data):
    save_json(CRYPTO_FILE, data)

async def update_daily_crypto():
    async with market_lock:
        market = load_crypto()
        for coin, info in market.items():
            change_pct = random.uniform(-0.1, 0.1)  # ±10%
            info["price"] = round(info["price"] * (1 + change_pct), 2)
            info["last_update"] = datetime.utcnow().isoformat()
        save_crypto(market)

# EMBEDS
def generate_transfer_embed(sender, receiver, amount, reason):
    embed = discord.Embed(
        title="💼 Company Transfer Receipt",
        color=discord.Color.green(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Sender", value=f"```{sender}```", inline=True)
    embed.add_field(name="Receiver", value=f"```{receiver}```", inline=True)
    embed.add_field(name="Amount", value=f"```{amount:,.2f}```", inline=False)
    embed.add_field(name="Reason", value=f"```{reason}```", inline=False)
    embed.set_footer(text=f"Processed by {TELLER_NAME}")
    return embed

def generate_financial_report_embed(company_name, revenue, expenses, crypto_holdings=None):
    net_income = revenue - expenses
    tax_data = calculate_progressive_tax(net_income)
    total_tax = tax_data["total_tax"]
    breakdown = "\n".join(tax_data["breakdown"])
    crypto_value = 0.0
    market = load_crypto()
    if crypto_holdings:
        for coin, amount in crypto_holdings.items():
            if coin in market:
                crypto_value += market[coin]["price"] * amount
    embed = discord.Embed(
        title=f"🏦 Financial Report: {company_name}",
        color=discord.Color.gold(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(
        name="Revenue / Expenses",
        value=f"Revenue: {revenue:,.2f}\nExpenses: {expenses:,.2f}\nNet Income: {net_income:,.2f}",
        inline=False
    )
    embed.add_field(
        name="Taxes",
        value=f"Total Tax: {total_tax:,.2f}\nBreakdown:\n{breakdown}",
        inline=False
    )
    if crypto_holdings:
        embed.add_field(
            name="Crypto Assets",
            value=f"Value: {crypto_value:,.2f}\nHoldings: {crypto_holdings}",
            inline=False
        )
    embed.set_footer(text=f"Prepared by {TELLER_NAME}")
    return embed

# BOT SETUP
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="ub!", intents=intents)

# THREAD MANAGEMENT
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
        memory[str(thread.id)] = {"mode": "data_collection", "companies": {}, "history": []}
        save_json(MEMORY_FILE, memory)
    await thread.send(f"🏛️ **{TELLER_NAME}**: Welcome. Please provide your company financial data. Type **all done** to finalize.")

# MESSAGE HANDLING
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not isinstance(message.channel, discord.Thread) or message.channel.parent_id != FORUM_ID:
        return
    thread_id = str(message.channel.id)

    # Update last activity
    async with status_lock:
        status = load_json(STATUS_FILE)
        status[thread_id]["last_activity"] = datetime.utcnow().isoformat()
        save_json(STATUS_FILE, status)

    # Finalize thread
    if message.content.lower().strip() == "all done":
        async with memory_lock:
            memory = load_json(MEMORY_FILE)
            companies = memory.get(thread_id, {}).get("companies", {})
        for name, data in companies.items():
            embed = generate_financial_report_embed(name, data["revenue"], data["expenses"], data.get("crypto"))
            await message.channel.send(embed=embed)
        # Ping role
        await message.channel.send(f"<@&{ROLE_ID}> Financial reports finalized.")
        # Rename thread
        if not message.channel.name.startswith("[CLOSED]"):
            await message.channel.edit(name=f"[CLOSED] {message.channel.name}")
        await message.channel.edit(locked=True)
        async with status_lock:
            status[thread_id]["closed"] = True
            save_json(STATUS_FILE, status)
        async with memory_lock:
            if thread_id in memory:
                memory.pop(thread_id)
                save_json(MEMORY_FILE, memory)
        return

    # Input parsing: expected format -> CompanyName | revenue | expenses | coin:amount,...
    try:
        parts = [p.strip() for p in message.content.split("|")]
        company_name = parts[0]
        revenue = float(parts[1])
        expenses = float(parts[2])
        crypto_holdings = {}
        if len(parts) > 3:
            coins = parts[3].split(",")
            for coin in coins:
                c, amt = coin.split(":")
                crypto_holdings[c.strip()] = float(amt)
    except Exception:
        await message.channel.send("Invalid input format. Example:\n`AcmeCorp | 50000 | 30000 | CoinA:10,CoinB:5`")
        return

    async with memory_lock:
        memory = load_json(MEMORY_FILE)
        thread_memory = memory.get(thread_id, {"mode":"data_collection","companies":{},"history":[]})
        thread_memory["companies"][company_name] = {
            "revenue": revenue,
            "expenses": expenses,
            "crypto": crypto_holdings
        }
        thread_memory["history"].append({"user": message.content})
        memory[thread_id] = thread_memory
        save_json(MEMORY_FILE, memory)
    await message.channel.send(f"Recorded company `{company_name}`. Add more companies or type **all done** to finalize.")

# AUTO-LOCK
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
                    if not thread.name.startswith("[CLOSED]"):
                        await thread.edit(name=f"[CLOSED] {thread.name}")
                    await thread.edit(locked=True)
                info["closed"] = True
        save_json(STATUS_FILE, status)

# DAILY CRYPTO UPDATE
@tasks.loop(hours=24)
async def daily_crypto_update():
    await update_daily_crypto()

# BOT READY
@bot.event
async def on_ready():
    auto_lock_threads.start()
    daily_crypto_update.start()
    print(f"{TELLER_NAME} v4.4 online as {bot.user}")

# START BOT
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)

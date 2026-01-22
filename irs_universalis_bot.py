# Universalis Bank Bot v4.1.2
# Kirztin – Universal Financial Teller (Rigid, Auditable)

import os
import json
import asyncio
import random
from pathlib import Path
from typing import Dict, List
from datetime import datetime, timedelta

import discord
from discord.ext import commands, tasks
import openai

# ENVIRONMENT

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_KEY")
FORUM_ID = int(os.getenv("FORUM_ID"))

if not DISCORD_TOKEN or not OPENAI_KEY or not FORUM_ID:
    raise RuntimeError("Missing required environment variables")

# CONSTANTS

TELLER_NAME = "Kirztin"
INACTIVITY_MINUTES = 10
MAX_MEMORY = 50

DATA_DIR = Path("./data")
DATA_DIR.mkdir(exist_ok=True)

MEMORY_FILE = DATA_DIR / "thread_memory.json"
STATUS_FILE = DATA_DIR / "thread_status.json"

memory_lock = asyncio.Lock()
status_lock = asyncio.Lock()

# OPENAI

client = openai.OpenAI(api_key=OPENAI_KEY)

SYSTEM_PROMPT = f"""
You are {TELLER_NAME}, a regulated bank teller.

STRICT RULES:
- You may calculate numbers.
- You must show calculations step-by-step.
- You must confirm all inputs before calculating.
- You never invent missing values.
- You ask one question at a time.
- You do not roleplay creatively.

MODES:
1) COLLECTING DATA
2) CONFIRMATION
3) CALCULATION
"""

# UTILITIES

def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r") as f:
        return json.load(f)

def save_json(path: Path, data: dict):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

# TAX & DICE

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

        breakdown.append(
            f"{taxable:,.2f} @ {bracket['rate']}% = {tax:,.2f}"
        )

        total_tax += tax
        remaining -= taxable
        if remaining <= 0:
            break

    return {"total_tax": total_tax, "breakdown": breakdown}

def roll_d100() -> int:
    return random.randint(1, 100)

# EMBED BUILDERS

def generate_transfer_embed(sender: str, receiver: str, amount: float, reason: str) -> discord.Embed:
    embed = discord.Embed(
        title="💼 Company Transfer Receipt",
        color=discord.Color.green(),
        timestamp=datetime.utcnow()
    )

    embed.add_field(name="📤 Sender", value=f"```{sender}```", inline=True)
    embed.add_field(name="📥 Receiver", value=f"```{receiver}```", inline=True)
    embed.add_field(name="💰 Amount", value=f"```{amount:,.2f}```", inline=False)
    embed.add_field(name="📝 Reason", value=f"```{reason}```", inline=False)

    embed.set_footer(text=f"Processed by {TELLER_NAME}")
    return embed

def calculate_loan(principal: float, rate: float, months: int) -> Dict:
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

def generate_loan_embed(borrower: str, principal: float, rate: float, months: int) -> discord.Embed:
    loan = calculate_loan(principal, rate, months)

    embed = discord.Embed(
        title="🏦 Loan Approval Summary",
        color=discord.Color.gold(),
        timestamp=datetime.utcnow()
    )

    embed.add_field(
        name="📄 Loan Terms",
        value=(
            "```"
            f"Borrower: {borrower}\n"
            f"Principal: {principal:,.2f}\n"
            f"Rate: {rate}% annually\n"
            f"Duration: {months} months"
            "```"
        ),
        inline=False
    )

    embed.add_field(
        name="📐 Repayment Calculation",
        value=(
            "```"
            f"Monthly Rate: {loan['monthly_rate']:.5f}\n"
            f"Monthly Payment: {loan['monthly_payment']:,.2f}\n"
            f"Total Paid: {loan['total_paid']:,.2f}\n"
            f"Interest Paid: {loan['interest_paid']:,.2f}"
            "```"
        ),
        inline=False
    )

    embed.set_footer(text=f"Prepared by {TELLER_NAME}")
    return embed

# DISCORD BOT

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="ub!", intents=intents)

# EVENTS

@bot.event
async def on_thread_create(thread: discord.Thread):
    if thread.parent_id != FORUM_ID:
        return

    async with status_lock:
        status = load_json(STATUS_FILE)
        status[str(thread.id)] = {
            "last_activity": datetime.utcnow().isoformat(),
            "closed": False
        }
        save_json(STATUS_FILE, status)

    await thread.send(
        f"🏛️ **{TELLER_NAME}**: Please state your request.\n"
        f"_Type **all done** to finalize._"
    )

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
        await message.channel.send(
            f"**{TELLER_NAME}**: This request is finalized. The thread is now locked."
        )
        await message.channel.edit(locked=True)

        async with status_lock:
            status = load_json(STATUS_FILE)
            status[thread_id]["closed"] = True
            save_json(STATUS_FILE, status)
        return

    async with memory_lock:
        memory = load_json(MEMORY_FILE)
        history = memory.get(thread_id, [])
        history.append({"role": "user", "content": message.content})
        memory[thread_id] = history[-MAX_MEMORY:]
        save_json(MEMORY_FILE, memory)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + memory[thread_id]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=400
    )

    reply = response.choices[0].message.content
    await message.channel.send(reply)

    async with memory_lock:
        memory[thread_id].append({"role": "assistant", "content": reply})
        save_json(MEMORY_FILE, memory)

# AUTO-LOCK TASK

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

@bot.event
async def on_ready():
    auto_lock_threads.start()
    print(f"Universalis Bank Bot v4.1.2 online as {bot.user}")

# START

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)

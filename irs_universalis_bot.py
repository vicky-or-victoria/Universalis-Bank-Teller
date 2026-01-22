# Universalis Bank Bot v4.1
# Kirztin – Universal Financial Teller

import os
import json
import asyncio
import random
import re
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta

import discord
from discord.ext import commands, tasks
import openai

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_KEY")
FORUM_ID = int(os.getenv("FORUM_ID"))

if not DISCORD_TOKEN or not OPENAI_KEY:
    raise RuntimeError("Missing required environment variables")

TELLER_NAME = "Kirztin"
INACTIVITY_MINUTES = 10
MAX_MEMORY = 50

DATA_DIR = Path("./data")
DATA_DIR.mkdir(exist_ok=True)

MEMORY_FILE = DATA_DIR / "thread_memory.json"
STATUS_FILE = DATA_DIR / "thread_status.json"

memory_lock = asyncio.Lock()
status_lock = asyncio.Lock()

client = openai.OpenAI(api_key=OPENAI_KEY)

SYSTEM_PROMPT = f"""
You are {TELLER_NAME}, a regulated bank teller.

RULES (STRICT):
- You MAY calculate numbers.
- You MUST show calculations step-by-step.
- You MUST confirm all inputs before calculating.
- You NEVER invent missing values.
- You NEVER skip required fields.
- You ask ONE question at a time.
- You do not roleplay creatively.

You operate in 3 MODES:
1) COLLECTING DATA
2) CONFIRMATION
3) CALCULATION

If data is missing → ask for it.
If data is present → confirm it.
Only calculate after confirmation.
"""

def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r") as f:
        return json.load(f)

def save_json(path: Path, data: dict):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

TAX_BRACKETS = [
    {"min": 0, "max": 100000, "rate": 8},
    {"min": 100001, "max": 500000, "rate": 10},
    {"min": 500001, "max": 1_000_000, "rate": 12},
    {"min": 1_000_001, "max": 10_000_000, "rate": 13},
    {"min": 10_000_001, "max": None, "rate": 15},
]

def calculate_progressive_tax(amount: float) -> Dict:
    remaining = amount
    total_tax = 0
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

    return {
        "total_tax": total_tax,
        "breakdown": breakdown
    }

def roll_d100() -> int:
    return random.randint(1, 100)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="ub!", intents=intents)

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
        f"🏛️ *You approach the bank counter.*\n"
        f"**{TELLER_NAME}**: Please state your request clearly.\n"
        f"_Type **all done** to close this request._"
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

    if message.content.lower().strip() == "all done":
        await message.channel.send(
            f"**{TELLER_NAME}**: Your request is concluded. Thank you."
        )
        return

    async with memory_lock:
        memory = load_json(MEMORY_FILE)
        history = memory.get(thread_id, [])
        history.append({"role": "user", "content": message.content})
        history = history[-MAX_MEMORY:]
        memory[thread_id] = history
        save_json(MEMORY_FILE, memory)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=400
    )

    reply = response.choices[0].message.content

    await message.channel.send(reply)

    async with memory_lock:
        memory = load_json(MEMORY_FILE)
        memory[thread_id].append({"role": "assistant", "content": reply})
        save_json(MEMORY_FILE, memory)

if __name__ == "__main__":
    print("Universalis Bank Bot v4.1 online.")
    bot.run(DISCORD_TOKEN)
def generate_financial_report_embed(
    company: str,
    player: str,
    items: List[dict],
    expenses: float,
    include_ceo: bool,
    ceo_percent: float
) -> discord.Embed:

    embed = discord.Embed(
        title=f"{company} — Financial Report",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )

    sales_lines = []
    gross_revenue = 0

    for item in items:
        roll = roll_d100()
        revenue = roll * item["price"]
        gross_revenue += revenue

        sales_lines.append(
            f"{item['name']}:\n"
            f"Roll: d100 → **{roll}**\n"
            f"{roll} × {item['price']:,.2f} = {revenue:,.2f}"
        )

    embed.add_field(
        name="📦 Sales & Dice Rolls",
        value="```" + "\n\n".join(sales_lines) + "```",
        inline=False
    )

    net_profit = gross_revenue - expenses

    embed.add_field(
        name="📊 Profit Calculation",
        value=(
            "```"
            f"Gross Revenue: {gross_revenue:,.2f}\n"
            f"Expenses:     {expenses:,.2f}\n"
            f"-----------------------------\n"
            f"Net Profit:   {net_profit:,.2f}"
            "```"
        ),
        inline=False
    )

    tax_data = calculate_progressive_tax(net_profit)

    embed.add_field(
        name="🏛️ Progressive Tax Calculation",
        value="```" + "\n".join(tax_data["breakdown"]) +
              f"\n-----------------------------\n"
              f"Total Tax: {tax_data['total_tax']:,.2f}```",
        inline=False
    )

    after_tax = net_profit - tax_data["total_tax"]

    if include_ceo:
        ceo_salary = after_tax * (ceo_percent / 100)
        final_profit = after_tax - ceo_salary

        embed.add_field(
            name="👔 CEO Salary Deduction",
            value=(
                "```"
                f"After-Tax Profit: {after_tax:,.2f}\n"
                f"CEO Rate: {ceo_percent}%\n"
                f"{after_tax:,.2f} × {ceo_percent / 100:.2f}\n"
                f"CEO Salary: {ceo_salary:,.2f}\n"
                f"-----------------------------\n"
                f"Final Profit: {final_profit:,.2f}"
                "```"
            ),
            inline=False
        )
    else:
        embed.add_field(
            name="👔 CEO Salary",
            value="```Not applied```",
            inline=False
        )

    embed.set_footer(text=f"Prepared by {TELLER_NAME} — Universalis Bank")
    return embed

def calculate_loan(principal: float, rate: float, months: int) -> dict:
    monthly_rate = rate / 100 / 12
    monthly_payment = (
        principal * monthly_rate
    ) / (1 - (1 + monthly_rate) ** -months)

    total_paid = monthly_payment * months
    interest_paid = total_paid - principal

    return {
        "monthly_payment": monthly_payment,
        "total_paid": total_paid,
        "interest_paid": interest_paid,
        "monthly_rate": monthly_rate
    }

def generate_loan_embed(
    borrower: str,
    principal: float,
    rate: float,
    months: int
) -> discord.Embed:

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
            f"Interest Rate: {rate}% annually\n"
            f"Duration: {months} months"
            "```"
        ),
        inline=False
    )

    embed.add_field(
        name="📐 Repayment Calculation",
        value=(
            "```"
            f"Monthly Rate: {rate}% ÷ 12 = {loan['monthly_rate']:.5f}\n"
            f"Monthly Payment: {loan['monthly_payment']:,.2f}\n"
            f"Total Paid: {loan['total_paid']:,.2f}\n"
            f"Interest Paid: {loan['interest_paid']:,.2f}"
            "```"
        ),
        inline=False
    )

    embed.set_footer(text=f"Prepared by {TELLER_NAME}")
    return embed

async def generate_transfer_embed(
    sender: str,
    receiver: str,
    amount: float,
    reason: str
) -> discord.Embed:

    embed = discord.Embed(
        title="💼 Company Transfer Receipt",
        color=discord.Color.green(),
        timestamp=datetime.utcnow()
    )

    embed.add_field(
        name="📤 Sender",
        value=f"```{sender}```",
        inline=True
    )

    embed.add_field(
        name="📥 Receiver",
        value=f"```{receiver}```",
        inline=True
    )

    embed.add_field(
        name="💰 Transfer Amount",
        value=f"```{amount:,.2f}```",
        inline=False
    )

    embed.add_field(
        name="📝 Reason",
        value=f"```{reason}```",
        inline=False
    )

    embed.set_footer(text=f"Processed by {TELLER_NAME}")
    return embed


await thread.send(
    embed=generate_transfer_embed(
        sender=session.sender,
        receiver=session.receiver,
        amount=session.amount,
        reason=session.reason
    )
)

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

if message.content.lower().strip() == "all done":
    await message.channel.send(
        f"**{TELLER_NAME}**: This request is finalized. The thread is now locked."
    )
    await message.channel.edit(locked=True)

    async with status_lock:
        status = load_json(STATUS_FILE)
        status[str(message.channel.id)]["closed"] = True
        save_json(STATUS_FILE, status)

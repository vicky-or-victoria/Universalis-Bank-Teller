# Universalis Bank Bot v4.2
# Kirztin – Universalis Bank Teller (Company Financial Reports)

import os
import json
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict

import discord
from discord.ext import commands, tasks
import openai

# ------------------ ENVIRONMENT ------------------
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_KEY")
FORUM_ID = int(os.getenv("FORUM_ID"))
NOTIFY_ROLE_ID = int(os.getenv("NOTIFY_ROLE_ID", 0))  # Discord role to ping (optional)

if not DISCORD_TOKEN or not OPENAI_KEY or not FORUM_ID:
    raise RuntimeError("Missing required environment variables")

# ------------------ CONSTANTS ------------------
TELLER_NAME = "Kirztin"
INACTIVITY_MINUTES = 10
MAX_MEMORY = 50

DATA_DIR = Path("./data")
DATA_DIR.mkdir(exist_ok=True)

MEMORY_FILE = DATA_DIR / "thread_memory.json"
STATUS_FILE = DATA_DIR / "thread_status.json"

memory_lock = asyncio.Lock()
status_lock = asyncio.Lock()

# ------------------ OPENAI SETUP ------------------
client = openai.OpenAI(api_key=OPENAI_KEY)

SYSTEM_PROMPT = f"""
You are {TELLER_NAME}, a Universalis Bank Teller.
You only:
- Collect missing financial inputs from users step by step.
- Confirm all collected inputs with Yes/No.
- Reference Python functions for calculations: calculate_loan(), calculate_progressive_tax().
- Format results into a professional financial report.
Do NOT perform calculations yourself; Python does the math.
"""

# ------------------ UTILITIES ------------------
def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r") as f:
        return json.load(f)

def save_json(path: Path, data: dict):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

# ------------------ CALCULATIONS ------------------
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

# ------------------ EMBED BUILDERS ------------------
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

def generate_tax_embed(company_name: str, revenue: float, expenses: float) -> discord.Embed:
    taxable_income = revenue - expenses
    tax_info = calculate_progressive_tax(taxable_income)
    embed = discord.Embed(
        title=f"📊 Financial Report: {company_name}",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Gross Revenue", value=f"```{revenue:,.2f}```", inline=True)
    embed.add_field(name="Expenses", value=f"```{expenses:,.2f}```", inline=True)
    embed.add_field(name="Taxable Income", value=f"```{taxable_income:,.2f}```", inline=False)
    embed.add_field(
        name="Tax Breakdown",
        value="```" + "\n".join(tax_info["breakdown"]) + "```",
        inline=False
    )
    embed.add_field(name="Total Tax", value=f"```{tax_info['total_tax']:,.2f}```", inline=False)
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
        memory[str(thread.id)] = {"mode": "data_collection", "inputs": {}, "history": [], "notify_role": None}
        save_json(MEMORY_FILE, memory)
    await thread.send(
        f"🏛️ **{TELLER_NAME}**: Welcome. Please provide your financial request. Type **all done** to finalize."
    )

# ------------------ MESSAGE HANDLING ------------------
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if not isinstance(message.channel, discord.Thread):
        return
    if message.channel.parent_id != FORUM_ID:
        return

    thread_id = str(message.channel.id)

    # Update last activity
    async with status_lock:
        status = load_json(STATUS_FILE)
        status[thread_id]["last_activity"] = datetime.utcnow().isoformat()
        save_json(STATUS_FILE, status)

    # Load memory
    async with memory_lock:
        memory = load_json(MEMORY_FILE)
        thread_memory = memory.get(thread_id, {"mode": "data_collection", "inputs": {}, "history": [], "notify_role": None})
        mode = thread_memory["mode"]
        inputs = thread_memory["inputs"]
        history = thread_memory["history"]
        notify_role = thread_memory.get("notify_role")

    # Append user message
    history.append({"role": "user", "content": message.content})
    history = history[-MAX_MEMORY:]
    thread_memory["history"] = history

    # ------------------ FINALIZE THREAD ------------------
    if message.content.lower().strip() == "all done":
        # Ask about pinging the role first
        if NOTIFY_ROLE_ID and notify_role is None:
            thread_memory["mode"] = "ask_ping_role"
            await message.channel.send(
                f"Do you want to notify <@&{NOTIFY_ROLE_ID}>? (Yes/No)"
            )
        else:
            # Lock & close
            thread = message.channel
            original_name = thread.name
            if not original_name.startswith("[CLOSED]"):
                await thread.edit(name=f"[CLOSED] {original_name}", locked=True)
            else:
                await thread.edit(locked=True)
            async with status_lock:
                status = load_json(STATUS_FILE)
                status[thread_id]["closed"] = True
                save_json(STATUS_FILE, status)
            # Ping role if set
            if notify_role:
                await thread.send(f"<@&{NOTIFY_ROLE_ID}> This thread has been finalized.")
        # Save memory
        async with memory_lock:
            memory[thread_id] = thread_memory
            save_json(MEMORY_FILE, memory)
        return

    # ------------------ ASK PING ROLE ------------------
    if mode == "ask_ping_role":
        if message.content.lower() in ["yes", "y"]:
            thread_memory["notify_role"] = True
        else:
            thread_memory["notify_role"] = False
        # Lock thread & rename
        thread = message.channel
        original_name = thread.name
        if not original_name.startswith("[CLOSED]"):
            await thread.edit(name=f"[CLOSED] {original_name}", locked=True)
        else:
            await thread.edit(locked=True)
        # Ping role if confirmed
        if thread_memory["notify_role"] and NOTIFY_ROLE_ID:
            await thread.send(f"<@&{NOTIFY_ROLE_ID}> This thread has been finalized.")
        async with status_lock:
            status = load_json(STATUS_FILE)
            status[thread_id]["closed"] = True
            save_json(STATUS_FILE, status)
        # Reset memory
        thread_memory = {"mode": "data_collection", "inputs": {}, "history": [], "notify_role": None}
        async with memory_lock:
            memory[thread_id] = thread_memory
            save_json(MEMORY_FILE, memory)
        return

    # ------------------ MODE: DATA COLLECTION ------------------
    if mode == "data_collection":
        # Ask GPT for missing inputs
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=400
        )
        reply = response.choices[0].message.content
        await message.channel.send(reply)

        # Detect if GPT says "all inputs collected"
        if "all inputs collected" in reply.lower():
            thread_memory["mode"] = "confirmation"

    # ------------------ MODE: CONFIRMATION ------------------
    elif mode == "confirmation":
        if message.content.lower() in ["yes", "y"]:
            thread_memory["mode"] = "calculation"
            await message.channel.send(f"**{TELLER_NAME}**: Inputs confirmed. Performing calculations.")
        elif message.content.lower() in ["no", "n"]:
            thread_memory["mode"] = "data_collection"
            await message.channel.send(f"**{TELLER_NAME}**: Please provide missing inputs again.")
        else:
            await message.channel.send("Please reply with **Yes** or **No**.")

    # ------------------ MODE: CALCULATION ------------------
    elif mode == "calculation":
        # Python performs actual calculations
        if inputs.get("type") == "loan":
            borrower = inputs.get("borrower", "N/A")
            principal = float(inputs.get("principal", 0))
            rate = float(inputs.get("rate", 0))
            months = int(inputs.get("months", 1))
            embed = generate_loan_embed(borrower, principal, rate, months)
            await message.channel.send(embed=embed)
        elif inputs.get("type") == "transfer":
            sender = inputs.get("sender", "N/A")
            receiver = inputs.get("receiver", "N/A")
            amount = float(inputs.get("amount", 0))
            reason = inputs.get("reason", "")
            embed = generate_transfer_embed(sender, receiver, amount, reason)
            await message.channel.send(embed=embed)
        elif inputs.get("type") == "tax_report":
            company_name = inputs.get("company_name", "N/A")
            revenue = float(inputs.get("revenue", 0))
            expenses = float(inputs.get("expenses", 0))
            embed = generate_tax_embed(company_name, revenue, expenses)
            await message.channel.send(embed=embed)

        # Reset memory
        thread_memory = {"mode": "data_collection", "inputs": {}, "history": [], "notify_role": None}

    # Save memory
    async with memory_lock:
        memory[thread_id] = thread_memory
        save_json(MEMORY_FILE, memory)

# ------------------ AUTO-LOCK INACTIVE THREADS ------------------
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
                    original_name = thread.name
                    if not original_name.startswith("[CLOSED]"):
                        await thread.edit(name=f"[CLOSED] {original_name}", locked=True)
                    else:
                        await thread.edit(locked=True)
                info["closed"] = True
        save_json(STATUS_FILE, status)

# ------------------ BOT READY ------------------
@bot.event
async def on_ready():
    auto_lock_threads.start()
    print(f"{TELLER_NAME} online as {bot.user}")

# ------------------ START BOT ------------------
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)

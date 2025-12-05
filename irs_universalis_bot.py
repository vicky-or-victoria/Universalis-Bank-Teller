# irs_universalis_bot.py (v3.0) - Kirztin, thread-based OpenAI-powered bank teller

import os
import json
import re
import random
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict

import discord
from discord.ext import commands, tasks
import openai


# Configuration & settings
OPENAI_KEY = os.getenv("OPENAI_KEY")
ROLE_ID_SECRET = os.getenv("ROLE_ID")
FORUM_ID_SECRET = os.getenv("FORUM_ID")

if not OPENAI_KEY:
    raise RuntimeError("OPENAI_KEY environment variable is required.")
if not ROLE_ID_SECRET:
    raise RuntimeError("ROLE_ID environment variable is required.")
if not FORUM_ID_SECRET:
    raise RuntimeError("FORUM_ID environment variable is required.")

try:
    BANK_MANAGER_ROLE_ID = int(ROLE_ID_SECRET)
    WATCH_FORUM_ID = int(FORUM_ID_SECRET)
except ValueError:
    raise RuntimeError("ROLE_ID and FORUM_ID must be numeric IDs (strings that parse to int).")

openai.api_key = OPENAI_KEY

# Basic settings and defaults (from your prior implementation)
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
TELLER_NAME = "Kirztin"


# Load/save settings
def load_settings():
    if Path(SETTINGS_FILE).exists():
        try:
            with open(SETTINGS_FILE, "r") as f:
                data = json.load(f)
            # ensure keys exist
            data.setdefault("tax_brackets", DEFAULT_SETTINGS["tax_brackets"])
            data.setdefault("ceo_salary_percent", DEFAULT_SETTINGS["ceo_salary_percent"])
            data.setdefault("ceo_tax_brackets", DEFAULT_SETTINGS["ceo_tax_brackets"])
            return data
        except Exception:
            return DEFAULT_SETTINGS.copy()
    return DEFAULT_SETTINGS.copy()

def save_settings(s):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(s, f, indent=2)

settings = load_settings()


# Utilities
def format_money(amount: float) -> str:
    return f"${amount:,.2f}"

def create_divider() -> str:
    return "─" * 30

def calculate_progressive_tax(amount: float, brackets: list):
    if amount <= 0:
        return 0.0, []
    total_tax = 0.0
    breakdown = []
    sorted_brackets = sorted(brackets, key=lambda x: x["min"])
    for bracket in sorted_brackets:
        bmin = bracket["min"]
        bmax = bracket["max"] if bracket["max"] is not None else float('inf')
        rate = bracket["rate"]
        if amount <= bmin:
            continue
        if bmax == float('inf'):
            taxable = max(0, amount - bmin)
        else:
            upper = min(amount, bmax)
            taxable = max(0, upper - bmin)
        if taxable > 0:
            tax = taxable * (rate / 100)
            total_tax += tax
            breakdown.append({"min": bmin, "max": bmax, "rate": rate, "taxable": taxable, "tax": tax})
    return total_tax, breakdown

def roll_dice(sides: int) -> int:
    return random.randint(1, sides)


# Thread session management
class ThreadSession:
    def __init__(self, thread: discord.Thread, starter: Optional[discord.Member]):
        self.thread = thread
        self.thread_id = thread.id
        self.starter = starter
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.timeout_minutes = 30
        self.state = "AWAITING_CHOICE"  # or COMPANY_TAX, COMPANY_TRANSFER, LOAN, FINISHED
        self.substate = None
        # Data
        self.company = {"company_name": None, "player_name": None, "income": None, "expenses": None, "period": None, "modifiers": None}
        self.transfer = {"source": None, "destination": None, "amount": None, "reason": None}
        self.loan = {"player_name": None, "amount": None, "purpose": None, "collateral": None}
        # keep original messages if needed
        self.messages = []

    def touch(self):
        self.last_activity = datetime.utcnow()

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.last_activity + timedelta(minutes=self.timeout_minutes)

class ThreadSessionManager:
    def __init__(self):
        self.sessions: Dict[int, ThreadSession] = {}

    def create(self, thread: discord.Thread, starter: Optional[discord.Member]) -> ThreadSession:
        s = ThreadSession(thread, starter)
        self.sessions[thread.id] = s
        return s

    def get(self, thread_id: int) -> Optional[ThreadSession]:
        s = self.sessions.get(thread_id)
        if s and s.is_expired():
            del self.sessions[thread_id]
            return None
        return s

    def remove(self, thread_id: int):
        if thread_id in self.sessions:
            del self.sessions[thread_id]

    def cleanup(self):
        expired = [tid for tid, s in self.sessions.items() if s.is_expired()]
        for tid in expired:
            del self.sessions[tid]

thread_manager = ThreadSessionManager()


# OpenAI
async def ask_openai_for_intent(user_message: str) -> dict:
    """
    Uses OpenAI to interpret the user's message and return a dict with:
    {
      "intent": "tax" | "transfer" | "loan" | "other",
      "fields": { ... }  # optional parsed details like amount, company_name, source, destination
    }
    The assistant is instructed to respond with JSON only.
    """
    system_prompt = (
        "You are a helpful assistant that extracts structured intent from a single user message "
        "for a banking NPC named Kirztin. Return a JSON object and nothing else, with keys: "
        "\"intent\" (one of 'tax','transfer','loan','choice','finish','unknown'), "
        "\"choice\" when the user replies with a simple letter/word choice (A/B/etc), "
        "and \"fields\" containing any detected structured fields. "
        "Fields examples: company_name, player_name, income, expenses, period, modifiers, "
        "source, destination, amount, reason, collateral, purpose. "
        "Use simple values for amounts (numbers only). If you cannot parse, set intent to 'unknown'."
    )

    user_prompt = (
        "User message:\n---\n" + user_message + "\n---\n"
        "Return JSON only. Example outputs:\n"
        '{"intent":"tax","fields":{"company_name":"IronWorks","player_name":"Thane","income":12000,"expenses":3000}}\n'
        '{"intent":"transfer","fields":{"source":"IronWorks","destination":"Thane","amount":2500,"reason":"payout"}}'
    )

    try:
        resp = await openai.ChatCompletion.acreate(
            model="gpt-4o-mini",  # if this model isn't available in your environment, change to a supported model
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=400,
            temperature=0.0,
        )
        text = resp.choices[0].message.content.strip()
        # Attempt to extract JSON from the response
        # Some models may include surrounding text — find first and last curly braces
        json_text = text
        # if there are code fences, strip them
        json_text = re.sub(r"^```(?:json)?\n", "", json_text)
        json_text = re.sub(r"\n```$", "", json_text)
        # attempt to find first { and last }
        first = json_text.find("{")
        last = json_text.rfind("}")
        if first != -1 and last != -1:
            json_text = json_text[first:last+1]
        parsed = json.loads(json_text)
        return parsed
    except Exception as e:
        # fallback: return unknown
        return {"intent": "unknown", "fields": {}}


# Report generators
def generate_tax_report_embed(company_data: dict) -> discord.Embed:
    income = float(company_data.get("income") or 0.0)
    expenses = float(company_data.get("expenses") or 0.0)
    company_name = company_data.get("company_name") or "Unknown Company"
    player_name = company_data.get("player_name") or "Unknown"
    period = company_data.get("period") or "Period"

    net_profit = income - expenses

    embed = discord.Embed(
        title=f"UNIVERSALIS BANK — Tax Assessment Report",
        description=f"*{TELLER_NAME} prepares your tax assessment for {company_name} ({player_name}) — {period}*",
        color=discord.Color.from_rgb(255, 193, 7),
        timestamp=datetime.utcnow()
    )

    embed.add_field(
        name="Overview",
        value=(
            f"**Company:** {company_name}\n"
            f"**Client:** {player_name}\n"
            f"**Period:** {period}\n"
            f"**Gross Income:** {format_money(income)}\n"
            f"**Expenses:** {format_money(expenses)}\n"
        ),
        inline=False
    )

    if net_profit <= 0:
        embed.add_field(
            name="Result",
            value=f"Net Profit: {format_money(net_profit)}\n\n*No business income tax applies when there is no profit.*",
            inline=False
        )
        embed.set_footer(text=f"Teller: {TELLER_NAME} | Universalis Bank")
        return embed

    business_tax, breakdown = calculate_progressive_tax(net_profit, settings["tax_brackets"])
    profit_after_tax = net_profit - business_tax

    # build breakdown string
    btxt = ""
    for b in breakdown:
        rng = f"${b['min']:,.0f}" + (f" - ${b['max']:,.0f}" if b["max"] != float('inf') and b["max"] is not None else "+")
        btxt += f"{rng} @ {b['rate']}%\n   Tax: {format_money(b['tax'])}\n"
    btxt += f"\nTotal Business Tax: {format_money(business_tax)}"

    embed.add_field(name="Tax Calculation", value=f"```\nNet Profit: {format_money(net_profit)}\n\n{btxt}\n```", inline=False)
    embed.add_field(name="After Tax", value=f"```\nProfit After Tax: {format_money(profit_after_tax)}\n```", inline=False)
    embed.set_footer(text=f"Teller: {TELLER_NAME} | Universalis Bank")
    return embed

def generate_transfer_report_embed(transfer: dict) -> discord.Embed:
    src = transfer.get("source") or "Unknown"
    dst = transfer.get("destination") or "Unknown"
    amount = float(transfer.get("amount") or 0.0)
    reason = transfer.get("reason") or "No reason provided"
    e = discord.Embed(
        title="UNIVERSALIS BANK — Transfer Report",
        description=f"*{TELLER_NAME} processes the transfer...*",
        color=discord.Color.from_rgb(0, 123, 255),
        timestamp=datetime.utcnow()
    )
    e.add_field(name="Details", value=f"**From:** {src}\n**To:** {dst}\n**Amount:** {format_money(amount)}\n**Reason:** {reason}\n", inline=False)
    e.add_field(name="Status", value="✔️ Completed", inline=False)
    e.set_footer(text=f"Teller: {TELLER_NAME} | Universalis Bank")
    return e

def generate_loan_notice_embed(loan: dict, requester: discord.Member) -> discord.Embed:
    pname = loan.get("player_name") or "Unknown"
    amount = float(loan.get("amount") or 0.0)
    purpose = loan.get("purpose") or "No purpose given"
    collateral = loan.get("collateral") or "None"
    e = discord.Embed(
        title="UNIVERSALIS BANK — Loan Request",
        description="*A loan request has been submitted and requires manager attention.*",
        color=discord.Color.from_rgb(220, 53, 69),
        timestamp=datetime.utcnow()
    )
    e.add_field(name="Requester", value=f"{pname} ({requester.display_name})", inline=False)
    e.add_field(name="Amount", value=format_money(amount), inline=True)
    e.add_field(name="Purpose", value=purpose, inline=True)
    e.add_field(name="Collateral", value=collateral, inline=False)
    e.set_footer(text=f"Teller: {TELLER_NAME} | Universalis Bank")
    return e


# Intents & Bot init
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.messages = True

bot = commands.Bot(command_prefix="!", intents=intents)


# Background cleanup
@tasks.loop(minutes=5.0)
async def cleanup_sessions_task():
    thread_manager.cleanup()


# BOT EVENTS
@bot.event
async def on_ready():
    # Start background tasks here (safe to create tasks once the loop exists)
    if not cleanup_sessions_task.is_running():
        cleanup_sessions_task.start()
    print(f"{bot.user} is ready. Watching forum id {WATCH_FORUM_ID} for thread creations.")

@bot.event
async def on_thread_create(thread: discord.Thread):
    # only respond to the configured forum channel
    parent = getattr(thread, "parent", None)
    if not parent:
        return
    # parent.id is the forum channel id in API v2
    try:
        if parent.id != WATCH_FORUM_ID:
            return
    except Exception:
        return

    # get starter if possible
    starter = None
    if hasattr(thread, "owner_id") and thread.owner_id:
        try:
            starter = thread.guild.get_member(thread.owner_id) or await thread.guild.fetch_member(thread.owner_id)
        except Exception:
            starter = None

    # create session
    session = thread_manager.create(thread, starter)

    greeting = (
        f"👋 **Welcome to Universalis Bank.**\n"
        f"I am **{TELLER_NAME}**, your virtual bank teller. How may I assist you today?\n\n"
        f"Please reply in this thread with what you need (examples):\n"
        f"- \"Calculate company taxes for [CompanyName]: income 12k, expenses 3k\"\n"
        f"- \"Transfer 2.5k from CompanyName to PlayerName for payout\"\n"
        f"- \"Request a loan of 5k for colony expansion\"\n\n"
        f"I can understand natural requests — just type them and I'll respond."
    )
    try:
        await thread.send(greeting)
    except Exception:
        try:
            await parent.send(greeting)
        except Exception:
            pass

@bot.event
async def on_message(message: discord.Message):
    # Let commands still work
    await bot.process_commands(message)

    if message.author.bot:
        return

    channel = message.channel
    if not isinstance(channel, discord.Thread):
        return

    session = thread_manager.get(channel.id)
    if not session:
        return

    # Only let the starter or an admin operate the session
    if session.starter and message.author.id != session.starter.id:
        member = message.author
        if message.guild and isinstance(member, discord.Member) and member.guild_permissions.administrator:
            pass
        else:
            try:
                await channel.send("*Kirztin says: Only the thread starter may interact with this session, or ask an admin for assistance.*")
            except Exception:
                pass
            return

    session.touch()
    session.messages.append((message.author.id, message.content, datetime.utcnow()))

    # Use OpenAI to parse intent
    parsed = await ask_openai_for_intent(message.content)
    intent = parsed.get("intent", "unknown")
    fields = parsed.get("fields", {})

    # If the user sends a single-letter choice like "A" or "B", treat appropriately
    lower = message.content.strip().lower()
    if lower in ("a", "b", "company", "loan", "tax", "transfer", "calculate", "finish"):
        # map simple keywords
        if lower in ("a", "company"):
            intent = "choice"
            fields = {"choice": "company"}
        elif lower in ("b", "loan"):
            intent = "choice"
            fields = {"choice": "loan"}
        elif "tax" in lower or "calculate" in lower:
            intent = "tax"
        elif "transfer" in lower:
            intent = "transfer"
        elif lower in ("finish", "calculate"):
            intent = "finish"

    # Branch on intent
    if intent == "choice" and fields.get("choice") == "company":
        session.state = "AWAITING_COMPANY_SUBCHOICE"
        await channel.send("*\"Company Services — would you like 'tax' (calculate taxes) or 'transfer' (company transfer)?\"*")
        return

    if intent == "tax":
        # Fields may already contain data parsed by OpenAI; ask follow-ups for missing fields
        session.state = "COMPANY_TAX"
        # fill fields into session.company where present
        if "company_name" in fields:
            session.company["company_name"] = fields["company_name"]
        if "player_name" in fields:
            session.company["player_name"] = fields["player_name"]
        if "income" in fields:
            try:
                session.company["income"] = float(fields["income"])
            except Exception:
                session.company["income"] = None
        if "expenses" in fields:
            try:
                session.company["expenses"] = float(fields["expenses"])
            except Exception:
                session.company["expenses"] = None
        if "period" in fields:
            session.company["period"] = fields["period"]

        # ask for any missing required field in turn
        if not session.company["company_name"]:
            session.substate = "ASK_COMPANY_NAME"
            await channel.send("*\"What's the company name?\"*")
            return
        if not session.company["player_name"]:
            session.substate = "ASK_PLAYER_NAME"
            await channel.send("*\"What's the character/player name for this company?\"*")
            return
        if session.company["income"] is None:
            session.substate = "ASK_INCOME"
            await channel.send("*\"What is the gross income for the period? (e.g., 12k or 12000)\"*")
            return
        if session.company["expenses"] is None:
            session.substate = "ASK_EXPENSES"
            await channel.send("*\"How much in expenses? (enter 0 if none)\"*")
            return
        # all present -> generate report
        embed = generate_tax_report_embed(session.company)
        await channel.send(embed=embed)
        session.state = "FINISHED"
        thread_manager.remove(channel.id)
        return

    if session.state == "COMPANY_TAX":
        # we're mid-flow for a tax collection — check substate to accept answers
        if session.substate == "ASK_COMPANY_NAME":
            session.company["company_name"] = message.content.strip()
            session.substate = None
            await channel.send(f"*\"Recorded company: **{session.company['company_name']}**. Now what's the player name?\"*")
            return
        if session.substate == "ASK_PLAYER_NAME":
            session.company["player_name"] = message.content.strip()
            session.substate = None
            await channel.send(f"*\"Recorded player: **{session.company['player_name']}**. Now enter gross income (e.g., 12k).\"*")
            return
        if session.substate == "ASK_INCOME":
            # parse money
            parsed = None
            try:
                parsed = parse_money_local(message.content)
            except Exception:
                parsed = None
            if parsed is None:
                await channel.send("*\"I couldn't parse that amount — please use formats like 12k, 12000, or $12,000.\"*")
                return
            session.company["income"] = parsed
            await channel.send(f"*\"Income recorded: {format_money(parsed)}. How much are expenses?\"*")
            return
        if session.substate == "ASK_EXPENSES":
            parsed = parse_money_local(message.content)
            if parsed is None:
                await channel.send("*\"I couldn't parse that amount — please use formats like 5k, 5000, or $5,000.\"*")
                return
            session.company["expenses"] = parsed
            # done -> generate report
            embed = generate_tax_report_embed(session.company)
            await channel.send(embed=embed)
            session.state = "FINISHED"
            thread_manager.remove(channel.id)
            return

    if intent == "transfer":
        session.state = "COMPANY_TRANSFER"
        # Accept fields if present
        if "source" in fields:
            session.transfer["source"] = fields["source"]
        if "destination" in fields:
            session.transfer["destination"] = fields["destination"]
        if "amount" in fields:
            try:
                session.transfer["amount"] = float(fields["amount"])
            except Exception:
                session.transfer["amount"] = None
        if "reason" in fields:
            session.transfer["reason"] = fields["reason"]
        # ask for missing data
        if not session.transfer["source"]:
            session.substate = "ASK_TRANSFER_SOURCE"
            await channel.send("*\"Who is the source of funds? (e.g., CompanyName or PlayerName)\"*")
            return
        if not session.transfer["destination"]:
            session.substate = "ASK_TRANSFER_DEST"
            await channel.send("*\"Who is the destination? (e.g., CompanyName or PlayerName)\"*")
            return
        if session.transfer["amount"] is None:
            session.substate = "ASK_TRANSFER_AMOUNT"
            await channel.send("*\"How much should be transferred?\"*")
            return
        # all present -> perform transfer (report only)
        embed = generate_transfer_report_embed(session.transfer)
        await channel.send(embed=embed)
        session.state = "FINISHED"
        thread_manager.remove(channel.id)
        return

    if session.state == "COMPANY_TRANSFER":
        if session.substate == "ASK_TRANSFER_SOURCE":
            session.transfer["source"] = message.content.strip()
            session.substate = None
            await channel.send(f"*\"Source recorded: {session.transfer['source']}. Now who is the destination?\"*")
            return
        if session.substate == "ASK_TRANSFER_DEST":
            session.transfer["destination"] = message.content.strip()
            session.substate = None
            await channel.send(f"*\"Destination recorded: {session.transfer['destination']}. How much to transfer?\"*")
            return
        if session.substate == "ASK_TRANSFER_AMOUNT":
            parsed = parse_money_local(message.content)
            if parsed is None:
                await channel.send("*\"I couldn't parse that amount — please use formats like 2.5k or 2500.\"*")
                return
            session.transfer["amount"] = parsed
            # ask for reason
            await channel.send("*\"Recorded amount. Any reason or note for the transfer? If none, reply 'none'.\"*")
            session.substate = "ASK_TRANSFER_REASON"
            return
        if session.substate == "ASK_TRANSFER_REASON":
            session.transfer["reason"] = message.content.strip()
            embed = generate_transfer_report_embed(session.transfer)
            await channel.send(embed=embed)
            session.state = "FINISHED"
            thread_manager.remove(channel.id)
            return

    if intent == "loan":
        session.state = "LOAN"
        if "player_name" in fields:
            session.loan["player_name"] = fields["player_name"]
        if "amount" in fields:
            try:
                session.loan["amount"] = float(fields["amount"])
            except Exception:
                session.loan["amount"] = None
        if "purpose" in fields:
            session.loan["purpose"] = fields["purpose"]
        if "collateral" in fields:
            session.loan["collateral"] = fields["collateral"]

        if session.loan["player_name"] is None:
            session.substate = "ASK_LOAN_NAME"
            await channel.send("*\"Who is requesting the loan? (player/character name)\"*")
            return
        if session.loan["amount"] is None:
            session.substate = "ASK_LOAN_AMOUNT"
            await channel.send("*\"How much is being requested?\"*")
            return
        if session.loan["purpose"] is None:
            session.substate = "ASK_LOAN_PURPOSE"
            await channel.send("*\"What is the purpose of the loan?\"*")
            return
        if session.loan["collateral"] is None:
            session.substate = "ASK_LOAN_COLLATERAL"
            await channel.send("*\"Any collateral? If none, reply 'none'.\"*")
            return
        # all present -> create notice and ping bank manager role
        embed = generate_loan_notice_embed(session.loan, message.author)
        try:
            await channel.send(content=f"<@&{BANK_MANAGER_ROLE_ID}> A loan request needs review.", embed=embed)
        except Exception:
            await channel.send(embed=embed)
        session.state = "FINISHED"
        thread_manager.remove(channel.id)
        return

    # mid-flow loan responses:
    if session.state == "LOAN":
        if session.substate == "ASK_LOAN_NAME":
            session.loan["player_name"] = message.content.strip()
            session.substate = None
            await channel.send("*\"Name recorded. How much would you like to request?\"*")
            return
        if session.substate == "ASK_LOAN_AMOUNT":
            parsed = parse_money_local(message.content)
            if parsed is None:
                await channel.send("*\"I couldn't parse that amount — try formats like 5k or 5000.\"*")
                return
            session.loan["amount"] = parsed
            session.substate = None
            await channel.send("*\"Amount recorded. What's the purpose of the loan?\"*")
            return
        if session.substate == "ASK_LOAN_PURPOSE":
            session.loan["purpose"] = message.content.strip()
            session.substate = "ASK_LOAN_COLLATERAL"
            await channel.send("*\"Collateral? If none, reply 'none'.\"*")
            return
        if session.substate == "ASK_LOAN_COLLATERAL":
            session.loan["collateral"] = message.content.strip()
            embed = generate_loan_notice_embed(session.loan, message.author)
            try:
                await channel.send(content=f"<@&{BANK_MANAGER_ROLE_ID}> A loan request needs review.", embed=embed)
            except Exception:
                await channel.send(embed=embed)
            session.state = "FINISHED"
            thread_manager.remove(channel.id)
            return

    # If nothing matched, provide a helpful fallback
    await channel.send("*\"I'm sorry — I couldn't interpret that. Please tell me if you want taxes, a transfer, or a loan. Example: 'Calculate taxes for IronWorks — income 12k, expenses 3k'\"*")


# small local money parser (fallback)
def parse_money_local(text: str) -> Optional[float]:
    if not text:
        return None
    t = text.strip().lower()
    t = t.replace('$', '').replace('uc', '')
    match = re.search(r'([0-9]+(?:[.,][0-9]+)?)(\s*[km])?', t)
    if not match:
        return None
    num_str = match.group(1).replace(',', '')
    suffix = (match.group(2) or "").strip()
    try:
        val = float(num_str)
    except Exception:
        return None
    if suffix == 'k':
        val *= 1_000
    elif suffix == 'm':
        val *= 1_000_000
    return val


# Example slash command kept: view_rates
@bot.tree.command(name="view_rates", description="View the current tax brackets and CEO salary rates")
async def view_rates(interaction: discord.Interaction):
    business_brackets = settings["tax_brackets"]
    ceo_brackets = settings["ceo_tax_brackets"]
    ceo_rate = settings["ceo_salary_percent"]

    embed = discord.Embed(
        title="Universalis Bank - Tax Rate Schedule",
        description=f"*{TELLER_NAME} pulls up the current rates with a helpful smile...*",
        color=discord.Color.from_rgb(0, 123, 255)
    )

    business_text = ""
    for bracket in sorted(business_brackets, key=lambda x: x["min"]):
        business_text += f"{format_bracket_range(bracket['min'], bracket['max'])}: {bracket['rate']}%\n"

    embed.add_field(name="Business Income Tax Brackets", value=f"```\n{business_text}```", inline=False)

    ceo_text = ""
    for bracket in sorted(ceo_brackets, key=lambda x: x["min"]):
        ceo_text += f"{format_bracket_range(bracket['min'], bracket['max'])}: {bracket['rate']}%\n"

    embed.add_field(name="CEO Income Tax Brackets", value=f"```\n{ceo_text}```", inline=False)
    embed.add_field(name="CEO Salary Rate", value=f"```\n{ceo_rate}% of post-tax business profit\n```", inline=False)
    embed.set_footer(text=f"Teller: {TELLER_NAME} | Universalis Bank")
    await interaction.response.send_message(embed=embed, ephemeral=True)

def format_bracket_range(min_val, max_val):
    if max_val is None or max_val == float('inf'):
        return f"${min_val:,.0f}+"
    return f"${min_val:,.0f} - ${max_val:,.0f}"


# Run
if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("Error: DISCORD_BOT_TOKEN not found in environment variables!")
        raise SystemExit(1)
    print("Starting Universalis Bank Bot v3.0 (Kirztin)...")
    bot.run(token)
        self.transfer_data = {
            "source": None,
            "destination": None,
            "amount": None,
            "reason": None
        }
        self.loan_data = {
            "player_name": None,
            "amount": None,
            "purpose": None,
            "collateral": None
        }

    def touch(self):
        self.last_activity = datetime.utcnow()

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.last_activity + timedelta(minutes=self.timeout_minutes)

class ThreadSessionManager:
    def __init__(self):
        self.sessions: Dict[int, ThreadSession] = {}

    def create_session(self, thread: discord.Thread, author: discord.Member) -> ThreadSession:
        session = ThreadSession(thread, author)
        self.sessions[thread.id] = session
        return session

    def get_session(self, thread_id: int) -> Optional[ThreadSession]:
        session = self.sessions.get(thread_id)
        if session and session.is_expired():
            del self.sessions[thread_id]
            return None
        return session

    def remove_session(self, thread_id: int):
        if thread_id in self.sessions:
            del self.sessions[thread_id]

    def cleanup_expired(self):
        expired = [tid for tid, s in self.sessions.items() if s.is_expired()]
        for tid in expired:
            del self.sessions[tid]

thread_manager = ThreadSessionManager()

def parse_money(text: str) -> Optional[float]:
    """
    Parse common money formats like "5k", "2,500", "$3,200.50", "1200"
    Returns float or None if cannot parse.
    """
    if not text:
        return None
    text = text.strip().lower()
    # Replace currency symbols
    text = text.replace('$', '').replace('uc', '').strip()
    # Shorthand: 2k, 1.5m
    match = re.match(r'^([0-9,.]*\d)(\s*[km])?$', text)
    if match:
        num_str = match.group(1).replace(',', '')
        suffix = match.group(2)
        try:
            val = float(num_str)
            if suffix:
                suffix = suffix.strip()
                if suffix == 'k':
                    val *= 1_000
                elif suffix == 'm':
                    val *= 1_000_000
            return val
        except ValueError:
            return None
    # Try to extract a number anywhere in the string
    match_any = re.search(r'([0-9][0-9,\.]*\d)', text)
    if match_any:
        try:
            return float(match_any.group(1).replace(',', ''))
        except ValueError:
            return None
    return None

def parse_choice(text: str) -> str:
    """
    Return a normalized choice token from text.
    """
    t = text.strip().lower()
    if t in ("a", "a)", "company", "company services", "company service", "company transaction", "company transactions", "services"):
        return "A"
    if t in ("b", "b)", "loan", "loan request", "request loan", "loans"):
        return "B"
    if "tax" in t or "calculate" in t or "taxes" in t:
        return "TAX"
    if "transfer" in t or "move" in t:
        return "TRANSFER"
    if t in ("finish", "done", "calculate", "report", "end"):
        return "FINISH"
    return ""

def parse_dice(text: str) -> Optional[int]:
    """
    Extract a dice value like d20, 20, d100 from user text.
    """
    if not text:
        return None
    m = re.search(r'd\s*([0-9]{1,3})', text.lower())
    if m:
        val = int(m.group(1))
        if val in DICE_OPTIONS:
            return val
    m2 = re.search(r'\b(' + '|'.join(str(x) for x in DICE_OPTIONS) + r')\b', text)
    if m2:
        return int(m2.group(1))
    return None

def generate_tax_report_embed(company_data: dict) -> discord.Embed:
    """
    Generate a tax report embed using the same tax logic from the original calculator,
    but using provided company_data: income, expenses, ceo salary handling not required here.
    """
    income = company_data.get("income") or 0.0
    expenses = company_data.get("expenses") or 0.0
    company_name = company_data.get("company_name") or "Unknown Company"
    player_name = company_data.get("player_name") or "Unknown"
    period = company_data.get("period") or "Period"

    gross_profit = income
    gross_expenses = expenses
    net_profit = gross_profit - gross_expenses

    embed = discord.Embed(
        title=f"UNIVERSALIS BANK — Tax Assessment Report",
        description=f"*Kirztin prepares your tax assessment for {company_name} ({player_name}) — {period}*",
        color=discord.Color.from_rgb(255, 193, 7),
        timestamp=datetime.utcnow()
    )

    embed.add_field(
        name="Overview",
        value=(
            f"**Company:** {company_name}\n"
            f"**Client:** {player_name}\n"
            f"**Period:** {period}\n"
            f"**Gross Income:** {format_money(gross_profit)}\n"
            f"**Expenses:** {format_money(gross_expenses)}\n"
        ),
        inline=False
    )

    if net_profit <= 0:
        embed.add_field(
            name="Result",
            value=(
                f"Net Profit: {format_money(net_profit)}\n\n"
                "*No business income tax applies when there is no profit.*"
            ),
            inline=False
        )
        embed.set_footer(text=f"Teller: {TELLER_NAME} | Universalis Bank")
        return embed

    business_tax, business_breakdown = calculate_progressive_tax(net_profit, settings["tax_brackets"])
    profit_after_tax = net_profit - business_tax

    business_tax_text = ""
    for item in business_breakdown:
        bracket_range = format_bracket_range(item["min"], item["max"])
        business_tax_text += f"{bracket_range} @ {item['rate']}%\n   Tax: {format_money(item['tax'])}\n"
    business_tax_text += f"\nTotal Business Tax: {format_money(business_tax)}"

    embed.add_field(
        name="Tax Calculation",
        value=f"```\nNet Profit: {format_money(net_profit)}\n\n{business_tax_text}\n```",
        inline=False
    )

    embed.add_field(
        name="After Tax",
        value=(
            f"```\n"
            f"Profit After Tax: {format_money(profit_after_tax)}\n"
            f"```"
        ),
        inline=False
    )

    embed.set_footer(text=f"Teller: {TELLER_NAME} | Universalis Bank")
    return embed

def generate_transfer_report_embed(transfer_data: dict) -> discord.Embed:
    src = transfer_data.get("source") or "Unknown"
    dst = transfer_data.get("destination") or "Unknown"
    amount = transfer_data.get("amount") or 0.0
    reason = transfer_data.get("reason") or "No reason provided"
    embed = discord.Embed(
        title="UNIVERSALIS BANK — Transfer Report",
        description=f"*Kirztin processes the transfer...*",
        color=discord.Color.from_rgb(0, 123, 255),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Details", value=(
        f"**From:** {src}\n"
        f"**To:** {dst}\n"
        f"**Amount:** {format_money(amount)}\n"
        f"**Reason:** {reason}\n"
    ), inline=False)
    embed.add_field(name="Status", value="✔️ Completed", inline=False)
    embed.set_footer(text=f"Teller: {TELLER_NAME} | Universalis Bank")
    return embed

def generate_loan_notice_embed(loan_data: dict, requester: discord.Member) -> discord.Embed:
    player_name = loan_data.get("player_name") or "Unknown"
    amount = loan_data.get("amount") or 0.0
    purpose = loan_data.get("purpose") or "No purpose given"
    collateral = loan_data.get("collateral") or "None"
    embed = discord.Embed(
        title="UNIVERSALIS BANK — Loan Request",
        description=f"*A loan request has been submitted and requires manager attention.*",
        color=discord.Color.from_rgb(220, 53, 69),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Requester", value=f"{player_name} ({requester.display_name})", inline=False)
    embed.add_field(name="Amount", value=format_money(amount), inline=True)
    embed.add_field(name="Purpose", value=purpose, inline=True)
    embed.add_field(name="Collateral", value=collateral, inline=False)
    embed.set_footer(text=f"Teller: {TELLER_NAME} | Universalis Bank")
    return embed

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True
intents.members = True
intents.reactions = True
intents.integrations = True
intents.dm_messages = True
intents.typing = False

bot = commands.Bot(command_prefix="!", intents=intents)

@tasks.loop(minutes=5.0)
async def cleanup_sessions():
    thread_manager.cleanup_expired()

@cleanup_sessions.before_loop
async def before_cleanup_sessions():
    await bot.wait_until_ready()

@bot.event
async def on_ready():
    if not cleanup_sessions.is_running():
        cleanup_sessions.start()
    print("Bot is ready.")

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
async def on_thread_create(thread: discord.Thread):
    # Only react to threads created in Forum channels (thread.parent.type == forum)
    try:
        parent = thread.parent
    except AttributeError:
        parent = None

    if parent is None:
        return

    # Check parent is a forum channel or thread is a public/private thread created from a forum post
    if getattr(parent, "type", None) != discord.ChannelType.forum:
        return

    # Attempt to get the user who started the thread (creator)
    starter = None
    # thread.owner_id is available on Thread objects; try to resolve Member
    if hasattr(thread, "owner_id") and thread.owner_id:
        try:
            guild = thread.guild
            starter = guild.get_member(thread.owner_id) or await guild.fetch_member(thread.owner_id)
        except Exception:
            starter = None

    # Create a ThreadSession and greet
    if starter:
        session = thread_manager.create_session(thread, starter)
    else:
        # If we cannot resolve starter, still create session with author=None
        session = thread_manager.create_session(thread, None)

    # Kirztin greeting with options
    greeting = (
        f"👋 **Welcome to Universalis Bank.**\n"
        f"I am **{TELLER_NAME}**, your virtual bank teller. How may I assist you today?\n\n"
        f"Please reply in this thread with one of the choices below:\n"
        f"**A)** Company Services — tax calculation or company transfer\n"
        f"**B)** Loan Request — request a loan (a Bank Manager will be notified)\n\n"
        f"You can reply with `A` or `B`, or write the words (e.g., 'company' or 'loan')."
    )

    try:
        await thread.send(greeting)
    except Exception:
        # fallback: try to send to parent channel
        try:
            await parent.send(greeting)
        except Exception:
            pass

@bot.event
async def on_message(message: discord.Message):
    # let commands process as well
    await bot.process_commands(message)

    # Ignore messages from bots
    if message.author.bot:
        return

    # Only handle messages in threads
    if not message.channel or not isinstance(message.channel, discord.Thread):
        return

    thread = message.channel
    session = thread_manager.get_session(thread.id)
    # If no session existed, ignore (we only trigger on thread_create)
    if not session:
        return

    # Ensure only the thread starter or an admin interacts with the session (admins can assist)
    if session.author and message.author.id != session.author.id:
        # Allow admins to interact (guild admins)
        member = message.author
        if message.guild and isinstance(member, discord.Member) and member.guild_permissions.administrator:
            pass
        else:
            # Ignore other users
            try:
                await message.reply("*Kirztin says: Please let the original requester interact with this session, or ask an admin for help.*", mention_author=False)
            except Exception:
                pass
            return

    session.touch()
    content = message.content.strip()

    # Normalize quick choices
    choice = parse_choice(content)

    # State machine
    if session.state == "AWAITING_CHOICE":
        if choice == "A":
            session.state = "COMPANY_MENU"
            await thread.send(f"*\"Excellent. Company Services it is. Would you like 'tax' (calculate taxes) or 'transfer' (company transfer)?\"*")
            return
        elif choice == "B":
            session.state = "LOAN_COLLECTING"
            session.substate = "ASK_NAME"
            await thread.send(f"*\"A loan request — understood. To begin, what's your character name?\"*")
            return
        else:
            # Try to interpret full-text choices
            if "company" in content.lower():
                session.state = "COMPANY_MENU"
                await thread.send(f"*\"Excellent. Company Services it is. Would you like 'tax' (calculate taxes) or 'transfer' (company transfer)?\"*")
                return
            if "loan" in content.lower():
                session.state = "LOAN_COLLECTING"
                session.substate = "ASK_NAME"
                await thread.send(f"*\"A loan request — understood. To begin, what's your character name?\"*")
                return
            await thread.send(f"*\"I'm sorry, I didn't quite catch that. Please reply with `A` for Company Services or `B` for Loan Request.\"*")
            return

    # Company menu
    if session.state == "COMPANY_MENU":
        if choice == "TAX":
            session.state = "TAX_COLLECTING"
            session.substate = "ASK_COMPANY"
            await thread.send(f"*\"Very well — Tax calculation. What is the company name?\"*")
            return
        elif choice == "TRANSFER":
            session.state = "TRANSFER_COLLECTING"
            session.substate = "ASK_SOURCE"
            await thread.send(f"*\"Understood — Company Transfer. Who is the source of funds? (e.g., CompanyName or PlayerName)\"*")
            return
        else:
            # Try to detect keywords
            low = content.lower()
            if "tax" in low or "calculate" in low:
                session.state = "TAX_COLLECTING"
                session.substate = "ASK_COMPANY"
                await thread.send(f"*\"Very well — Tax calculation. What is the company name?\"*")
                return
            if "transfer" in low or "move" in low:
                session.state = "TRANSFER_COLLECTING"
                session.substate = "ASK_SOURCE"
                await thread.send(f"*\"Understood — Company Transfer. Who is the source of funds? (e.g., CompanyName or PlayerName)\"*")
                return
            await thread.send(f"*\"Please specify 'tax' or 'transfer' so I know which service to perform.\"*")
            return

    # TAX collection flows
    if session.state == "TAX_COLLECTING":
        sub = session.substate
        if sub == "ASK_COMPANY":
            session.company_data["company_name"] = content.strip()
            session.substate = "ASK_PLAYER"
            await thread.send(f"*\"Recorded company name as **{session.company_data['company_name']}**. What is the character/player name?\"*")
            return
        if sub == "ASK_PLAYER":
            session.company_data["player_name"] = content.strip()
            session.substate = "ASK_INCOME"
            await thread.send(f"*\"Great. What is the gross income for the period? (e.g., 12000 or 12k)\"*")
            return
        if sub == "ASK_INCOME":
            parsed = parse_money(content)
            if parsed is None:
                await thread.send(f"*\"I couldn't parse that amount — please enter a number like 12000 or 12k (you may use 'k' or 'm').\"*")
                return
            session.company_data["income"] = parsed
            session.substate = "ASK_EXPENSES"
            await thread.send(f"*\"Income recorded: {format_money(parsed)}. What are the total expenses? (enter 0 if none)\"*")
            return
        if sub == "ASK_EXPENSES":
            parsed = parse_money(content)
            if parsed is None:
                await thread.send(f"*\"I couldn't parse that amount — please enter a number like 5000 or 5k.\"*")
                return
            session.company_data["expenses"] = parsed
            session.substate = "ASK_PERIOD"
            await thread.send(f"*\"Expenses recorded: {format_money(parsed)}. What is the fiscal period? (e.g., 'This month', 'Q3 1425')\"*")
            return
        if sub == "ASK_PERIOD":
            session.company_data["period"] = content.strip()
            session.substate = "ASK_MODIFIERS"
            await thread.send(f"*\"Any modifiers or special notes? (e.g., 'charity deduction 10%' or reply 'no')\"*")
            return
        if sub == "ASK_MODIFIERS":
            session.company_data["modifiers"] = content.strip()
            # Completed gathering data. Provide summary and instructions to 'calculate'
            summary = (
                f"**Summary so far:**\n"
                f"- Company: {session.company_data['company_name']}\n"
                f"- Player: {session.company_data['player_name']}\n"
                f"- Income: {format_money(session.company_data['income'])}\n"
                f"- Expenses: {format_money(session.company_data['expenses'])}\n"
                f"- Period: {session.company_data['period']}\n"
                f"- Modifiers: {session.company_data['modifiers']}\n\n"
                f"Type `calculate` or `finish` to get the full tax report."
            )
            session.substate = "READY"
            await thread.send(f"*\"All set. {summary}\"*")
            return

    # TRANSFER collection flows
    if session.state == "TRANSFER_COLLECTING":
        sub = session.substate
        if sub == "ASK_SOURCE":
            session.transfer_data["source"] = content.strip()
            session.substate = "ASK_DEST"
            await thread.send(f"*\"Source recorded: {session.transfer_data['source']}. Who is the destination?\"*")
            return
        if sub == "ASK_DEST":
            session.transfer_data["destination"] = content.strip()
            session.substate = "ASK_AMOUNT"
            await thread.send(f"*\"Destination recorded: {session.transfer_data['destination']}. How much would you like to transfer?\"*")
            return
        if sub == "ASK_AMOUNT":
            parsed = parse_money(content)
            if parsed is None:
                await thread.send(f"*\"I couldn't parse that amount — please enter a number like 12000 or 12k.\"*")
                return
            session.transfer_data["amount"] = parsed
            session.substate = "ASK_REASON"
            await thread.send(f"*\"Amount recorded: {format_money(parsed)}. Any reason/notes for the transfer? (or 'none')\"*")
            return
        if sub == "ASK_REASON":
            session.transfer_data["reason"] = content.strip()
            session.substate = "READY"
            await thread.send(f"*\"Transfer details recorded. Type `finish` to process and see the transfer report.*\"")
            return

    # LOAN collection flows
    if session.state == "LOAN_COLLECTING":
        sub = session.substate
        if sub == "ASK_NAME":
            session.loan_data["player_name"] = content.strip()
            session.substate = "ASK_AMOUNT"
            await thread.send(f"*\"Thanks. How much would you like to request as a loan?\"*")
            return
        if sub == "ASK_AMOUNT":
            parsed = parse_money(content)
            if parsed is None:
                await thread.send(f"*\"I couldn't parse that amount — please enter a number like 12000 or 12k.\"*")
                return
            session.loan_data["amount"] = parsed
            session.substate = "ASK_PURPOSE"
            await thread.send(f"*\"Amount noted: {format_money(parsed)}. What's the purpose of the loan?\"*")
            return
        if sub == "ASK_PURPOSE":
            session.loan_data["purpose"] = content.strip()
            session.substate = "ASK_COLLATERAL"
            await thread.send(f"*\"Any collateral to list? If none, reply 'none'.\"*")
            return
        if sub == "ASK_COLLATERAL":
            session.loan_data["collateral"] = content.strip()
            # Completed loan request
            embed = generate_loan_notice_embed(session.loan_data, message.author)
            notice = f"<@&{BANK_MANAGER_ROLE_ID}> — A new loan request requires your attention."
            await thread.send(content=notice, embed=embed)
            session.state = "FINISHED"
            return

    # READY / FINISH handling
    if session.substate == "READY" or choice == "FINISH":
        if session.state == "TAX_COLLECTING" or session.state == "COMPANY_MENU":
            # Generate tax report
            embed = generate_tax_report_embed(session.company_data)
            await thread.send(embed=embed)
            session.state = "FINISHED"
            thread_manager.remove_session(thread.id)
            return
        if session.state == "TRANSFER_COLLECTING":
            embed = generate_transfer_report_embed(session.transfer_data)
            await thread.send(embed=embed)
            session.state = "FINISHED"
            thread_manager.remove_session(thread.id)
            return

    # If we get here, message didn't match expected flow
    await thread.send(f"*\"I'm not sure how to handle that message in the current step. Please follow the prompts, or type 'finish' to end and see the report.\"*")

@bot.tree.command(name="view_rates", description="View the current tax brackets and CEO salary rates")
async def view_rates(interaction: discord.Interaction):
    business_brackets = settings["tax_brackets"]
    ceo_brackets = settings["ceo_tax_brackets"]
    ceo_rate = settings["ceo_salary_percent"]
    
    embed = discord.Embed(
        title="Universalis Bank - Tax Rate Schedule",
        description=f"*{TELLER_NAME} pulls up the current rates with a helpful smile...*\n\n*\"Here's our complete tax structure!\"*",
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
    
    embed.set_footer(text="Use /calculate to run your private calculator!")
    
    await interaction.response.send_message(embed=embed)

if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("Error: DISCORD_BOT_TOKEN not found in environment variables!")
        print("Please set your Discord bot token in the Secrets tab.")
        exit(1)
    
    print("Starting the Universalis Bank Bot v3.0...")
    bot.run(token)

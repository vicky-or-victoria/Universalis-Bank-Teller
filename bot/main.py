import os
import logging
from dotenv import load_dotenv

import discord
from discord.ext import commands

from bot.data.store import Database

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
FORUM_ID = os.getenv("FORUM_ID")  # optional here; will be saved into DB if present
TEST_GUILD_ID = os.getenv("TEST_GUILD_ID")  # optional: use for fast slash sync (guild id)

if not DISCORD_TOKEN:
    raise RuntimeError("Missing required environment variable DISCORD_BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ubteller")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="ub!", intents=intents, help_command=None)

# Database singleton
DB_PATH = "data/universalis.db"
db = Database(DB_PATH)

@bot.event
async def on_ready():
    await db.initialize()
    # If FORUM_ID or FINANCE_ROLE_ID provided via env, persist them to the DB config table
    if FORUM_ID:
        await db.set_config("FORUM_ID", FORUM_ID)
        logger.info(f"Saved FORUM_ID from env to DB: {FORUM_ID}")
    finance_id = os.getenv("FINANCE_ROLE_ID")
    if finance_id:
        await db.set_config("FINANCE_ROLE_ID", finance_id)
        logger.info("Saved FINANCE_ROLE_ID from env to DB")

    # load cogs
    extensions = (
        "bot.cogs.threads",
        "bot.cogs.financial",
        "bot.cogs.stocks",
        "bot.cogs.admin",
    )
    for ext in extensions:
        try:
            bot.load_extension(ext)
            logger.info(f"Loaded extension {ext}")
        except Exception:
            logger.exception(f"Failed to load extension {ext}")

    # Fast guild sync for app commands (if TEST_GUILD_ID provided)
    try:
        if TEST_GUILD_ID:
            guild = discord.Object(id=int(TEST_GUILD_ID))
            await bot.tree.sync(guild=guild)
            logger.info(f"Synced app commands to test guild {TEST_GUILD_ID}")
        else:
            # fallback to global sync; may take up to 1 hour to update
            await bot.tree.sync()
            logger.info("Synced global app commands")
    except Exception:
        logger.exception("Slash command sync failed")

    logger.info(f"Bot ready: {bot.user}")


def main():
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
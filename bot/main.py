import discord
from discord.ext import commands
import aiosqlite
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True


class TradingBot(commands.Bot):
    def __init__(self, owner_ids=None):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
            owner_ids=owner_ids,
        )
        self.db = None

    async def setup_hook(self):
        """Initialize database and load cogs"""
        os.makedirs("data", exist_ok=True)

        # Connect to database
        self.db = await aiosqlite.connect("data/trading_bot.db")
        await self.init_database()

        # Load all cogs
        cogs = [
            "cogs.chatgpt_responder",
            "cogs.financial_reports",
            "cogs.stock_market",
        ]

        for cog in cogs:
            try:
                await self.load_extension(cog)
                print(f"✓ Loaded {cog}")
            except Exception as e:
                print(f"✗ Failed to load {cog}: {e}")

        # Sync slash commands
        await self.tree.sync()
        print("✓ Synced slash commands")

    async def init_database(self):
        """Initialize database tables"""
        async with self.db.cursor() as cursor:
            # Companies table
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS companies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    owner_id INTEGER NOT NULL,
                    balance REAL DEFAULT 0,
                    is_public BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Financial reports table
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER NOT NULL,
                    items_sold TEXT NOT NULL,
                    gross_profit REAL NOT NULL,
                    net_profit REAL NOT NULL,
                    reported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (company_id) REFERENCES companies(id)
                )
            """)

            # Stocks table
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS stocks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER NOT NULL,
                    ticker TEXT UNIQUE NOT NULL,
                    price REAL NOT NULL,
                    available_shares INTEGER NOT NULL,
                    total_shares INTEGER NOT NULL,
                    FOREIGN KEY (company_id) REFERENCES companies(id)
                )
            """)

            # Holdings table
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS holdings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    stock_id INTEGER NOT NULL,
                    shares INTEGER NOT NULL,
                    FOREIGN KEY (stock_id) REFERENCES stocks(id),
                    UNIQUE(user_id, stock_id)
                )
            """)

            # Users table
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    balance REAL DEFAULT 50000
                )
            """)

            await self.db.commit()

    async def close(self):
        """Cleanup on shutdown"""
        if self.db:
            await self.db.close()
        await super().close()


# Replace this with your Discord user ID
bot = TradingBot(owner_ids={795733380532404224})


@bot.event
async def on_ready():
    print(f"✓ {bot.user} is ready!")
    print(f"✓ Connected to {len(bot.guilds)} guild(s)")


async def main():
    try:
        await bot.start(os.getenv("DISCORD_TOKEN"))
    except KeyboardInterrupt:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())

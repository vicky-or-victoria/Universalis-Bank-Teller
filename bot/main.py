import discord
from discord.ext import commands
import asyncpg
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
            command_prefix="ub!",
            intents=intents,
            help_command=None,
            owner_ids=owner_ids,
        )
        self.db = None

    async def setup_hook(self):
        """Initialize database and load cogs"""
        # Connect to PostgreSQL database
        database_url = os.getenv("DATABASE_URL")
        
        if not database_url:
            print("❌ DATABASE_URL not found in environment variables!")
            return
        
        # Fix for some platforms that use postgres:// instead of postgresql://
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        
        try:
            self.db = await asyncpg.create_pool(database_url)
            print("✓ Connected to PostgreSQL database")
        except Exception as e:
            print(f"❌ Failed to connect to database: {e}")
            return
        
        await self.init_database()

        # Load all cogs
        cogs = [
            "cogs.chatgpt_responder",
            "cogs.financial_reports",
            "cogs.stock_market",
            "cogs.francesca_control",
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
        async with self.db.acquire() as conn:
            # Companies table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS companies (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    owner_id BIGINT NOT NULL,
                    balance DECIMAL(15, 2) DEFAULT 0,
                    is_public BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Financial reports table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER NOT NULL,
                    items_sold TEXT NOT NULL,
                    gross_profit DECIMAL(15, 2) NOT NULL,
                    net_profit DECIMAL(15, 2) NOT NULL,
                    reported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (company_id) REFERENCES companies(id)
                )
            """)

            # Stocks table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS stocks (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER NOT NULL,
                    ticker TEXT UNIQUE NOT NULL,
                    price DECIMAL(15, 2) NOT NULL,
                    available_shares INTEGER NOT NULL,
                    total_shares INTEGER NOT NULL,
                    FOREIGN KEY (company_id) REFERENCES companies(id)
                )
            """)

            # Holdings table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS holdings (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    stock_id INTEGER NOT NULL,
                    shares INTEGER NOT NULL,
                    FOREIGN KEY (stock_id) REFERENCES stocks(id),
                    UNIQUE(user_id, stock_id)
                )
            """)

            # Users table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    balance DECIMAL(15, 2) DEFAULT 50000
                )
            """)
            
            print("✓ Database tables initialized")

    async def close(self):
        """Cleanup on shutdown"""
        if self.db:
            await self.db.close()
        await super().close()


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

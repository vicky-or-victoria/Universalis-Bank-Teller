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
            print("✅ Connected to PostgreSQL database")
        except Exception as e:
            print(f"❌ Failed to connect to database: {e}")
            return
        
        await self.init_database()

        # Load all cogs 
        cogs = [
            "cogs.help_system",
            "cogs.chatgpt_responder",
            "cogs.company_management",
            "cogs.report_filing",
            "cogs.stock_market",
            "cogs.francesca_control",
            "cogs.short_selling",
            "cogs.tax_system",
            "cogs.admin_company_tools",
            "cogs.leaderboard",
        ]

        for cog in cogs:
            try:
                await self.load_extension(cog)
                print(f"✅ Loaded {cog}")
            except Exception as e:
                print(f"❌ Failed to load {cog}: {e}")

        # Sync slash commands
        await self.tree.sync()
        print("✅ Synced slash commands")

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
                    ceo_salary_percent DECIMAL(5, 2) DEFAULT 5.00,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Financial reports table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER NOT NULL,
                    items_sold TEXT NOT NULL,
                    gross_revenue DECIMAL(15, 2) NOT NULL,
                    gross_expenses_percent DECIMAL(5, 2) NOT NULL,
                    gross_expenses DECIMAL(15, 2) NOT NULL,
                    gross_profit DECIMAL(15, 2) NOT NULL,
                    corporate_tax DECIMAL(15, 2) NOT NULL,
                    ceo_salary DECIMAL(15, 2) NOT NULL,
                    personal_tax DECIMAL(15, 2) NOT NULL,
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

            # Holdings table (for long positions)
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

            # Short positions table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS short_positions (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    stock_id INTEGER NOT NULL,
                    shares INTEGER NOT NULL,
                    entry_price DECIMAL(15, 2) NOT NULL,
                    opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (stock_id) REFERENCES stocks(id),
                    UNIQUE(user_id, stock_id)
                )
            """)

            # Users table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    balance DECIMAL(15, 2) DEFAULT 25000
                )
            """)
            
            # Tax brackets table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS tax_brackets (
                    id SERIAL PRIMARY KEY,
                    min_income DECIMAL(15, 2) NOT NULL,
                    max_income DECIMAL(15, 2),
                    rate DECIMAL(5, 4) NOT NULL,
                    bracket_order INTEGER NOT NULL
                )
            """)
            
            # Initialize default progressive tax brackets if empty
            bracket_count = await conn.fetchval("SELECT COUNT(*) FROM tax_brackets")
            if bracket_count == 0:
                # Default US-style progressive brackets
                await conn.execute("""
                    INSERT INTO tax_brackets (min_income, max_income, rate, bracket_order) VALUES
                    (0, 10000, 0.10, 1),
                    (10000, 40000, 0.12, 2),
                    (40000, 85000, 0.22, 3),
                    (85000, 160000, 0.24, 4),
                    (160000, 200000, 0.32, 5),
                    (200000, 500000, 0.35, 6),
                    (500000, NULL, 0.37, 7)
                """)
            
            # Trade cooldowns table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS trade_cooldowns (
                    user_id BIGINT NOT NULL,
                    ticker TEXT NOT NULL,
                    last_trade TIMESTAMP NOT NULL,
                    PRIMARY KEY (user_id, ticker)
                )
            """)
            
            print("✅ Database tables initialized")

    async def close(self):
        """Cleanup on shutdown"""
        if self.db:
            await self.db.close()
        await super().close()


bot = TradingBot(owner_ids={795733380532404224})


@bot.event
async def on_ready():
    print(f"✅ {bot.user} is ready!")
    print(f"✅ Connected to {len(bot.guilds)} guild(s)")


async def main():
    try:
        await bot.start(os.getenv("DISCORD_TOKEN"))
    except KeyboardInterrupt:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())

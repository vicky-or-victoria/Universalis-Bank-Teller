# Universalis Bank Teller (refactor)

Features:
- Automatic responses to players in a specific forum channel when they create threads or post messages.
- Financial report parsing (Format: Company | Revenue | Expenses) with progressive tax calculation and an embed response.
- Simple IPO / buy / stocks market with persistent SQLite storage.
- Background tasks: auto-lock inactive threads and daily stock price fluctuation.
- Modular design using cogs, async SQLite (aiosqlite), and environment configuration (.env).

Getting started:
1. Copy `.env.example` to `.env` and fill the values (DISCORD_BOT_TOKEN, FORUM_ID, optionally FINANCE_ROLE_ID).
2. Install dependencies: `pip install -r requirements.txt`
3. Run: `python -m bot.main`

Notes:
- Commands use the `ub!` prefix for backward compatibility. Many commands are hybrid (work as slash commands too).
- Storage is a SQLite database at `data/universalis.db`.

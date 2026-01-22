# Universalis Bank Teller (refactor)

Features:
- Automatic responses to players in a specific forum channel when they create threads or post messages.
- Financial report parsing (Format: Company | Revenue | Expenses) with progressive tax calculation and an embed response.
- Simple IPO / buy / stocks market with persistent SQLite storage.
- Background tasks: auto-lock inactive threads and daily stock price fluctuation.
- Modular design using cogs, async SQLite (aiosqlite), and environment configuration (.env).

Notes:
- Commands use the `ub!` prefix for backward compatibility. Many commands are hybrid (work as slash commands too).
- Storage is a SQLite database at `data/universalis.db`.

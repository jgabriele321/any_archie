# AnyArchie

A multi-tenant personal assistant service powered by Telegram and Claude.

Users message a central "Hub" bot to get started, go through a conversational onboarding, and receive their own personal assistant bot.

## Features

- **Task Management** - Add, view, and complete tasks
- **Reminders** - Natural language reminder scheduling
- **Conversational AI** - Chat naturally with Claude
- **Web Search** - Search the web via Exa
- **Personal Context** - Stores goals, focus, and preferences
- **PDF Exports** - Weekly summaries and task lists

## Quick Start

### 1. Prerequisites

- Python 3.10+
- PostgreSQL 14+
- Telegram Bot tokens (create via @BotFather)
- OpenRouter API key
- Exa API key (for web search)

### 2. Create Telegram Bots

1. Message @BotFather on Telegram
2. Create a "Hub" bot: `/newbot` → name it something like "AnyArchie Hub"
3. Create 5-10 user bots: `/newbot` → name them "AnyArchie 1", "AnyArchie 2", etc.
4. Save all the tokens

### 3. Set Up Database

```bash
# Install PostgreSQL if needed
brew install postgresql  # macOS
# or
sudo apt install postgresql  # Ubuntu

# Create database
createdb anyarchie

# Run schema
psql anyarchie < schema.sql
```

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env with your values
```

Required variables:
- `DATABASE_URL` - PostgreSQL connection string
- `OPENROUTER_API_KEY` - Your OpenRouter key
- `EXA_API_KEY` - Your Exa key
- `HUB_BOT_TOKEN` - The Hub bot's token
- `BOT_TOKEN_POOL` - Comma-separated list of user bot tokens
- `ADMIN_TELEGRAM_ID` - Your Telegram user ID

### 5. Install & Run

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the bot
python -m bot.main

# In another terminal, run the worker (for reminders)
python worker.py
```

## Architecture

```
┌─────────────────┐
│   Hub Bot       │  ← New users start here
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Bot Router    │  ← Routes messages to correct handler
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐ ┌───────┐
│User 1 │ │User 2 │  ← Each user has dedicated bot
│ Bot   │ │ Bot   │
└───┬───┘ └───┬───┘
    │         │
    └────┬────┘
         ▼
┌─────────────────┐
│   PostgreSQL    │  ← All user data
└─────────────────┘
```

## Commands

| Command | Description |
|---------|-------------|
| `/add <task>` | Add a task |
| `/today` | Show today's tasks |
| `/tasks` | Show all pending tasks |
| `/done <number>` | Complete a task |
| `/remind <time> <msg>` | Set a reminder |
| `/reminders` | List reminders |
| `/search <query>` | Search the web |
| `/context` | View stored context |
| `/setcontext <key> <val>` | Update context |
| `/clear` | Clear chat history |
| `/help` | Show help |

## Production Deployment

### systemd service (main bot)

```ini
[Unit]
Description=AnyArchie Bot
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/anyarchie
ExecStart=/var/www/anyarchie/.venv/bin/python -m bot.main
Restart=on-failure
EnvironmentFile=/var/www/anyarchie/.env

[Install]
WantedBy=multi-user.target
```

### systemd service (worker)

```ini
[Unit]
Description=AnyArchie Worker
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/anyarchie
ExecStart=/var/www/anyarchie/.venv/bin/python worker.py
Restart=on-failure
EnvironmentFile=/var/www/anyarchie/.env

[Install]
WantedBy=multi-user.target
```

## File Structure

```
AnyArchie/
├── bot/
│   ├── __init__.py
│   ├── main.py          # Bot router + polling
│   ├── db.py            # Database operations
│   ├── llm.py           # OpenRouter integration
│   ├── handlers.py      # Command handlers
│   ├── onboarding.py    # New user flow
│   ├── reminders.py     # Reminder parsing
│   ├── research.py      # Web search
│   └── pdf_export.py    # PDF generation
├── config.py            # Configuration
├── worker.py            # Background jobs
├── schema.sql           # Database schema
├── requirements.txt
├── .env.example
└── README.md
```

## License

MIT

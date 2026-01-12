"""
AnyArchie Configuration
Loads settings from environment variables
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/anyarchie")

# OpenRouter (LLM)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "anthropic/claude-sonnet-4"

# Exa (Web Search)
EXA_API_KEY = os.getenv("EXA_API_KEY")

# Telegram
HUB_BOT_TOKEN = os.getenv("HUB_BOT_TOKEN")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))

# Bot Token Pool - simple list from comma-separated env var
_pool_str = os.getenv("BOT_TOKEN_POOL", "")
BOT_TOKEN_POOL = [t.strip() for t in _pool_str.split(",") if t.strip()]

# Polling settings
POLL_TIMEOUT = 30  # seconds

# LLM settings
MAX_CONVERSATION_HISTORY = 20  # messages to keep in context
MAX_TOKENS = 2000

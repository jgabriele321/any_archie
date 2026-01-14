#!/usr/bin/env python3
"""
One-time welcome message for Miranda
Run via: python3 /var/www/anyarchie/scripts/welcome_miranda.py
"""
import httpx
import sys
import os

sys.path.insert(0, '/var/www/anyarchie')
from config import BOT_TOKEN_POOL

# Miranda's telegram_id
MIRANDA_TELEGRAM_ID = 8506315004

# Get the bot token (first one in pool)
BOT_TOKEN = BOT_TOKEN_POOL[0] if BOT_TOKEN_POOL else None

MESSAGE = """Good morning! ☀️

I'm Artemis, your personal assistant - ready to help whenever you need me!

Here's what I can do:

**Tasks:**
• `/add Buy groceries` - Add a task
• `/today` - See today's tasks  
• `/done 1` - Complete task #1

**Reminders:**
• `/remind 3pm Call the pediatrician` - Set a reminder

**Other:**
• `/search best baby sleep tips` - Search the web
• `/help` - See all commands

Or just chat naturally - I understand things like "remind me to order diapers tomorrow at 10am" or "add meal prep to my list".

What can I help you with today?"""

def send_message():
    if not BOT_TOKEN:
        print("Error: No bot token configured")
        return False
    
    try:
        with httpx.Client(timeout=30) as client:
            response = client.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": MIRANDA_TELEGRAM_ID,
                    "text": MESSAGE,
                    "parse_mode": "Markdown"
                }
            )
            if response.status_code == 200:
                print(f"Message sent successfully to Miranda!")
                return True
            else:
                print(f"Failed: {response.text}")
                return False
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    send_message()

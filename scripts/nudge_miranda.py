#!/usr/bin/env python3
"""
One-time script to send Miranda a nudge message from Artemis
"""
import asyncio
import httpx
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import db


async def send_message(token: str, chat_id: int, text: str) -> bool:
    """Send a message via Telegram API"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                }
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Error sending message: {e}")
            return False


async def main():
    # Miranda's telegram_id
    user = db.get_user_by_telegram_id(8506315004)
    
    if not user:
        print("User not found!")
        return
    
    message = """Hey Miranda! 👋 Just checking in.

I've been thinking about what you shared - organizing a 200-person gathering while caring for an 8-month-old is no small feat!

Want me to help with any of these?

📋 To-do list for the Earthkin gathering - I can help you break it down into manageable pieces

💰 Land finances tracker - I can remind you to update it or help you stay on top of deadlines

⏰ Self-care reminders - Simple things like "take 10 minutes for yourself" or "drink water"

Just reply with what sounds helpful, or tell me what's on your mind today!"""

    success = await send_message(user['bot_token'], user['telegram_id'], message)
    
    if success:
        print(f"✅ Nudge sent to Miranda!")
    else:
        print(f"❌ Failed to send nudge")


if __name__ == "__main__":
    asyncio.run(main())

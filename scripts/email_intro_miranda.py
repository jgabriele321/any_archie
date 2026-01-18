#!/usr/bin/env python3
"""
Send Miranda intro to email feature
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
    user = db.get_user_by_telegram_id(8506315004)
    
    if not user:
        print("User not found!")
        return
    
    message = """Hey! 📧 Quick update - I can now check your emails for you!

Just type:
• /emails - last 24 hours
• /emails 12 - last 12 hours  
• /emails 72 - last 3 days

I'll show you the important ones and filter out the junk. Give it a try!

Type /help anytime to see everything I can do 🙂"""

    success = await send_message(user['bot_token'], user['telegram_id'], message)
    
    if success:
        print("✅ Email intro sent to Miranda!")
    else:
        print("❌ Failed to send message")


if __name__ == "__main__":
    asyncio.run(main())

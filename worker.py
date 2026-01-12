"""
AnyArchie Background Worker
Handles scheduled tasks like reminders
"""
import asyncio
import signal
import httpx
from datetime import datetime

from config import POLL_TIMEOUT
from bot import db


running = True


async def send_message(client: httpx.AsyncClient, token: str, chat_id: int, text: str) -> bool:
    """Send a message via Telegram API"""
    try:
        response = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown"
            }
        )
        return response.status_code == 200
    except Exception as e:
        print(f"Error sending message: {e}")
        return False


async def process_reminders(client: httpx.AsyncClient) -> int:
    """
    Process pending reminders.
    Returns number of reminders sent.
    """
    reminders = db.get_pending_reminders()
    sent = 0
    
    for r in reminders:
        try:
            message = f"**Reminder:** {r['message']}"
            success = await send_message(
                client,
                r['bot_token'],
                r['telegram_id'],
                message
            )
            
            if success:
                db.mark_reminder_sent(r['id'])
                sent += 1
                print(f"Sent reminder {r['id']} to user {r['user_id']}")
            else:
                print(f"Failed to send reminder {r['id']}")
                
        except Exception as e:
            print(f"Error processing reminder {r['id']}: {e}")
    
    return sent


async def main_loop():
    """Main worker loop"""
    global running
    
    print("AnyArchie Worker starting...")
    print(f"Checking reminders every 30 seconds")
    
    async with httpx.AsyncClient() as client:
        while running:
            try:
                # Process reminders
                sent = await process_reminders(client)
                if sent > 0:
                    print(f"Sent {sent} reminders")
                
                # Wait before next check
                for _ in range(30):  # 30 second intervals
                    if not running:
                        break
                    await asyncio.sleep(1)
                    
            except Exception as e:
                print(f"Error in worker loop: {e}")
                await asyncio.sleep(10)
    
    print("AnyArchie Worker stopped.")


def handle_signal(signum, frame):
    """Handle shutdown signals"""
    global running
    print("\nShutting down worker...")
    running = False


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    asyncio.run(main_loop())

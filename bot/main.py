"""
AnyArchie Main Bot Router
Handles multiple Telegram bots via long polling

Supports two modes:
1. Hub mode: Users sign up via Hub bot, get assigned personal bot
2. Direct mode: Users message their personal bot directly, auto-created on first message
"""
import asyncio
import signal
import sys
import os
from typing import Dict, Optional
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import HUB_BOT_TOKEN, BOT_TOKEN_POOL, ADMIN_TELEGRAM_ID, POLL_TIMEOUT
from bot import db
from bot import onboarding
from bot import handlers


# Store update offsets per bot
offsets: Dict[str, int] = {}

# Track running state
running = True


async def get_updates(client: httpx.AsyncClient, token: str, offset: int = 0) -> list:
    """Get updates from Telegram API"""
    try:
        response = await client.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={"offset": offset, "timeout": POLL_TIMEOUT},
            timeout=POLL_TIMEOUT + 10
        )
        data = response.json()
        if data.get("ok"):
            return data.get("result", [])
    except Exception as e:
        print(f"Error getting updates: {e}")
    return []


async def send_message(client: httpx.AsyncClient, token: str, chat_id: int, text: str) -> bool:
    """Send a message via Telegram API"""
    try:
        # Truncate if too long
        if len(text) > 4096:
            text = text[:4093] + "..."
        
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
        # Try without markdown if it failed
        try:
            response = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text}
            )
            return response.status_code == 200
        except:
            return False


async def handle_hub_message(client: httpx.AsyncClient, message: dict) -> None:
    """
    Handle messages to the Hub bot (new user onboarding).
    """
    chat_id = message["chat"]["id"]
    telegram_id = message["from"]["id"]
    text = message.get("text", "").strip()
    
    print(f"[HUB] Message from {telegram_id}: {text[:50]}...")
    
    # Check if user already exists
    user = db.get_user_by_telegram_id(telegram_id)
    
    if user:
        # User exists - redirect them to their bot
        await send_message(
            client, HUB_BOT_TOKEN, chat_id,
            f"You already have an assistant! Message your personal bot to continue."
        )
        return
    
    # Check if we have available bot tokens
    available_token = None
    for token in BOT_TOKEN_POOL:
        if not db.is_bot_token_assigned(token):
            available_token = token
            break
    
    if not available_token:
        await send_message(
            client, HUB_BOT_TOKEN, chat_id,
            "Sorry, we're at capacity right now. Please try again later!"
        )
        return
    
    # Create new user
    user = db.create_user(telegram_id, available_token)
    
    # Start onboarding
    message_text, _ = onboarding.get_onboarding_message("new")
    
    # Send via their personal bot (not hub)
    await send_message(client, available_token, chat_id, message_text)
    
    # Also confirm on hub
    await send_message(
        client, HUB_BOT_TOKEN, chat_id,
        "I've set up your personal assistant! Check your messages from your new bot."
    )


async def handle_user_message(client: httpx.AsyncClient, token: str, message: dict) -> None:
    """
    Handle messages to a user's personal bot.
    In direct mode, auto-creates user on first message.
    """
    chat_id = message["chat"]["id"]
    telegram_id = message["from"]["id"]
    text = message.get("text", "").strip()
    
    if not text:
        return
    
    print(f"[USER BOT] Message from {telegram_id}: {text[:50]}...")
    
    # Get user by bot token
    user = db.get_user_by_bot_token(token)
    
    # DIRECT MODE: If no user exists for this bot, check if this telegram_id 
    # is messaging for the first time - auto-create them
    if not user:
        # Check if user exists with different bot (shouldn't happen in direct mode)
        existing_user = db.get_user_by_telegram_id(telegram_id)
        if existing_user:
            await send_message(client, token, chat_id, 
                "You already have an assistant on a different bot!")
            return
        
        # Auto-create user for this bot (DIRECT MODE)
        print(f"[DIRECT MODE] Creating new user for telegram_id {telegram_id}")
        user = db.create_user(telegram_id, token)
        
        # Start onboarding
        message_text, _ = onboarding.get_onboarding_message("new")
        await send_message(client, token, chat_id, message_text)
        return
    
    # Verify this is the right user for this bot
    if user['telegram_id'] != telegram_id:
        # Someone else is messaging this bot - could be a problem
        # For now, just ignore or warn
        await send_message(client, token, chat_id,
            "This bot is assigned to someone else. Please contact support.")
        return
    
    # Check if user is in onboarding
    if user['onboarding_state'] != 'complete':
        response, is_complete = onboarding.process_onboarding_step(
            user['id'], user['onboarding_state'], text
        )
        await send_message(client, token, chat_id, response)
        return
    
    # Handle command or natural language
    response = handlers.handle_command(user['id'], text, user)
    await send_message(client, token, chat_id, response)


async def poll_bot(client: httpx.AsyncClient, token: str, is_hub: bool = False) -> None:
    """Poll a single bot for updates"""
    global offsets, running
    
    offset = offsets.get(token, 0)
    updates = await get_updates(client, token, offset)
    
    for update in updates:
        offsets[token] = update["update_id"] + 1
        
        if "message" not in update:
            continue
        
        message = update["message"]
        
        if is_hub:
            await handle_hub_message(client, message)
        else:
            await handle_user_message(client, token, message)


async def main_loop():
    """Main polling loop"""
    global running
    
    print("AnyArchie starting...")
    
    # Check if we're in Hub mode or Direct mode
    hub_mode = bool(HUB_BOT_TOKEN)
    print(f"Mode: {'Hub + Direct' if hub_mode else 'Direct only'}")
    print(f"Bot pool size: {len(BOT_TOKEN_POOL)}")
    
    if not BOT_TOKEN_POOL:
        print("ERROR: No bot tokens in BOT_TOKEN_POOL!")
        return
    
    # Get active user bots (bots with users assigned)
    active_tokens = db.get_all_active_bot_tokens()
    print(f"Active user bots: {len(active_tokens)}")
    
    # In direct mode, we poll ALL bots in the pool (even unassigned ones)
    # so new users can message them directly
    tokens_to_poll = set(BOT_TOKEN_POOL)
    
    async with httpx.AsyncClient() as client:
        while running:
            try:
                # Poll hub bot if configured
                if hub_mode:
                    await poll_bot(client, HUB_BOT_TOKEN, is_hub=True)
                
                # Poll all bots in the pool
                for token in tokens_to_poll:
                    if not running:
                        break
                    await poll_bot(client, token, is_hub=False)
                
                # Small delay between full cycles
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"Error in main loop: {e}")
                await asyncio.sleep(5)
    
    print("AnyArchie stopped.")


def handle_signal(signum, frame):
    """Handle shutdown signals"""
    global running
    print("\nShutting down...")
    running = False


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    asyncio.run(main_loop())

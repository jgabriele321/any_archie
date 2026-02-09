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


# Track processed update IDs to prevent duplicates
_processed_updates: set = set()

async def send_message(client: httpx.AsyncClient, token: str, chat_id: int, text: str) -> bool:
    """Send a message via Telegram API"""
    # #region agent log
    try:
        import json as _json, os as _os, traceback as _tb
        _log_path = '/Users/giovannigabriele/Documents/Code/AnyArchie/.cursor/debug.log'
        _os.makedirs(_os.path.dirname(_log_path), exist_ok=True)
        _stack = ''.join(_tb.format_stack()[-5:-1])
        with open(_log_path, 'a') as _f: _f.write(_json.dumps({"location":"main.py:send_message","message":"SEND_MESSAGE CALLED","data":{"chat_id":chat_id,"text_preview":text[:50],"stack_trace":_stack[:500]},"timestamp":__import__('time').time()*1000,"hypothesisId":"C"})+'\n')
    except: pass
    # #endregion
    print(f"[DEBUG] send_message called: chat_id={chat_id}, text={text[:50]}...")
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
    
    # #region agent log
    import json as _json; open('/Users/giovannigabriele/Documents/Code/AnyArchie/.cursor/debug.log','a').write(_json.dumps({"location":"main.py:126","message":"HANDLE_USER_MESSAGE ENTRY","data":{"telegram_id":telegram_id,"text":text[:30],"chat_id":chat_id},"timestamp":__import__('time').time()*1000,"hypothesisId":"A"})+'\n')
    # #endregion
    
    if not text:
        return
    
    print(f"[USER BOT] Message from {telegram_id}: {text[:50]}...")
    
    # Handle /start command specially
    if text.lower() == "/start" or text.lower().startswith("/start "):
        # #region agent log
        try:
            import json as _json, os as _os
            _log_path = '/Users/giovannigabriele/Documents/Code/AnyArchie/.cursor/debug.log'
            _os.makedirs(_os.path.dirname(_log_path), exist_ok=True)
            with open(_log_path, 'a') as _f: _f.write(_json.dumps({"location":"main.py:145","message":"MAIN.PY /start handler ENTRY","data":{"telegram_id":telegram_id,"text":text,"chat_id":chat_id},"timestamp":__import__('time').time()*1000,"hypothesisId":"B"})+'\n')
        except: pass
        # #endregion
        print(f"[DEBUG] /start command received from {telegram_id}")
        user = db.get_user_by_bot_token(token)
        if not user:
            # Check if user exists with different bot
            existing_user = db.get_user_by_telegram_id(telegram_id)
            if existing_user:
                await send_message(client, token, chat_id, 
                    "You already have an assistant on a different bot!")
                return
            
            # Create new user
            print(f"[DIRECT MODE] Creating new user for telegram_id {telegram_id}")
            user = db.create_user(telegram_id, token)
        else:
            # Reset onboarding if user exists but wants to restart
            if user['telegram_id'] == telegram_id:
                db.update_user(user['id'], onboarding_state='new')
        
        # Start onboarding
        message_text, _ = onboarding.get_onboarding_message("new")
        # #region agent log
        try:
            import json as _json, os as _os
            _log_path = '/Users/giovannigabriele/Documents/Code/AnyArchie/.cursor/debug.log'
            _os.makedirs(_os.path.dirname(_log_path), exist_ok=True)
            with open(_log_path, 'a') as _f: _f.write(_json.dumps({"location":"main.py:167","message":"MAIN.PY /start sending onboarding msg","data":{"telegram_id":telegram_id,"msg_preview":message_text[:50]},"timestamp":__import__('time').time()*1000,"hypothesisId":"B"})+'\n')
        except: pass
        # #endregion
        print(f"[DEBUG] Sending onboarding message to {telegram_id} (chat {chat_id})")
        await send_message(client, token, chat_id, message_text)
        # #region agent log
        try:
            import json as _json
            with open('/Users/giovannigabriele/Documents/Code/AnyArchie/.cursor/debug.log', 'a') as _f: _f.write(_json.dumps({"location":"main.py:175","message":"MAIN.PY /start RETURNING","data":{"telegram_id":telegram_id},"timestamp":__import__('time').time()*1000,"hypothesisId":"B"})+'\n')
        except: pass
        # #endregion
        print(f"[DEBUG] Returning from /start handler")
        return
    
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
    
    # Helper function for sending messages (wraps async send_message)
    def sync_send_message(telegram_id: int, message: str):
        """Sync wrapper for async send_message"""
        asyncio.create_task(send_message(client, token, chat_id, message))
    
    # Check if user is in onboarding
    if user['onboarding_state'] != 'complete':
        # #region agent log
        import json as _json; open('/Users/giovannigabriele/Documents/Code/AnyArchie/.cursor/debug.log','a').write(_json.dumps({"location":"main.py:207","message":"MAIN.PY onboarding handler","data":{"telegram_id":telegram_id,"state":user['onboarding_state'],"text":text[:30]},"timestamp":__import__('time').time()*1000,"hypothesisId":"B"})+'\n')
        # #endregion
        response, is_complete = onboarding.process_onboarding_step(
            user['id'], user['onboarding_state'], text
        )
        await send_message(client, token, chat_id, response)
        if is_complete:
            db.update_user(user['id'], onboarding_state='complete')
        # #region agent log
        import json as _json; open('/Users/giovannigabriele/Documents/Code/AnyArchie/.cursor/debug.log','a').write(_json.dumps({"location":"main.py:223","message":"MAIN.PY onboarding RETURNING","data":{"telegram_id":telegram_id,"is_complete":is_complete},"timestamp":__import__('time').time()*1000,"hypothesisId":"B"})+'\n')
        # #endregion
        return
    
    # Helper function for sending messages (wraps async send_message)
    def sync_send_message(telegram_id: int, message: str):
        """Sync wrapper for async send_message - note: telegram_id ignored, uses chat_id"""
        asyncio.create_task(send_message(client, token, chat_id, message))
    
    # #region agent log
    import json as _json; open('/Users/giovannigabriele/Documents/Code/AnyArchie/.cursor/debug.log','a').write(_json.dumps({"location":"main.py:232","message":"MAIN.PY calling handlers.handle_command (onboarding complete)","data":{"user_id":user['id'],"text":text[:30],"onboarding_state":user['onboarding_state']},"timestamp":__import__('time').time()*1000,"hypothesisId":"B"})+'\n')
    # #endregion
    # Handle command or natural language (only for users who completed onboarding)
    handlers.handle_command(
        user_id=user['id'],
        text=text,
        user=user,
        send_message=sync_send_message
    )


async def poll_bot(client: httpx.AsyncClient, token: str, is_hub: bool = False) -> None:
    """Poll a single bot for updates"""
    global offsets, running, _processed_updates
    
    offset = offsets.get(token, 0)
    updates = await get_updates(client, token, offset)
    
    # Log number of updates received
    print(f"[DEBUG] poll_bot: received {len(updates)} updates for token {token[:10]}...")
    
    for update in updates:
        update_id = update["update_id"]
        
        # DEDUPLICATION: Skip if already processed
        if update_id in _processed_updates:
            print(f"[DEBUG] Skipping duplicate update {update_id}")
            offsets[token] = update_id + 1
            continue
        _processed_updates.add(update_id)
        # Keep set from growing too large
        if len(_processed_updates) > 1000:
            _processed_updates = set(list(_processed_updates)[-500:])
        
        # #region agent log
        try:
            import json as _json, os as _os
            _log_path = '/Users/giovannigabriele/Documents/Code/AnyArchie/.cursor/debug.log'
            _os.makedirs(_os.path.dirname(_log_path), exist_ok=True)
            with open(_log_path, 'a') as _f: _f.write(_json.dumps({"location":"main.py:280","message":"POLL_BOT processing update","data":{"update_id":update_id,"token_preview":token[:10]+"...","num_updates":len(updates)},"timestamp":__import__('time').time()*1000,"hypothesisId":"A"})+'\n')
        except: pass
        # #endregion
        
        if "message" not in update:
            # Update offset even for non-message updates
            offsets[token] = update_id + 1
            continue
        
        message = update["message"]
        # #region agent log
        try:
            import json as _json
            with open('/Users/giovannigabriele/Documents/Code/AnyArchie/.cursor/debug.log', 'a') as _f: _f.write(_json.dumps({"location":"main.py:262","message":"POLL_BOT message extracted","data":{"update_id":update_id,"text":message.get("text","")[:30],"chat_id":message.get("chat",{}).get("id")},"timestamp":__import__('time').time()*1000,"hypothesisId":"A"})+'\n')
        except: pass
        # #endregion
        
        # Handle photo uploads
        if "photo" in message and not is_hub:
            # Get user for this bot
            user = db.get_user_by_bot_token(token)
            if user and user['telegram_id'] == message["from"]["id"]:
                # Download photo
                photo = message["photo"][-1]  # Get largest size
                file_id = photo["file_id"]
                # Note: Would need to download file here, but for now just notify
                # Full implementation would download via getFile API
                await send_message(client, token, message["chat"]["id"],
                    "📸 Photo received! Business card scanning coming soon.")
            # Update offset after processing
            offsets[token] = update_id + 1
            continue
        
        try:
            if is_hub:
                await handle_hub_message(client, message)
            else:
                # #region agent log
                try:
                    import json as _json
                    with open('/Users/giovannigabriele/Documents/Code/AnyArchie/.cursor/debug.log', 'a') as _f: _f.write(_json.dumps({"location":"main.py:280","message":"POLL_BOT calling handle_user_message","data":{"update_id":update_id,"text":message.get("text","")[:30]},"timestamp":__import__('time').time()*1000,"hypothesisId":"A"})+'\n')
                except: pass
                # #endregion
                await handle_user_message(client, token, message)
        except Exception as e:
            print(f"[ERROR] Error processing update {update_id}: {e}")
        finally:
            # Update offset AFTER successful processing
            offsets[token] = update_id + 1


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

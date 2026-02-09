"""
Heartbeat Worker for AnyArchie - Multi-tenant proactive monitoring.

Uses a "Look, Think, Decide, Act" approach:
- Look: Gather current state (emails, tasks, calendar) for each user
- Think: Compare against last notification - what's NEW/changed?
- Decide: Is this worth interrupting the user?
- Act: If yes, use Claude to compose a natural, contextual message

Only notifies when something actionable changed - no spam!
"""
import asyncio
import hashlib
import json
import signal
import sys
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
import httpx
import yaml
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, DEFAULT_MODEL
from bot import db
from bot import llm
from bot import credential_manager
from bot import calendar_client
from bot import email_client

running = True

# Config path
HEARTBEAT_CONFIG_PATH = Path(__file__).parent.parent / "heartbeat.yaml"


def load_heartbeat_config() -> Dict[str, Any]:
    """Load heartbeat configuration from YAML file."""
    if not HEARTBEAT_CONFIG_PATH.exists():
        return get_default_config()
    
    try:
        with open(HEARTBEAT_CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f) or {}
        return {**get_default_config(), **config}
    except Exception as e:
        print(f"Error loading heartbeat config: {e}")
        return get_default_config()


def get_default_config() -> Dict[str, Any]:
    """Return default heartbeat configuration."""
    return {
        "interval_minutes": 120,  # Check every 2 hours
        "quiet_hours": {
            "enabled": True,
            "start": 22,  # 10 PM
            "end": 8,     # 8 AM
        },
        "mute_duration_minutes": 120,  # 2 hours when user mutes
        "checks": {
            "urgent_emails": {
                "enabled": True,
                "max_age_hours": 24,
            },
            "calendar_soon": {
                "enabled": True,
                "lookahead_minutes": 60,
            },
            "overdue_tasks": {
                "enabled": True,
            },
        },
    }


def get_user_heartbeat_state(user_id: int) -> Dict[str, Any]:
    """Get heartbeat state for a user from database."""
    with db.get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM heartbeat_state WHERE user_id = %s",
                (user_id,)
            )
            row = cur.fetchone()
            
            if row:
                return {
                    "user_id": user_id,
                    "last_heartbeat": row.get('last_heartbeat'),
                    "muted_until": row.get('muted_until'),
                    "last_notified_email_ids": list(row.get('last_notified_email_ids', []) or []),
                    "last_notified_task_hashes": list(row.get('last_notified_task_hashes', []) or []),
                    "last_notified_calendar_ids": list(row.get('last_notified_calendar_ids', []) or []),
                }
            else:
                # Create default state
                cur.execute(
                    """INSERT INTO heartbeat_state (user_id, last_notified_email_ids, 
                       last_notified_task_hashes, last_notified_calendar_ids)
                       VALUES (%s, %s, %s, %s) RETURNING *""",
                    (user_id, [], [], [])
                )
                conn.commit()
                row = cur.fetchone()
                return {
                    "user_id": user_id,
                    "last_heartbeat": None,
                    "muted_until": None,
                    "last_notified_email_ids": [],
                    "last_notified_task_hashes": [],
                    "last_notified_calendar_ids": [],
                }


def save_user_heartbeat_state(state: Dict[str, Any]) -> None:
    """Save heartbeat state for a user to database."""
    user_id = state['user_id']
    with db.get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE heartbeat_state 
                   SET last_heartbeat = %s, muted_until = %s,
                       last_notified_email_ids = %s, last_notified_task_hashes = %s,
                       last_notified_calendar_ids = %s, updated_at = NOW()
                   WHERE user_id = %s""",
                (
                    state.get('last_heartbeat'),
                    state.get('muted_until'),
                    state.get('last_notified_email_ids', []),
                    state.get('last_notified_task_hashes', []),
                    state.get('last_notified_calendar_ids', []),
                    user_id
                )
            )
            conn.commit()


def is_muted(state: Dict[str, Any]) -> bool:
    """Check if heartbeat notifications are currently muted for user."""
    muted_until = state.get("muted_until")
    if not muted_until:
        return False
    
    if isinstance(muted_until, str):
        muted_until = datetime.fromisoformat(muted_until.replace('Z', '+00:00'))
    
    return datetime.now() < muted_until.replace(tzinfo=None) if muted_until.tzinfo else datetime.now() < muted_until


def mute_user_heartbeat(user_id: int, duration_minutes: int = 120) -> None:
    """Mute heartbeat notifications for a user."""
    state = get_user_heartbeat_state(user_id)
    state["muted_until"] = (datetime.now() + timedelta(minutes=duration_minutes))
    save_user_heartbeat_state(state)


def unmute_user_heartbeat(user_id: int) -> None:
    """Unmute heartbeat notifications for a user."""
    state = get_user_heartbeat_state(user_id)
    state["muted_until"] = None
    save_user_heartbeat_state(state)


def is_quiet_hours(config: Dict[str, Any]) -> bool:
    """Check if current time is within quiet hours."""
    quiet = config.get("quiet_hours", {})
    if not quiet.get("enabled", False):
        return False
    
    current_hour = datetime.now().hour
    start = quiet.get("start", 22)
    end = quiet.get("end", 8)
    
    if start > end:
        return current_hour >= start or current_hour < end
    else:
        return start <= current_hour < end


def hash_task(task_text: str) -> str:
    """Create a short hash of task text for tracking."""
    return hashlib.md5(task_text.strip().lower().encode()).hexdigest()[:12]


async def check_user_urgent_emails(user_id: int, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Check for urgent/unread emails for a user."""
    check_config = config.get("checks", {}).get("urgent_emails", {})
    if not check_config.get("enabled", True):
        return None
    
    try:
        creds = credential_manager.get_user_credential(user_id, "gmail")
        if not creds:
            return None
        
        email_address = creds.get('email')
        app_password = creds.get('password')
        if not email_address or not app_password:
            return None
        
        max_age_hours = check_config.get("max_age_hours", 24)
        emails = email_client.fetch_emails(
            email_address=email_address,
            app_password=app_password,
            hours=max_age_hours,
            imap_server='imap.gmail.com'
        )
        
        # Filter to important (non-junk) emails
        important_emails = [e for e in emails if not e.is_junk]
        
        if not important_emails:
            return None
        
        # Handle timezone-aware datetimes
        def format_email_id(email):
            email_date = email.date
            if email_date.tzinfo:
                email_date = email_date.replace(tzinfo=None)
            return f"{email.sender_email}_{email_date.isoformat()}"
        
        return {
            "type": "urgent_emails",
            "count": len(important_emails),
            "items": [
                {
                    "id": format_email_id(e),
                    "sender": e.sender,
                    "sender_email": e.sender_email,
                    "subject": e.subject[:80],
                    "snippet": e.snippet[:100] if hasattr(e, 'snippet') else "",
                }
                for e in important_emails[:10]
            ],
            "all_ids": [format_email_id(e) for e in important_emails],
        }
    except Exception as e:
        print(f"Error checking emails for user {user_id}: {e}")
        return None


async def check_user_calendar_soon(user_id: int, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Check for upcoming calendar events for a user."""
    check_config = config.get("checks", {}).get("calendar_soon", {})
    if not check_config.get("enabled", True):
        return None
    
    try:
        creds = credential_manager.get_user_credential(user_id, "google_calendar")
        if not creds:
            return None
        
        lookahead = check_config.get("lookahead_minutes", 60)
        events = calendar_client.fetch_events_from_user(user_id, days=1)
        
        now = datetime.now()
        upcoming = []
        for event in events:
            # Handle timezone-aware datetimes
            event_start = event.start
            if event_start.tzinfo:
                event_start = event_start.replace(tzinfo=None)
            
            if event_start <= now + timedelta(minutes=lookahead) and event_start >= now:
                minutes_until = int((event_start - now).total_seconds() / 60)
                event_id = f"{event.summary}_{event_start.isoformat()}"
                upcoming.append({
                    "id": event_id,
                    "summary": event.summary,
                    "minutes_until": minutes_until,
                    "location": event.location or "",
                    "is_imminent": minutes_until <= 15,
                })
        
        if not upcoming:
            return None
        
        return {
            "type": "calendar_soon",
            "count": len(upcoming),
            "items": upcoming,
            "all_ids": [e["id"] for e in upcoming],
        }
    except Exception as e:
        print(f"Error checking calendar for user {user_id}: {e}")
        return None


async def check_user_overdue_tasks(user_id: int, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Check for overdue/urgent tasks for a user."""
    check_config = config.get("checks", {}).get("overdue_tasks", {})
    if not check_config.get("enabled", True):
        return None
    
    try:
        # Get overdue tasks
        tasks = db.get_tasks_due_today(user_id)
        overdue = [t for t in tasks if t.get('due_date') and datetime.now().date() > t['due_date']]
        
        if not overdue:
            return None
        
        return {
            "type": "overdue_tasks",
            "count": len(overdue),
            "items": [
                {
                    "text": t['content'][:80],
                    "hash": hash_task(t['content']),
                    "priority": "overdue",
                }
                for t in overdue[:10]
            ],
            "all_hashes": [hash_task(t['content']) for t in overdue],
        }
    except Exception as e:
        print(f"Error checking tasks for user {user_id}: {e}")
        return None


async def run_user_heartbeat_checks(user_id: int, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Run all enabled heartbeat checks for a user."""
    results = []
    
    checks = [
        check_user_urgent_emails,
        check_user_calendar_soon,
        check_user_overdue_tasks,
    ]
    
    for check_fn in checks:
        try:
            result = await check_fn(user_id, config)
            if result:
                results.append(result)
        except Exception as e:
            print(f"Error running check {check_fn.__name__} for user {user_id}: {e}")
    
    return results


def filter_new_items(results: List[Dict[str, Any]], state: Dict[str, Any]) -> Dict[str, Any]:
    """Filter results to only include NEW items not previously notified."""
    last_notified = {
        "email_ids": set(state.get("last_notified_email_ids", [])),
        "task_hashes": set(state.get("last_notified_task_hashes", [])),
        "calendar_ids": set(state.get("last_notified_calendar_ids", [])),
    }
    
    new_items = {
        "emails": [],
        "tasks": [],
        "calendar": [],
        "summary": {
            "new_email_count": 0,
            "new_task_count": 0,
            "imminent_events": 0,
        }
    }
    
    for result in results:
        result_type = result.get("type")
        
        if result_type == "urgent_emails":
            for item in result.get("items", []):
                if item.get("id") not in last_notified["email_ids"]:
                    new_items["emails"].append(item)
            new_items["summary"]["new_email_count"] = len(new_items["emails"])
        
        elif result_type == "overdue_tasks":
            for item in result.get("items", []):
                if item.get("hash") not in last_notified["task_hashes"]:
                    new_items["tasks"].append(item)
            new_items["summary"]["new_task_count"] = len(new_items["tasks"])
        
        elif result_type == "calendar_soon":
            for item in result.get("items", []):
                if item.get("is_imminent"):
                    new_items["calendar"].append(item)
                    new_items["summary"]["imminent_events"] += 1
                elif item.get("id") not in last_notified["calendar_ids"]:
                    new_items["calendar"].append(item)
    
    return new_items


def has_actionable_items(new_items: Dict[str, Any]) -> bool:
    """Determine if there's anything worth notifying the user about."""
    summary = new_items.get("summary", {})
    
    # Always notify for imminent calendar events
    if summary.get("imminent_events", 0) > 0:
        return True
    
    # Notify for new important emails
    if summary.get("new_email_count", 0) > 0:
        for email in new_items.get("emails", []):
            subject_lower = email.get("subject", "").lower()
            if any(word in subject_lower for word in ["urgent", "asap", "important", "deadline", "quick", "?"]):
                return True
        if summary.get("new_email_count", 0) >= 3:
            return True
    
    # Notify for overdue tasks
    if summary.get("new_task_count", 0) > 0:
        return True
    
    return False


def update_notified_state(state: Dict[str, Any], results: List[Dict[str, Any]]) -> None:
    """Update state with what we just notified about."""
    for result in results:
        result_type = result.get("type")
        
        if result_type == "urgent_emails":
            state["last_notified_email_ids"] = result.get("all_ids", [])[:50]
        elif result_type == "overdue_tasks":
            state["last_notified_task_hashes"] = result.get("all_hashes", [])[:20]
        elif result_type == "calendar_soon":
            state["last_notified_calendar_ids"] = result.get("all_ids", [])[:10]


def compose_natural_message(user: Dict, new_items: Dict[str, Any]) -> str:
    """Use Claude to compose a natural, conversational check-in message."""
    try:
        now = datetime.now()
        time_of_day = "morning" if now.hour < 12 else "afternoon" if now.hour < 17 else "evening"
        
        context_parts = []
        
        if new_items["emails"]:
            email_info = []
            for e in new_items["emails"][:5]:
                email_info.append(f"- From {e.get('sender', 'unknown')}: \"{e.get('subject', 'no subject')}\"")
            context_parts.append(f"NEW EMAILS ({len(new_items['emails'])} total):\n" + "\n".join(email_info))
        
        if new_items["tasks"]:
            task_info = []
            for t in new_items["tasks"][:5]:
                task_info.append(f"- {t.get('text', '')}")
            context_parts.append(f"OVERDUE TASKS:\n" + "\n".join(task_info))
        
        if new_items["calendar"]:
            cal_info = []
            for c in new_items["calendar"]:
                mins = c.get("minutes_until", 0)
                cal_info.append(f"- {c.get('summary', 'Event')} in {mins} minutes")
            context_parts.append(f"UPCOMING EVENTS:\n" + "\n".join(cal_info))
        
        context = "\n\n".join(context_parts)
        
        assistant_name = user.get('assistant_name', 'Archie')
        user_name = user.get('user_name', 'there')
        
        prompt = f"""You are {assistant_name}, {user_name}'s personal assistant. Write a brief, natural check-in message for Telegram.

TIME: {time_of_day} ({now.strftime('%H:%M')})

WHAT'S NEW SINCE LAST CHECK:
{context}

GUIDELINES:
- Be conversational and natural, like a helpful friend
- Keep it SHORT (2-4 sentences max)
- Prioritize what's most actionable or time-sensitive
- Don't use bullet points or formal formatting
- Don't say "heartbeat" or sound robotic
- If something needs action, offer to help
- Vary your tone - don't start every message the same way

Write the message now:"""
        
        messages = [{"role": "user", "content": prompt}]
        response = llm.chat(messages, max_tokens=200)
        
        return response.strip()
        
    except Exception as e:
        print(f"Error composing message: {e}")
        # Fallback
        parts = []
        if new_items["calendar"]:
            for c in new_items["calendar"]:
                if c.get("is_imminent"):
                    parts.append(f"📅 {c.get('summary')} starting in {c.get('minutes_until')} min!")
        if new_items["emails"]:
            parts.append(f"📧 {len(new_items['emails'])} new email(s)")
        if new_items["tasks"]:
            parts.append(f"📋 {len(new_items['tasks'])} overdue task(s)")
        return "\n".join(parts) if parts else "Quick check-in - nothing urgent right now."


async def send_heartbeat_notification(client: httpx.AsyncClient, token: str, chat_id: int, message: str) -> bool:
    """Send a heartbeat notification via Telegram."""
    try:
        response = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown"
            },
            timeout=15
        )
        if response.status_code != 200:
            # Try without markdown
            response = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": message.replace("*", "").replace("_", "")
                },
                timeout=15
            )
        return response.status_code == 200
    except Exception as e:
        print(f"Error sending heartbeat notification: {e}")
        return False


async def run_user_heartbeat_cycle(user: Dict, config: Dict[str, Any], client: httpx.AsyncClient) -> None:
    """Run heartbeat cycle for a single user."""
    user_id = user['id']
    state = get_user_heartbeat_state(user_id)
    
    # Check if muted or quiet hours
    if is_muted(state):
        return
    
    if is_quiet_hours(config):
        return
    
    # LOOK: Gather current state
    results = await run_user_heartbeat_checks(user_id, config)
    
    if not results:
        return
    
    # THINK: What's NEW since last notification?
    new_items = filter_new_items(results, state)
    
    # DECIDE: Is this worth interrupting?
    if not has_actionable_items(new_items):
        # Still update state
        update_notified_state(state, results)
        state["last_heartbeat"] = datetime.now()
        save_user_heartbeat_state(state)
        return
    
    # ACT: Compose and send message
    message = compose_natural_message(user, new_items)
    
    success = await send_heartbeat_notification(
        client,
        user['bot_token'],
        user['telegram_id'],
        message
    )
    
    if success:
        # Update state
        update_notified_state(state, results)
        state["last_heartbeat"] = datetime.now()
        save_user_heartbeat_state(state)


async def process_all_users(client: httpx.AsyncClient, config: Dict[str, Any]) -> int:
    """Process heartbeat for all active users."""
    # Get all users who have completed onboarding
    with db.get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM users WHERE onboarding_state = 'complete'"
            )
            users = cur.fetchall()
    
    processed = 0
    for user in users:
        try:
            await run_user_heartbeat_cycle(user, config, client)
            processed += 1
        except Exception as e:
            print(f"Error processing heartbeat for user {user['id']}: {e}")
    
    return processed


async def main_loop():
    """Main heartbeat worker loop."""
    global running
    
    print("AnyArchie Heartbeat Worker starting...")
    
    config = load_heartbeat_config()
    interval = config.get("interval_minutes", 120) * 60
    
    print(f"Heartbeat interval: {interval // 60} minutes")
    
    async with httpx.AsyncClient() as client:
        while running:
            try:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Running heartbeat cycle...")
                processed = await process_all_users(client, config)
                print(f"Processed {processed} users")
                
                # Wait before next check
                for _ in range(interval):
                    if not running:
                        break
                    await asyncio.sleep(1)
                    
            except Exception as e:
                print(f"Error in heartbeat loop: {e}")
                await asyncio.sleep(60)
    
    print("AnyArchie Heartbeat Worker stopped.")


def handle_signal(signum, frame):
    """Handle shutdown signals"""
    global running
    print("\nShutting down heartbeat worker...")
    running = False


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    asyncio.run(main_loop())
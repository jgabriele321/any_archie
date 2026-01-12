"""
AnyArchie Database Operations
Simple PostgreSQL interface using psycopg2
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from datetime import datetime, date
from typing import Optional, List, Dict, Any
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATABASE_URL


@contextmanager
def get_db():
    """Context manager for database connections"""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def dict_cursor(conn):
    """Get a cursor that returns dicts"""
    return conn.cursor(cursor_factory=RealDictCursor)


# ============ USERS ============

def get_user_by_telegram_id(telegram_id: int) -> Optional[Dict]:
    """Get user by their Telegram ID"""
    with get_db() as conn:
        with dict_cursor(conn) as cur:
            cur.execute(
                "SELECT * FROM users WHERE telegram_id = %s",
                (telegram_id,)
            )
            return cur.fetchone()


def get_user_by_bot_token(bot_token: str) -> Optional[Dict]:
    """Get user by their assigned bot token"""
    with get_db() as conn:
        with dict_cursor(conn) as cur:
            cur.execute(
                "SELECT * FROM users WHERE bot_token = %s",
                (bot_token,)
            )
            return cur.fetchone()


def get_all_active_bot_tokens() -> List[str]:
    """Get all bot tokens that have users assigned"""
    with get_db() as conn:
        with dict_cursor(conn) as cur:
            cur.execute("SELECT DISTINCT bot_token FROM users")
            return [row['bot_token'] for row in cur.fetchall()]


def create_user(telegram_id: int, bot_token: str, assistant_name: str = "Archie") -> Dict:
    """Create a new user with assigned bot"""
    with get_db() as conn:
        with dict_cursor(conn) as cur:
            cur.execute(
                """INSERT INTO users (telegram_id, bot_token, assistant_name)
                   VALUES (%s, %s, %s) RETURNING *""",
                (telegram_id, bot_token, assistant_name)
            )
            return cur.fetchone()


def update_user(user_id: int, **kwargs) -> Optional[Dict]:
    """Update user fields"""
    if not kwargs:
        return None
    
    fields = ", ".join(f"{k} = %s" for k in kwargs.keys())
    values = list(kwargs.values()) + [user_id]
    
    with get_db() as conn:
        with dict_cursor(conn) as cur:
            cur.execute(
                f"UPDATE users SET {fields} WHERE id = %s RETURNING *",
                values
            )
            return cur.fetchone()


def is_bot_token_assigned(bot_token: str) -> bool:
    """Check if a bot token is already assigned to a user"""
    with get_db() as conn:
        with dict_cursor(conn) as cur:
            cur.execute(
                "SELECT 1 FROM users WHERE bot_token = %s LIMIT 1",
                (bot_token,)
            )
            return cur.fetchone() is not None


# ============ CONTEXT ============

def get_context(user_id: int, key: str) -> Optional[str]:
    """Get a context value for a user"""
    with get_db() as conn:
        with dict_cursor(conn) as cur:
            cur.execute(
                "SELECT value FROM context WHERE user_id = %s AND key = %s",
                (user_id, key)
            )
            row = cur.fetchone()
            return row['value'] if row else None


def set_context(user_id: int, key: str, value: str) -> None:
    """Set a context value (upsert)"""
    with get_db() as conn:
        with dict_cursor(conn) as cur:
            cur.execute(
                """INSERT INTO context (user_id, key, value)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (user_id, key) 
                   DO UPDATE SET value = EXCLUDED.value""",
                (user_id, key, value)
            )


def get_all_context(user_id: int) -> Dict[str, str]:
    """Get all context for a user as a dict"""
    with get_db() as conn:
        with dict_cursor(conn) as cur:
            cur.execute(
                "SELECT key, value FROM context WHERE user_id = %s",
                (user_id,)
            )
            return {row['key']: row['value'] for row in cur.fetchall()}


# ============ TASKS ============

def add_task(user_id: int, content: str, due_date: Optional[date] = None, 
             priority: int = 0, category: Optional[str] = None) -> Dict:
    """Add a new task"""
    with get_db() as conn:
        with dict_cursor(conn) as cur:
            cur.execute(
                """INSERT INTO tasks (user_id, content, due_date, priority, category)
                   VALUES (%s, %s, %s, %s, %s) RETURNING *""",
                (user_id, content, due_date, priority, category)
            )
            return cur.fetchone()


def get_tasks(user_id: int, status: str = "pending") -> List[Dict]:
    """Get tasks for a user by status"""
    with get_db() as conn:
        with dict_cursor(conn) as cur:
            cur.execute(
                """SELECT * FROM tasks 
                   WHERE user_id = %s AND status = %s
                   ORDER BY priority DESC, due_date ASC NULLS LAST, created_at ASC""",
                (user_id, status)
            )
            return cur.fetchall()


def get_tasks_due_today(user_id: int) -> List[Dict]:
    """Get tasks due today (or overdue)"""
    with get_db() as conn:
        with dict_cursor(conn) as cur:
            cur.execute(
                """SELECT * FROM tasks 
                   WHERE user_id = %s AND status = 'pending' 
                   AND (due_date IS NULL OR due_date <= CURRENT_DATE)
                   ORDER BY priority DESC, due_date ASC NULLS LAST""",
                (user_id,)
            )
            return cur.fetchall()


def complete_task(task_id: int) -> Optional[Dict]:
    """Mark a task as done"""
    with get_db() as conn:
        with dict_cursor(conn) as cur:
            cur.execute(
                """UPDATE tasks SET status = 'done', completed_at = NOW()
                   WHERE id = %s RETURNING *""",
                (task_id,)
            )
            return cur.fetchone()


def delete_task(task_id: int) -> bool:
    """Delete a task"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
            return cur.rowcount > 0


# ============ REMINDERS ============

def add_reminder(user_id: int, message: str, remind_at: datetime) -> Dict:
    """Add a reminder"""
    with get_db() as conn:
        with dict_cursor(conn) as cur:
            cur.execute(
                """INSERT INTO reminders (user_id, message, remind_at)
                   VALUES (%s, %s, %s) RETURNING *""",
                (user_id, message, remind_at)
            )
            return cur.fetchone()


def get_pending_reminders() -> List[Dict]:
    """Get all reminders that should be sent now"""
    with get_db() as conn:
        with dict_cursor(conn) as cur:
            cur.execute(
                """SELECT r.*, u.bot_token, u.telegram_id, u.assistant_name
                   FROM reminders r
                   JOIN users u ON r.user_id = u.id
                   WHERE r.sent = FALSE AND r.remind_at <= NOW()
                   ORDER BY r.remind_at ASC"""
            )
            return cur.fetchall()


def mark_reminder_sent(reminder_id: int) -> None:
    """Mark a reminder as sent"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE reminders SET sent = TRUE WHERE id = %s",
                (reminder_id,)
            )


def get_user_reminders(user_id: int) -> List[Dict]:
    """Get pending reminders for a user"""
    with get_db() as conn:
        with dict_cursor(conn) as cur:
            cur.execute(
                """SELECT * FROM reminders 
                   WHERE user_id = %s AND sent = FALSE
                   ORDER BY remind_at ASC""",
                (user_id,)
            )
            return cur.fetchall()


# ============ CONVERSATIONS ============

def add_message(user_id: int, role: str, content: str) -> Dict:
    """Add a message to conversation history"""
    with get_db() as conn:
        with dict_cursor(conn) as cur:
            cur.execute(
                """INSERT INTO conversations (user_id, role, content)
                   VALUES (%s, %s, %s) RETURNING *""",
                (user_id, role, content)
            )
            return cur.fetchone()


def get_conversation_history(user_id: int, limit: int = 20) -> List[Dict]:
    """Get recent conversation history"""
    with get_db() as conn:
        with dict_cursor(conn) as cur:
            cur.execute(
                """SELECT role, content FROM conversations 
                   WHERE user_id = %s
                   ORDER BY created_at DESC LIMIT %s""",
                (user_id, limit)
            )
            # Return in chronological order
            return list(reversed(cur.fetchall()))


def clear_conversation_history(user_id: int) -> int:
    """Clear conversation history for a user"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM conversations WHERE user_id = %s", (user_id,))
            return cur.rowcount

"""
AnyArchie Reminders
Parses natural language time expressions and manages reminders
"""
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple
from . import db


def parse_time(time_str: str, reference: Optional[datetime] = None) -> Optional[datetime]:
    """
    Parse a time string into a datetime.
    
    Supports:
    - "3pm", "3:30pm", "15:00"
    - "in 30 minutes", "in 2 hours"
    - "tomorrow at 3pm", "tomorrow 3pm"
    - "monday at 2pm"
    
    Args:
        time_str: The time expression to parse
        reference: Reference datetime (defaults to now)
    
    Returns:
        datetime or None if couldn't parse
    """
    if reference is None:
        reference = datetime.now()
    
    time_str = time_str.lower().strip()
    
    # "in X minutes/hours"
    in_match = re.match(r'in\s+(\d+)\s*(min|minute|minutes|hour|hours|hr|hrs)', time_str)
    if in_match:
        amount = int(in_match.group(1))
        unit = in_match.group(2)
        if 'hour' in unit or 'hr' in unit:
            return reference + timedelta(hours=amount)
        else:
            return reference + timedelta(minutes=amount)
    
    # Parse time part (e.g., "3pm", "3:30pm", "15:00")
    time_part = None
    time_patterns = [
        (r'(\d{1,2}):(\d{2})\s*(am|pm)', lambda m: _parse_12h(int(m.group(1)), int(m.group(2)), m.group(3))),
        (r'(\d{1,2})\s*(am|pm)', lambda m: _parse_12h(int(m.group(1)), 0, m.group(2))),
        (r'(\d{1,2}):(\d{2})', lambda m: (int(m.group(1)), int(m.group(2)))),
    ]
    
    for pattern, parser in time_patterns:
        match = re.search(pattern, time_str)
        if match:
            time_part = parser(match)
            break
    
    if time_part is None:
        return None
    
    hour, minute = time_part
    
    # Check for "tomorrow"
    if 'tomorrow' in time_str:
        target = reference + timedelta(days=1)
        return target.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    # Check for day of week
    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    for i, day in enumerate(days):
        if day in time_str:
            current_day = reference.weekday()
            days_ahead = i - current_day
            if days_ahead <= 0:
                days_ahead += 7
            target = reference + timedelta(days=days_ahead)
            return target.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    # Just a time - assume today, or tomorrow if time has passed
    target = reference.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= reference:
        target += timedelta(days=1)
    
    return target


def _parse_12h(hour: int, minute: int, ampm: str) -> Tuple[int, int]:
    """Convert 12-hour time to 24-hour"""
    if ampm == 'pm' and hour != 12:
        hour += 12
    elif ampm == 'am' and hour == 12:
        hour = 0
    return (hour, minute)


def parse_reminder_command(text: str) -> Tuple[Optional[datetime], Optional[str]]:
    """
    Parse a reminder command like "/remind 3pm call mom" or "remind me tomorrow at 2pm to buy milk"
    
    Returns:
        Tuple of (remind_at datetime, message) or (None, None) if couldn't parse
    """
    # Remove command prefix if present
    text = re.sub(r'^/remind\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^remind\s+me\s+', '', text, flags=re.IGNORECASE)
    
    # Try to find time at the start
    # Pattern: time expression followed by message
    patterns = [
        # "tomorrow at 3pm call mom"
        r'^(tomorrow\s+(?:at\s+)?\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s+(?:to\s+)?(.+)',
        # "3pm call mom"
        r'^(\d{1,2}(?::\d{2})?\s*(?:am|pm))\s+(?:to\s+)?(.+)',
        # "in 30 minutes call mom"
        r'^(in\s+\d+\s*(?:min|minute|minutes|hour|hours|hr|hrs))\s+(?:to\s+)?(.+)',
        # "monday at 2pm call mom"
        r'^((?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+(?:at\s+)?\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s+(?:to\s+)?(.+)',
    ]
    
    for pattern in patterns:
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            time_str = match.group(1)
            message = match.group(2).strip()
            remind_at = parse_time(time_str)
            if remind_at:
                return (remind_at, message)
    
    return (None, None)


def create_reminder(user_id: int, message: str, remind_at: datetime) -> dict:
    """Create a reminder in the database"""
    return db.add_reminder(user_id, message, remind_at)


def format_reminder_time(dt: datetime) -> str:
    """Format a datetime for display"""
    now = datetime.now()
    
    if dt.date() == now.date():
        return f"today at {dt.strftime('%I:%M %p').lstrip('0')}"
    elif dt.date() == (now + timedelta(days=1)).date():
        return f"tomorrow at {dt.strftime('%I:%M %p').lstrip('0')}"
    else:
        return dt.strftime('%A, %b %d at %I:%M %p').replace(' 0', ' ')

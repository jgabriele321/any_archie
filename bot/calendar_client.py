"""
AnyArchie Google Calendar Client
Uses service account authentication with encrypted credentials
"""
import os
import json
import tempfile
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass

from google.oauth2 import service_account
from googleapiclient.discovery import build

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import credential_manager

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']


@dataclass
class CalendarEvent:
    """Represents a calendar event"""
    summary: str
    start: datetime
    end: datetime
    location: Optional[str] = None
    description: Optional[str] = None
    is_all_day: bool = False


def get_calendar_service_from_creds(credentials_dict: Dict):
    """
    Create a Google Calendar service from credentials dict.
    
    Args:
        credentials_dict: Service account credentials as dict
    
    Returns:
        Google Calendar API service object
    """
    credentials = service_account.Credentials.from_service_account_info(
        credentials_dict, scopes=SCOPES
    )
    return build('calendar', 'v3', credentials=credentials)


def get_calendar_service(credentials_path: str):
    """
    Create a Google Calendar service using service account credentials file.
    
    Args:
        credentials_path: Path to the service account JSON file
    
    Returns:
        Google Calendar API service object
    """
    credentials = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=SCOPES
    )
    return build('calendar', 'v3', credentials=credentials)


def fetch_events_from_user(
    user_id: int,
    days: int = 7,
    max_results: int = 20
) -> List[CalendarEvent]:
    """
    Fetch events using user's stored credentials.
    
    Args:
        user_id: Database user ID
        days: Number of days ahead to fetch
        max_results: Maximum number of events to return
    
    Returns:
        List of CalendarEvent objects
    """
    # Get credentials from database
    creds_data = credential_manager.get_user_credential(user_id, "google_calendar")
    if not creds_data:
        raise RuntimeError("Google Calendar not configured. Use /setup google to configure.")
    
    # Get calendar ID from context
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from bot import db
    calendar_id = db.get_context(user_id, "calendar_id")
    if not calendar_id:
        raise RuntimeError("Calendar ID not set. Complete setup with /setup google")
    
    service = get_calendar_service_from_creds(creds_data)
    
    now = datetime.utcnow()
    time_min = now.isoformat() + 'Z'
    time_max = (now + timedelta(days=days)).isoformat() + 'Z'
    
    try:
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
    except Exception as e:
        raise RuntimeError(f"Failed to fetch calendar: {str(e)}")
    
    events = []
    for item in events_result.get('items', []):
        start_data = item.get('start', {})
        end_data = item.get('end', {})
        
        if 'dateTime' in start_data:
            start = datetime.fromisoformat(start_data['dateTime'].replace('Z', '+00:00'))
            end = datetime.fromisoformat(end_data['dateTime'].replace('Z', '+00:00'))
            is_all_day = False
        else:
            start = datetime.strptime(start_data['date'], '%Y-%m-%d')
            end = datetime.strptime(end_data['date'], '%Y-%m-%d')
            is_all_day = True
        
        events.append(CalendarEvent(
            summary=item.get('summary', '(No title)'),
            start=start,
            end=end,
            location=item.get('location'),
            description=item.get('description'),
            is_all_day=is_all_day
        ))
    
    return events


def fetch_events(
    credentials_path: str,
    calendar_id: str,
    days: int = 7,
    max_results: int = 20
) -> List[CalendarEvent]:
    """
    Fetch upcoming events from a calendar.
    
    Args:
        credentials_path: Path to service account JSON
        calendar_id: The calendar ID (usually the user's email)
        days: Number of days ahead to fetch
        max_results: Maximum number of events to return
    
    Returns:
        List of CalendarEvent objects
    """
    service = get_calendar_service(credentials_path)
    
    now = datetime.utcnow()
    time_min = now.isoformat() + 'Z'
    time_max = (now + timedelta(days=days)).isoformat() + 'Z'
    
    try:
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
    except Exception as e:
        raise RuntimeError(f"Failed to fetch calendar: {str(e)}")
    
    events = []
    for item in events_result.get('items', []):
        # Handle all-day events vs timed events
        start_data = item.get('start', {})
        end_data = item.get('end', {})
        
        if 'dateTime' in start_data:
            # Timed event
            start = datetime.fromisoformat(start_data['dateTime'].replace('Z', '+00:00'))
            end = datetime.fromisoformat(end_data['dateTime'].replace('Z', '+00:00'))
            is_all_day = False
        else:
            # All-day event
            start = datetime.strptime(start_data['date'], '%Y-%m-%d')
            end = datetime.strptime(end_data['date'], '%Y-%m-%d')
            is_all_day = True
        
        events.append(CalendarEvent(
            summary=item.get('summary', '(No title)'),
            start=start,
            end=end,
            location=item.get('location'),
            description=item.get('description'),
            is_all_day=is_all_day
        ))
    
    return events


def get_today_events(credentials_path: str, calendar_id: str) -> List[CalendarEvent]:
    """Get events for today only"""
    return fetch_events(credentials_path, calendar_id, days=1)


def get_calendar_digest_for_user(user_id: int, days: int = 7) -> str:
    """
    Get calendar digest using user's stored credentials.
    
    Returns:
        Formatted string with events grouped by day
    """
    try:
        events = fetch_events_from_user(user_id, days=days)
    except RuntimeError as e:
        return f"❌ {str(e)}"
    except Exception as e:
        return f"❌ Couldn't fetch calendar: {str(e)}"
    
    if not events:
        return f"📅 No events in the next {days} days."
    
    lines = [f"📅 **Your Calendar** (next {days} days)\n"]
    
    current_date = None
    for event in events:
        event_date = event.start.date()
        
        if event_date != current_date:
            current_date = event_date
            if event_date == datetime.now().date():
                date_str = "**Today**"
            elif event_date == (datetime.now() + timedelta(days=1)).date():
                date_str = "**Tomorrow**"
            else:
                date_str = f"**{event_date.strftime('%A, %b %d')}**"
            lines.append(f"\n{date_str}")
        
        if event.is_all_day:
            time_str = "All day"
        else:
            time_str = event.start.strftime('%I:%M %p').lstrip('0')
        
        lines.append(f"• {time_str} - {event.summary}")
        
        if event.location:
            lines.append(f"  📍 {event.location[:40]}")
    
    return "\n".join(lines)


def get_calendar_digest(
    credentials_path: str,
    calendar_id: str,
    days: int = 7
) -> str:
    """
    Get a formatted digest of upcoming calendar events.
    
    Returns:
        Formatted string with events grouped by day
    """
    try:
        events = fetch_events(credentials_path, calendar_id, days=days)
    except RuntimeError as e:
        return f"❌ {str(e)}"
    except Exception as e:
        return f"❌ Couldn't fetch calendar: {str(e)}"
    
    if not events:
        return f"📅 No events in the next {days} days."
    
    lines = [f"📅 **Your Calendar** (next {days} days)\n"]
    
    # Group by date
    current_date = None
    for event in events:
        event_date = event.start.date()
        
        if event_date != current_date:
            current_date = event_date
            # Format date header
            if event_date == datetime.now().date():
                date_str = "**Today**"
            elif event_date == (datetime.now() + timedelta(days=1)).date():
                date_str = "**Tomorrow**"
            else:
                date_str = f"**{event_date.strftime('%A, %b %d')}**"
            lines.append(f"\n{date_str}")
        
        # Format event
        if event.is_all_day:
            time_str = "All day"
        else:
            time_str = event.start.strftime('%I:%M %p').lstrip('0')
        
        lines.append(f"• {time_str} - {event.summary}")
        
        if event.location:
            lines.append(f"  📍 {event.location[:40]}")
    
    return "\n".join(lines)


def get_today_digest(credentials_path: str, calendar_id: str) -> str:
    """Get a formatted digest of today's events"""
    try:
        events = get_today_events(credentials_path, calendar_id)
    except Exception as e:
        return f"❌ Couldn't fetch calendar: {str(e)}"
    
    if not events:
        return "📅 No events scheduled for today!"
    
    lines = ["📅 **Today's Schedule**\n"]
    
    for event in events:
        if event.is_all_day:
            time_str = "All day"
        else:
            time_str = event.start.strftime('%I:%M %p').lstrip('0')
        
        lines.append(f"• {time_str} - {event.summary}")
        
        if event.location:
            lines.append(f"  📍 {event.location[:40]}")
    
    return "\n".join(lines)

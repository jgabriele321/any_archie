"""
Calendar skill for AnyArchie.

Handles Google Calendar integration with self-service setup.
"""
from typing import Any, Callable, Dict, List, Optional

from .base import BaseSkill, CommandInfo, LLMActionInfo
from . import register_skill
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import db
from bot import calendar_client
from bot import credential_manager


@register_skill
class CalendarSkill(BaseSkill):
    """Skill for calendar management."""
    
    @property
    def name(self) -> str:
        return "calendar"
    
    @property
    def commands(self) -> List[CommandInfo]:
        return [
            CommandInfo("/calendar", "Show calendar events", "/calendar [today|days]"),
            CommandInfo("/cal", "Alias for /calendar", "/cal"),
        ]
    
    @property
    def llm_actions(self) -> List[LLMActionInfo]:
        return []
    
    def handle_command(
        self,
        user_id: int,
        command: str,
        args: str,
        send_message: Callable[[int, str], None],
        send_document: Callable[[int, Any, str], None] = None,
        send_photo: Callable[[int, bytes, str], None] = None,
    ) -> bool:
        """Handle calendar-related commands."""
        user = db.get_user_by_id(user_id)
        if not user:
            return False
        
        telegram_id = user['telegram_id']
        cmd_lower = command.lower()
        
        if cmd_lower.startswith("/calendar") or cmd_lower.startswith("/cal"):
            self._handle_calendar(user_id, args, send_message, telegram_id)
            return True
        
        return False
    
    def _handle_calendar(self, user_id: int, args: str, send_message: Callable, telegram_id: int) -> None:
        """Handle /calendar command."""
        # Check if calendar is configured
        creds = credential_manager.get_user_credential(user_id, "google_calendar")
        if not creds:
            send_message(
                telegram_id,
                "📅 Calendar not set up yet!\n\n"
                "Use `/setup google` to connect your Google Calendar."
            )
            return
        
        # Parse argument
        arg = args.strip().lower() if args else ""
        
        if arg == "today":
            try:
                events = calendar_client.fetch_events_from_user(user_id, days=1)
                if not events:
                    send_message(telegram_id, "📅 No events scheduled for today!")
                    return
                
                lines = ["📅 **Today's Schedule**\n"]
                for event in events:
                    if event.is_all_day:
                        time_str = "All day"
                    else:
                        time_str = event.start.strftime('%I:%M %p').lstrip('0')
                    lines.append(f"• {time_str} - {event.summary}")
                    if event.location:
                        lines.append(f"  📍 {event.location[:40]}")
                
                send_message(telegram_id, "\n".join(lines))
            except Exception as e:
                send_message(telegram_id, f"❌ Error fetching calendar: {str(e)[:100]}")
        else:
            # Default to 7 days, or parse number
            days = 7
            if arg:
                try:
                    days = min(int(arg), 30)
                except ValueError:
                    pass
            
            try:
                digest = calendar_client.get_calendar_digest_for_user(user_id, days=days)
                send_message(telegram_id, digest)
            except Exception as e:
                send_message(telegram_id, f"❌ Error fetching calendar: {str(e)[:100]}")
    
    def handle_llm_action(self, user_id: int, action: str, response: str) -> Optional[str]:
        """Handle LLM actions for calendar."""
        return None
    
    def get_help_text(self) -> str:
        """Return help text for calendar commands."""
        return """**Calendar:**
- `/calendar` - Next 7 days
- `/calendar today` - Today's schedule
- `/calendar 14` - Next 14 days

Use `/setup google` to connect your Google Calendar."""
    
    def get_llm_prompt_section(self) -> str:
        """Return LLM prompt section for calendar."""
        return ""
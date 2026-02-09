"""
Email skill for AnyArchie.

Handles Gmail integration with self-service setup.
"""
from typing import Any, Callable, Dict, List, Optional

from .base import BaseSkill, CommandInfo, LLMActionInfo
from . import register_skill
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import db
from bot import email_client
from bot import credential_manager


@register_skill
class EmailSkill(BaseSkill):
    """Skill for email management."""
    
    @property
    def name(self) -> str:
        return "email"
    
    @property
    def commands(self) -> List[CommandInfo]:
        return [
            CommandInfo("/emails", "Get email digest", "/emails [hours]"),
            CommandInfo("/emailsearch", "Search emails", "/emailsearch <query>"),
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
        """Handle email-related commands."""
        user = db.get_user_by_id(user_id)
        if not user:
            return False
        
        telegram_id = user['telegram_id']
        cmd_lower = command.lower()
        
        if cmd_lower.startswith("/emails"):
            self._handle_emails(user_id, args, send_message, telegram_id)
            return True
        
        elif cmd_lower.startswith("/emailsearch"):
            self._handle_email_search(user_id, args, send_message, telegram_id)
            return True
        
        return False
    
    def _handle_emails(self, user_id: int, args: str, send_message: Callable, telegram_id: int) -> None:
        """Handle /emails command."""
        # Check if Gmail is configured
        creds = credential_manager.get_user_credential(user_id, "gmail")
        if not creds:
            send_message(
                telegram_id,
                "📧 Gmail not set up yet!\n\n"
                "Use `/setup google` to connect your Gmail."
            )
            return
        
        # Parse hours argument (default 24, max 72)
        hours = 24
        if args:
            try:
                hours = min(int(args.strip()), 72)
            except ValueError:
                pass
        
        try:
            email_address = creds.get('email')
            app_password = creds.get('password')
            
            if not email_address or not app_password:
                send_message(telegram_id, "❌ Gmail credentials incomplete. Re-run `/setup google`")
                return
            
            digest = email_client.get_email_digest(
                email_address=email_address,
                app_password=app_password,
                hours=hours,
                imap_server='imap.gmail.com'
            )
            send_message(telegram_id, digest)
        except Exception as e:
            send_message(telegram_id, f"❌ Error fetching emails: {str(e)[:200]}")
    
    def _handle_email_search(self, user_id: int, args: str, send_message: Callable, telegram_id: int) -> None:
        """Handle /emailsearch command."""
        creds = credential_manager.get_user_credential(user_id, "gmail")
        if not creds:
            send_message(
                telegram_id,
                "📧 Gmail not set up yet!\n\n"
                "Use `/setup google` to connect your Gmail."
            )
            return
        
        if not args.strip():
            send_message(telegram_id, "Usage: /emailsearch <query>")
            return
        
        try:
            email_address = creds.get('email')
            app_password = creds.get('password')
            
            if not email_address or not app_password:
                send_message(telegram_id, "❌ Gmail credentials incomplete. Re-run `/setup google`")
                return
            
            results = email_client.search_emails(
                email_address=email_address,
                app_password=app_password,
                query=args.strip(),
                imap_server='imap.gmail.com'
            )
            
            if not results:
                send_message(telegram_id, f"No emails found matching '{args.strip()}'")
                return
            
            lines = [f"🔍 Found {len(results)} email(s):\n"]
            for email in results[:10]:
                lines.append(f"• {email.get('subject', '(No subject)')}")
                lines.append(f"  From: {email.get('from', 'Unknown')}")
                lines.append(f"  Date: {email.get('date', 'Unknown')}\n")
            
            if len(results) > 10:
                lines.append(f"\n...and {len(results) - 10} more")
            
            send_message(telegram_id, "\n".join(lines))
        except Exception as e:
            send_message(telegram_id, f"❌ Error searching emails: {str(e)[:200]}")
    
    def handle_llm_action(self, user_id: int, action: str, response: str) -> Optional[str]:
        """Handle LLM actions for email."""
        return None
    
    def get_help_text(self) -> str:
        """Return help text for email commands."""
        return """**Email:**
- `/emails` - Email digest (last 24 hours)
- `/emails 12` - Last 12 hours
- `/emails 72` - Last 72 hours (3 days)
- `/emailsearch <query>` - Search emails

Use `/setup google` to connect your Gmail."""
    
    def get_llm_prompt_section(self) -> str:
        """Return LLM prompt section for email."""
        return ""
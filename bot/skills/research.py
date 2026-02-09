"""
Research skill for AnyArchie.

Handles web search via Exa API.
"""
from typing import Any, Callable, Dict, List, Optional

from .base import BaseSkill, CommandInfo, LLMActionInfo
from . import register_skill
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import db
from bot import research


@register_skill
class ResearchSkill(BaseSkill):
    """Skill for web research."""
    
    @property
    def name(self) -> str:
        return "research"
    
    @property
    def commands(self) -> List[CommandInfo]:
        return [
            CommandInfo("/search", "Search the web", "/search <query>"),
            CommandInfo("/research", "Deep research on a topic", "/research <topic>"),
        ]
    
    @property
    def llm_actions(self) -> List[LLMActionInfo]:
        return [
            LLMActionInfo("SEARCH_WEB", "Search the web", r'\[SEARCH_WEB:\s*["\']?(.+?)["\']?\]'),
        ]
    
    def handle_command(
        self,
        user_id: int,
        command: str,
        args: str,
        send_message: Callable[[int, str], None],
        send_document: Callable[[int, Any, str], None] = None,
        send_photo: Callable[[int, bytes, str], None] = None,
    ) -> bool:
        """Handle research-related commands."""
        user = db.get_user_by_id(user_id)
        if not user:
            return False
        
        telegram_id = user['telegram_id']
        cmd_lower = command.lower()
        
        if cmd_lower.startswith("/search"):
            self._handle_search(user_id, args, send_message, telegram_id)
            return True
        
        elif cmd_lower.startswith("/research"):
            self._handle_research(user_id, args, send_message, telegram_id)
            return True
        
        return False
    
    def _handle_search(self, user_id: int, args: str, send_message: Callable, telegram_id: int) -> None:
        """Handle /search command."""
        if not args.strip():
            send_message(telegram_id, "Usage: /search <query>\n\nExample: /search latest AI news")
            return
        
        query = args.strip()
        try:
            results = research.search(query, num_results=5)
            if not results:
                send_message(telegram_id, f"No results found for '{query}'")
                return
            
            formatted = research.format_search_results(results)
            # Truncate if too long for Telegram (4096 char limit)
            if len(formatted) > 4000:
                formatted = formatted[:3997] + "..."
            send_message(telegram_id, formatted)
        except Exception as e:
            send_message(telegram_id, f"❌ Error searching: {str(e)[:100]}")
    
    def _handle_research(self, user_id: int, args: str, send_message: Callable, telegram_id: int) -> None:
        """Handle /research command (same as search for now)"""
        self._handle_search(user_id, args, send_message, telegram_id)
    
    def handle_llm_action(self, user_id: int, action: str, response: str) -> Optional[str]:
        """Handle LLM actions for research."""
        import re
        
        if action == "SEARCH_WEB":
            search_match = re.search(r'\[SEARCH_WEB:\s*["\']?(.+?)["\']?\]', response, re.IGNORECASE)
            if search_match:
                query = search_match.group(1).strip()
                try:
                    results = research.search(query, num_results=3)
                    if results:
                        # Format for LLM context
                        formatted = "\n".join([
                            f"- {r['title']}: {r['snippet'][:200]}"
                            for r in results
                        ])
                        return f"Search results for '{query}':\n{formatted}"
                    else:
                        return f"No results found for '{query}'"
                except Exception as e:
                    return f"Search error: {str(e)[:100]}"
        
        return None
    
    def get_help_text(self) -> str:
        """Return help text for research commands."""
        return """**Research:**
- `/search <query>` - Search the web
- `/research <topic>` - Deep research on a topic

I can search the internet for current information!"""
    
    def get_llm_prompt_section(self) -> str:
        """Return LLM prompt section for research."""
        return """**Web Search:**
You can search the web using:
- [SEARCH_WEB: "query"] - Search for current information

Use this when users ask about current events, recent news, or need up-to-date information."""
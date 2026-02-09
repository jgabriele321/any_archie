"""
Memory skill for AnyArchie.

Handles persistent memory - facts, observations, and context about the user.
"""
import re
from typing import Any, Callable, Dict, List, Optional

from .base import BaseSkill, CommandInfo, LLMActionInfo
from . import register_skill
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import db


@register_skill
class MemorySkill(BaseSkill):
    """Skill for persistent memory management."""
    
    @property
    def name(self) -> str:
        return "memory"
    
    @property
    def commands(self) -> List[CommandInfo]:
        return [
            CommandInfo("/remember", "Remember a fact", "/remember <fact>"),
            CommandInfo("/facts", "List facts", "/facts [category] [subject]"),
            CommandInfo("/searchfacts", "Search facts", "/searchfacts <query>"),
        ]
    
    @property
    def llm_actions(self) -> List[LLMActionInfo]:
        return [
            LLMActionInfo("REMEMBER_FACT", "Remember a fact", r'\[REMEMBER_FACT:\s*["\']?(.+?)["\']?\]'),
            LLMActionInfo("GET_FACTS", "Get facts", r'\[GET_FACTS(?::\s*(\w+))?(?::\s*(\w+))?\]'),
            LLMActionInfo("SEARCH_FACTS", "Search facts", r'\[SEARCH_FACTS:\s*["\']?(.+?)["\']?\]'),
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
        """Handle memory-related commands."""
        user = db.get_user_by_id(user_id)
        if not user:
            return False
        
        telegram_id = user['telegram_id']
        cmd_lower = command.lower()
        
        if cmd_lower.startswith("/remember"):
            self._handle_remember(user_id, args, send_message, telegram_id)
            return True
        
        elif cmd_lower.startswith("/facts"):
            self._handle_facts(user_id, args, send_message, telegram_id)
            return True
        
        elif cmd_lower.startswith("/searchfacts"):
            self._handle_search_facts(user_id, args, send_message, telegram_id)
            return True
        
        return False
    
    def _handle_remember(self, user_id: int, args: str, send_message: Callable, telegram_id: int) -> None:
        """Handle /remember command."""
        if not args.strip():
            send_message(
                telegram_id,
                "Usage: /remember <fact>\n\n"
                "Example: /remember I prefer morning workouts"
            )
            return
        
        # Try to parse category and subject from the fact
        # Simple heuristic: if it starts with "I" or "My", it's about the user
        fact_text = args.strip()
        category = "general"
        subject = "user"
        
        if fact_text.lower().startswith(("i ", "my ", "i'm ", "i've ")):
            category = "preference"
        elif "like" in fact_text.lower() or "prefer" in fact_text.lower():
            category = "preference"
        elif "goal" in fact_text.lower() or "want" in fact_text.lower():
            category = "goal"
        
        try:
            fact = db.add_fact(
                user_id=user_id,
                category=category,
                subject=subject,
                content=fact_text,
                source="explicit"
            )
            send_message(
                telegram_id,
                f"✅ Remembered: {fact_text}\n\n"
                f"Category: {category}\n"
                f"ID: {fact['id']}"
            )
        except Exception as e:
            send_message(telegram_id, f"Error remembering fact: {str(e)[:100]}")
    
    def _handle_facts(self, user_id: int, args: str, send_message: Callable, telegram_id: int) -> None:
        """Handle /facts command."""
        parts = args.split() if args else []
        category = parts[0] if len(parts) > 0 else None
        subject = parts[1] if len(parts) > 1 else None
        
        try:
            facts = db.get_facts(user_id, category=category, subject=subject, limit=20)
            
            if not facts:
                msg = "No facts found."
                if category:
                    msg += f" (category: {category})"
                if subject:
                    msg += f" (subject: {subject})"
                send_message(telegram_id, msg)
                return
            
            lines = [f"📝 **Facts** ({len(facts)})\n"]
            if category:
                lines[0] = f"📝 **Facts - {category}** ({len(facts)})\n"
            
            for f in facts:
                lines.append(f"• {f['content']}")
                if f['category'] != category:
                    lines[-1] += f" [{f['category']}]"
            
            send_message(telegram_id, "\n".join(lines))
        except Exception as e:
            send_message(telegram_id, f"Error getting facts: {str(e)[:100]}")
    
    def _handle_search_facts(self, user_id: int, args: str, send_message: Callable, telegram_id: int) -> None:
        """Handle /searchfacts command."""
        if not args.strip():
            send_message(telegram_id, "Usage: /searchfacts <query>")
            return
        
        query = args.strip()
        try:
            facts = db.search_facts(user_id, query, limit=20)
            
            if not facts:
                send_message(telegram_id, f"No facts found matching '{query}'.")
                return
            
            lines = [f"🔍 Found {len(facts)} fact(s) matching '{query}':\n"]
            for f in facts:
                lines.append(f"• {f['content']} [{f['category']}]")
            
            send_message(telegram_id, "\n".join(lines))
        except Exception as e:
            send_message(telegram_id, f"Error searching: {str(e)[:100]}")
    
    def handle_llm_action(self, user_id: int, action: str, response: str) -> Optional[str]:
        """Handle LLM actions for memory."""
        results = []
        
        # [REMEMBER_FACT: "fact"]
        remember_match = re.search(r'\[REMEMBER_FACT:\s*["\']?(.+?)["\']?\]', response, re.IGNORECASE)
        if remember_match:
            fact_text = remember_match.group(1).strip()
            category = "general"
            subject = "user"
            
            # Simple categorization
            if any(word in fact_text.lower() for word in ["like", "prefer", "enjoy"]):
                category = "preference"
            elif any(word in fact_text.lower() for word in ["goal", "want", "plan"]):
                category = "goal"
            
            try:
                fact = db.add_fact(
                    user_id=user_id,
                    category=category,
                    subject=subject,
                    content=fact_text,
                    source="inferred"
                )
                results.append(f"✅ Remembered: {fact_text}")
            except Exception as e:
                results.append(f"Error remembering: {str(e)[:50]}")
        
        # [GET_FACTS: category: subject]
        get_match = re.search(r'\[GET_FACTS(?::\s*(\w+))?(?::\s*(\w+))?\]', response, re.IGNORECASE)
        if get_match:
            category = get_match.group(1) if get_match.group(1) else None
            subject = get_match.group(2) if get_match.group(2) else None
            
            try:
                facts = db.get_facts(user_id, category=category, subject=subject, limit=10)
                if facts:
                    fact_list = [f"• {f['content']}" for f in facts]
                    results.append(f"📝 Facts:\n" + "\n".join(fact_list))
                else:
                    results.append("No facts found.")
            except Exception as e:
                results.append(f"Error getting facts: {str(e)[:50]}")
        
        # [SEARCH_FACTS: "query"]
        search_match = re.search(r'\[SEARCH_FACTS:\s*["\']?(.+?)["\']?\]', response, re.IGNORECASE)
        if search_match:
            query = search_match.group(1).strip()
            try:
                facts = db.search_facts(user_id, query, limit=10)
                if facts:
                    fact_list = [f"• {f['content']}" for f in facts]
                    results.append(f"🔍 Found {len(facts)} fact(s):\n" + "\n".join(fact_list))
                else:
                    results.append(f"No facts found matching '{query}'.")
            except Exception as e:
                results.append(f"Error searching: {str(e)[:50]}")
        
        return "\n".join(results) if results else None
    
    def get_help_text(self) -> str:
        """Return help text for memory commands."""
        return """**Memory:**
- `/remember <fact>` - Remember a fact about yourself
- `/facts [category] [subject]` - List facts
- `/searchfacts <query>` - Search facts

I automatically remember important things you tell me!"""
    
    def get_llm_prompt_section(self) -> str:
        """Return LLM prompt section for memory."""
        return """**Memory System:**
You can remember facts about the user using:
- [REMEMBER_FACT: "fact"] - Remember something about the user
- [GET_FACTS: category: subject] - Retrieve facts (category/subject optional)
- [SEARCH_FACTS: "query"] - Search facts by content

When users share preferences, goals, or important information, remember it using REMEMBER_FACT.
Categories include: preference, goal, routine, relationship, context."""
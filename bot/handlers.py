"""
AnyArchie Command Handlers
Handles /commands and natural language processing
Integrates skills system for modular features
"""
import re
from datetime import datetime, date
from typing import Optional, Tuple, Callable
from . import db
from . import llm
from . import research
from . import reminders as reminder_module
from . import email_client
from . import calendar_client
from . import credential_manager
from . import onboarding
from .skills import route_command, route_llm_actions, clean_llm_response, get_combined_help_text


def handle_command(
    user_id: int, 
    text: str, 
    user: dict,
    send_message: Callable[[int, str], None],
    send_document: Callable[[int, any, str], None] = None,
    send_photo: Callable[[int, bytes, str], None] = None,
) -> Optional[str]:
    """
    Handle a command or message from the user.
    
    Args:
        user_id: Database user ID
        text: The message text
        user: User dict from database
        send_message: Function to send message (takes telegram_id, message)
        send_document: Function to send document
        send_photo: Function to send photo
    
    Returns:
        Response message if handled synchronously, None if handled asynchronously
    """
    text = text.strip()
    telegram_id = user['telegram_id']
    
    # Handle /start command - restart onboarding
    # NOTE: This should only be called for users who completed onboarding.
    # /start during onboarding is handled in main.py and should not reach here.
    if text.lower() == "/start" or text.lower().startswith("/start "):
        # #region agent log
        import json as _json; open('/Users/giovannigabriele/Documents/Code/AnyArchie/.cursor/debug.log','a').write(_json.dumps({"location":"handlers.py:46","message":"HANDLERS.PY /start handler ENTRY","data":{"user_id":user_id,"telegram_id":telegram_id,"text":text,"onboarding_state":user.get('onboarding_state')},"timestamp":__import__('time').time()*1000,"hypothesisId":"B"})+'\n')
        # #endregion
        # Safety check: if user is in onboarding, this shouldn't be called
        # (main.py should have handled it already)
        if user.get('onboarding_state', 'new') != 'complete':
            # #region agent log
            import json as _json; open('/Users/giovannigabriele/Documents/Code/AnyArchie/.cursor/debug.log','a').write(_json.dumps({"location":"handlers.py:52","message":"HANDLERS.PY /start BLOCKED - user in onboarding","data":{"user_id":user_id,"state":user.get('onboarding_state')},"timestamp":__import__('time').time()*1000,"hypothesisId":"B"})+'\n')
            # #endregion
            return None
        db.update_user(user_id, onboarding_state='new')
        message, _ = onboarding.get_onboarding_message("new")
        send_message(telegram_id, message)
        return None
    
    # Check if user is in credential setup flow
    setup_handled = credential_manager.handle_setup_message(user_id, text, send_message)
    if setup_handled:
        return None  # Setup flow handles its own responses
    
    # Check if user is in onboarding
    onboarding_state = user.get('onboarding_state', 'new')
    if onboarding_state != 'complete':
        # Skip /start during onboarding - it's already handled
        if text.lower() == "/start" or text.lower().startswith("/start "):
            return None
        
        # #region agent log
        import json as _json; open('/Users/giovannigabriele/Documents/Code/AnyArchie/.cursor/debug.log','a').write(_json.dumps({"location":"handlers.py:64","message":"HANDLERS.PY onboarding handler","data":{"user_id":user_id,"state":onboarding_state,"text":text[:30]},"timestamp":__import__('time').time()*1000,"hypothesisId":"B"})+'\n')
        # #endregion
        message, is_complete = onboarding.process_onboarding_step(user_id, onboarding_state, text)
        send_message(telegram_id, message)
        if is_complete:
            db.update_user(user_id, onboarding_state='complete')
        return None
    
    # Command routing
    if text.startswith('/'):
        cmd_parts = text.split(maxsplit=1)
        cmd = cmd_parts[0].lower()
        arg = cmd_parts[1] if len(cmd_parts) > 1 else ""
        
        # Special commands
        if cmd == '/setup' and arg.lower().startswith('google'):
            credential_manager.start_setup(user_id, send_message)
            return None
        
        # Heartbeat commands
        if cmd == '/mute':
            from .heartbeat_worker import mute_user_heartbeat
            from datetime import timedelta
            import yaml
            from pathlib import Path
            
            config_path = Path(__file__).parent.parent / "heartbeat.yaml"
            if config_path.exists():
                with open(config_path) as f:
                    config = yaml.safe_load(f) or {}
                duration = config.get("mute_duration_minutes", 120)
            else:
                duration = 120
            
            mute_user_heartbeat(user_id, duration)
            send_message(telegram_id, f"🔇 Heartbeat notifications muted for {duration} minutes. Use /unmute to restore.")
            return None
        
        if cmd == '/unmute':
            from .heartbeat_worker import unmute_user_heartbeat
            unmute_user_heartbeat(user_id)
            send_message(telegram_id, "🔔 Heartbeat notifications restored!")
            return None
        
        # Try skills system first
        skill_handled = route_command(
            user_id=user_id,
            command=cmd,
            args=arg,
            send_message=send_message,
            send_document=send_document,
            send_photo=send_photo,
        )
        
        if skill_handled:
            return None  # Skill handled it
        
        # Fallback to legacy commands for backward compatibility
        if cmd == '/add':
            response = cmd_add(user_id, arg)
            send_message(telegram_id, response)
            return None
        elif cmd == '/today':
            response = cmd_today(user_id)
            send_message(telegram_id, response)
            return None
        elif cmd == '/done':
            response = cmd_done(user_id, arg)
            send_message(telegram_id, response)
            return None
        elif cmd == '/tasks':
            response = cmd_tasks(user_id)
            send_message(telegram_id, response)
            return None
        elif cmd == '/remind':
            response = cmd_remind(user_id, arg)
            send_message(telegram_id, response)
            return None
        elif cmd == '/reminders':
            response = cmd_list_reminders(user_id)
            send_message(telegram_id, response)
            return None
        elif cmd == '/clear':
            response = cmd_clear(user_id)
            send_message(telegram_id, response)
            return None
        elif cmd == '/help':
            response = cmd_help(user['assistant_name'])
            send_message(telegram_id, response)
            return None
        elif cmd == '/context':
            response = cmd_context(user_id)
            send_message(telegram_id, response)
            return None
        elif cmd == '/setcontext':
            response = cmd_set_context(user_id, arg)
            send_message(telegram_id, response)
            return None
        else:
            send_message(telegram_id, "Unknown command. Type /help to see available commands.")
            return None
    
    # Natural language processing via LLM
    response = handle_natural_language(user_id, text, user)
    send_message(telegram_id, response)
    return None


def handle_photo(user_id: int, photo_bytes: bytes, send_message: Callable[[int, str], None]) -> bool:
    """
    Handle photo upload - check if contacts skill can process it as business card.
    
    Returns:
        True if photo was handled, False otherwise
    """
    from .skills import get_skill
    
    contacts_skill = get_skill("contacts")
    if contacts_skill:
        return contacts_skill.handle_photo(user_id, photo_bytes, send_message)
    
    return False


def cmd_add(user_id: int, task_text: str) -> str:
    """Add a task"""
    if not task_text:
        return "What task do you want to add? Example: `/add Buy groceries`"
    
    task = db.add_task(user_id, task_text)
    return f"Added: {task_text}"


def cmd_today(user_id: int) -> str:
    """Show today's tasks"""
    tasks = db.get_tasks_due_today(user_id)
    
    if not tasks:
        return "No tasks for today! Use `/add <task>` to add one."
    
    lines = ["**Today's Tasks:**", ""]
    for i, task in enumerate(tasks, 1):
        status = "" if task['status'] == 'pending' else " "
        due = f" (due: {task['due_date']})" if task['due_date'] else ""
        lines.append(f"{i}. {status}{task['content']}{due}")
    
    return "\n".join(lines)


def cmd_tasks(user_id: int) -> str:
    """Show all pending tasks"""
    tasks = db.get_tasks(user_id, status="pending")
    
    if not tasks:
        return "No pending tasks! Use `/add <task>` to add one."
    
    lines = ["**All Pending Tasks:**", ""]
    for i, task in enumerate(tasks, 1):
        due = f" (due: {task['due_date']})" if task['due_date'] else ""
        lines.append(f"{i}. {task['content']}{due}")
    
    return "\n".join(lines)


def cmd_done(user_id: int, arg: str) -> str:
    """Mark a task as done"""
    if not arg:
        return "Which task? Example: `/done 1` to complete task #1"
    
    try:
        task_num = int(arg.strip())
    except ValueError:
        return "Please provide a task number. Example: `/done 1`"
    
    # Get tasks to find the right one
    tasks = db.get_tasks(user_id, status="pending")
    if task_num < 1 or task_num > len(tasks):
        return f"Invalid task number. You have {len(tasks)} pending tasks."
    
    task = tasks[task_num - 1]
    db.complete_task(task['id'])
    
    return f"Completed: {task['content']}"


def cmd_remind(user_id: int, arg: str) -> str:
    """Set a reminder"""
    if not arg:
        return "When should I remind you? Example: `/remind 3pm Call mom`"
    
    remind_at, message = reminder_module.parse_reminder_command(arg)
    
    if not remind_at or not message:
        return ("Couldn't parse that reminder. Try:\n"
                "- `/remind 3pm Call mom`\n"
                "- `/remind tomorrow at 9am Check emails`\n"
                "- `/remind in 30 minutes Take a break`")
    
    reminder_module.create_reminder(user_id, message, remind_at)
    formatted_time = reminder_module.format_reminder_time(remind_at)
    
    return f"I'll remind you {formatted_time}: {message}"


def cmd_list_reminders(user_id: int) -> str:
    """List pending reminders"""
    reminders = db.get_user_reminders(user_id)
    
    if not reminders:
        return "No pending reminders."
    
    lines = ["**Upcoming Reminders:**", ""]
    for r in reminders:
        formatted_time = reminder_module.format_reminder_time(r['remind_at'])
        lines.append(f"- {formatted_time}: {r['message']}")
    
    return "\n".join(lines)


def cmd_search(query: str) -> str:
    """Search the web"""
    if not query:
        return "What do you want to search for? Example: `/search latest AI news`"
    
    results = research.search_and_summarize(query)
    return f"**Search Results for '{query}':**\n\n{results}"


def cmd_emails(user: dict, arg: str) -> str:
    """Get email digest"""
    # Check if user has email configured
    email_address = user.get('email_address')
    app_password = user.get('email_app_password')
    
    if not email_address or not app_password:
        return ("📧 Email not set up yet!\n\n"
                "To enable email digests, contact support to add your Gmail credentials.")
    
    # Parse hours argument (default 24, max 72)
    hours = 24
    if arg:
        try:
            hours = min(int(arg.strip()), 72)
        except ValueError:
            pass
    
    imap_server = user.get('email_imap_server', 'imap.gmail.com')
    
    return email_client.get_email_digest(
        email_address=email_address,
        app_password=app_password,
        hours=hours,
        imap_server=imap_server
    )


def cmd_calendar(user: dict, arg: str) -> str:
    """Get calendar digest"""
    # Check if user has calendar configured
    calendar_id = user.get('calendar_id')
    credentials_path = user.get('calendar_credentials_path')
    
    if not calendar_id or not credentials_path:
        return ("📅 Calendar not set up yet!\n\n"
                "To enable calendar, contact support to connect your Google Calendar.")
    
    # Check if credentials file exists
    import os
    if not os.path.exists(credentials_path):
        return "❌ Calendar credentials not found. Contact support."
    
    # Parse argument
    arg = arg.strip().lower() if arg else ""
    
    if arg == "today":
        return calendar_client.get_today_digest(credentials_path, calendar_id)
    else:
        # Default to 7 days, or parse number
        days = 7
        if arg:
            try:
                days = min(int(arg), 30)
            except ValueError:
                pass
        return calendar_client.get_calendar_digest(credentials_path, calendar_id, days=days)


def cmd_clear(user_id: int) -> str:
    """Clear conversation history"""
    count = db.clear_conversation_history(user_id)
    return f"Cleared {count} messages from memory."


def cmd_help(assistant_name: str) -> str:
    """Show help"""
    # Get combined help from skills
    skills_help = get_combined_help_text()
    
    base_help = f"""**{assistant_name} Commands:**

**Tasks:**
- `/add <task>` - Add a task
- `/today` - Show today's tasks
- `/tasks` - Show all pending tasks
- `/done <number>` - Mark task as done

**Reminders:**
- `/remind <time> <message>` - Set a reminder
- `/reminders` - Show pending reminders

**Setup:**
- `/setup google` - Configure Google integrations (Calendar, Gmail, Sheets)

**Other:**
- `/context` - Show your stored context
- `/setcontext <key> <value>` - Update context
- `/clear` - Clear conversation history
- `/help` - Show this help

Or just chat naturally - I understand things like "add buy milk to my list" or "remind me to call John at 3pm".

---

{skills_help}"""
    
    return base_help


def cmd_context(user_id: int) -> str:
    """Show user's stored context"""
    context = db.get_all_context(user_id)
    
    if not context:
        return "No context stored yet. Use `/setcontext <key> <value>` to add some."
    
    lines = ["**Your Context:**", ""]
    for key, value in context.items():
        lines.append(f"- **{key.replace('_', ' ').title()}:** {value}")
    
    return "\n".join(lines)


def cmd_set_context(user_id: int, arg: str) -> str:
    """Set a context value"""
    if not arg:
        return "Example: `/setcontext goals Build my business and stay healthy`"
    
    parts = arg.split(maxsplit=1)
    if len(parts) < 2:
        return "Please provide both key and value. Example: `/setcontext goals My goals here`"
    
    key = parts[0].lower().replace(' ', '_')
    value = parts[1]
    
    db.set_context(user_id, key, value)
    return f"Updated {key.replace('_', ' ')}: {value}"


def handle_natural_language(user_id: int, text: str, user: dict) -> str:
    """
    Handle natural language messages using LLM.
    Detects intent and either performs actions or has a conversation.
    """
    # Store user message in history
    db.add_message(user_id, "user", text)
    
    # Get context and history
    context = db.get_all_context(user_id)
    history = db.get_conversation_history(user_id, limit=20)
    
    # Build messages for LLM
    messages = [{"role": m['role'], "content": m['content']} for m in history]
    
    # Build system prompt
    system_prompt = llm.build_system_prompt(
        user_name=user.get('user_name', 'there'),
        assistant_name=user.get('assistant_name', 'Archie'),
        context=context
    )
    
    # Check if user wants to add a task
    if _looks_like_task_add(text):
        task_text = _extract_task(text)
        if task_text:
            db.add_task(user_id, task_text)
            response = f"Added to your tasks: {task_text}"
            db.add_message(user_id, "assistant", response)
            return response
    
    # Check if user wants a reminder
    if _looks_like_reminder(text):
        remind_at, message = reminder_module.parse_reminder_command(text)
        if remind_at and message:
            reminder_module.create_reminder(user_id, message, remind_at)
            formatted_time = reminder_module.format_reminder_time(remind_at)
            response = f"I'll remind you {formatted_time}: {message}"
            db.add_message(user_id, "assistant", response)
            return response
    
    # Check if user wants to search
    if _looks_like_search(text):
        query = _extract_search_query(text)
        if query:
            results = research.search(query, num_results=3)
            if results:
                # Add search results to context for LLM
                search_context = "Here are some search results:\n"
                for r in results:
                    search_context += f"- {r['title']}: {r['snippet'][:200]}\n"
                messages.append({"role": "system", "content": search_context})
    
    # Get LLM response
    response = llm.chat(messages, system_prompt=system_prompt)
    
    # Process LLM actions (skills can act on the response)
    action_results = route_llm_actions(user_id, response)
    
    # Clean response of action tags
    cleaned_response = clean_llm_response(response)
    
    # Append action results if any
    if action_results:
        cleaned_response += "\n\n" + "\n".join(action_results)
    
    # Store assistant response
    db.add_message(user_id, "assistant", cleaned_response)
    
    # Truncate for Telegram (4096 char limit)
    if len(cleaned_response) > 4000:
        cleaned_response = cleaned_response[:3997] + "..."
    
    return cleaned_response


def _looks_like_task_add(text: str) -> bool:
    """Check if message looks like user wants to add a task"""
    patterns = [
        r'\badd\b.*\b(to|on)\s*(my\s*)?(list|tasks?|todo)',
        r'\bremember\s+to\b',
        r'\bdon\'?t\s+forget\s+to\b',
        r'\bneed\s+to\b.*\badd\b',
    ]
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in patterns)


def _extract_task(text: str) -> Optional[str]:
    """Extract task text from natural language"""
    patterns = [
        r'add\s+["\']?(.+?)["\']?\s+to\s+(?:my\s+)?(?:list|tasks?|todo)',
        r'remember\s+to\s+(.+)',
        r'don\'?t\s+forget\s+to\s+(.+)',
    ]
    text_lower = text.lower()
    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            return match.group(1).strip()
    return None


def _looks_like_reminder(text: str) -> bool:
    """Check if message looks like user wants a reminder"""
    patterns = [
        r'\bremind\s+me\b',
        r'\bset\s+a?\s*reminder\b',
        r'\balert\s+me\b',
    ]
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in patterns)


def _looks_like_search(text: str) -> bool:
    """Check if message looks like user wants to search"""
    patterns = [
        r'\bsearch\s+(?:for\s+)?',
        r'\blook\s+up\b',
        r'\bfind\s+(?:out\s+)?(?:about\s+)?',
        r'\bwhat\s+is\b',
        r'\bwho\s+is\b',
        r'\bhow\s+(?:do|does|to)\b',
    ]
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in patterns)


def _extract_search_query(text: str) -> Optional[str]:
    """Extract search query from natural language"""
    patterns = [
        r'search\s+(?:for\s+)?(.+)',
        r'look\s+up\s+(.+)',
        r'find\s+(?:out\s+)?(?:about\s+)?(.+)',
    ]
    text_lower = text.lower()
    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            return match.group(1).strip()
    return text  # Fall back to full text

"""
AnyArchie Command Handlers
Handles /commands and natural language processing
"""
import re
from datetime import datetime, date
from typing import Optional, Tuple
from . import db
from . import llm
from . import research
from . import reminders as reminder_module
from . import email_client


def handle_command(user_id: int, text: str, user: dict) -> str:
    """
    Handle a command or message from the user.
    
    Args:
        user_id: Database user ID
        text: The message text
        user: User dict from database
    
    Returns:
        Response message
    """
    text = text.strip()
    
    # Command routing
    if text.startswith('/'):
        cmd_parts = text.split(maxsplit=1)
        cmd = cmd_parts[0].lower()
        arg = cmd_parts[1] if len(cmd_parts) > 1 else ""
        
        if cmd == '/add':
            return cmd_add(user_id, arg)
        elif cmd == '/today':
            return cmd_today(user_id)
        elif cmd == '/done':
            return cmd_done(user_id, arg)
        elif cmd == '/tasks':
            return cmd_tasks(user_id)
        elif cmd == '/remind':
            return cmd_remind(user_id, arg)
        elif cmd == '/reminders':
            return cmd_list_reminders(user_id)
        elif cmd == '/search':
            return cmd_search(arg)
        elif cmd == '/emails':
            return cmd_emails(user, arg)
        elif cmd == '/clear':
            return cmd_clear(user_id)
        elif cmd == '/help':
            return cmd_help(user['assistant_name'])
        elif cmd == '/context':
            return cmd_context(user_id)
        elif cmd == '/setcontext':
            return cmd_set_context(user_id, arg)
        else:
            return f"Unknown command. Type /help to see available commands."
    
    # Natural language processing via LLM
    return handle_natural_language(user_id, text, user)


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
    
    # Parse hours argument (default 24, max 48)
    hours = 24
    if arg:
        try:
            hours = min(int(arg.strip()), 48)
        except ValueError:
            pass
    
    imap_server = user.get('email_imap_server', 'imap.gmail.com')
    
    return email_client.get_email_digest(
        email_address=email_address,
        app_password=app_password,
        hours=hours,
        imap_server=imap_server
    )


def cmd_clear(user_id: int) -> str:
    """Clear conversation history"""
    count = db.clear_conversation_history(user_id)
    return f"Cleared {count} messages from memory."


def cmd_help(assistant_name: str) -> str:
    """Show help"""
    return f"""**{assistant_name} Commands:**

**Tasks:**
- `/add <task>` - Add a task
- `/today` - Show today's tasks
- `/tasks` - Show all pending tasks
- `/done <number>` - Mark task as done

**Reminders:**
- `/remind <time> <message>` - Set a reminder
- `/reminders` - Show pending reminders

**Email:**
- `/emails` - Email digest (last 24 hours)
- `/emails 48` - Email digest (last 48 hours)

**Other:**
- `/search <query>` - Search the web
- `/context` - Show your stored context
- `/setcontext <key> <value>` - Update context
- `/clear` - Clear conversation history
- `/help` - Show this help

Or just chat naturally - I understand things like "add buy milk to my list" or "remind me to call John at 3pm"."""


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
    
    # Store assistant response
    db.add_message(user_id, "assistant", response)
    
    # Truncate for Telegram (4096 char limit)
    if len(response) > 4000:
        response = response[:3997] + "..."
    
    return response


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

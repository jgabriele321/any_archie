"""
AnyArchie Onboarding Flow
Handles new user setup via conversation
"""
from typing import Optional, Tuple
from . import db

# Onboarding states
STATES = {
    "new": "Just started",
    "asked_name": "Asked for user's name",
    "asked_assistant_name": "Asked what to call the assistant",
    "asked_goals": "Asked about goals",
    "asked_focus": "Asked about current focus",
    "complete": "Onboarding complete"
}


def get_onboarding_message(state: str, user_input: Optional[str] = None) -> Tuple[str, str]:
    """
    Get the next onboarding message based on current state.
    
    Args:
        state: Current onboarding state
        user_input: User's response to previous question
    
    Returns:
        Tuple of (message_to_send, next_state)
    """
    if state == "new":
        return (
            "Hey there! I'm your new personal assistant. "
            "Let's get you set up - it'll only take a minute.\n\n"
            "First, what's your name?",
            "asked_name"
        )
    
    elif state == "asked_name":
        return (
            f"Nice to meet you, {user_input}! "
            "What would you like to call me? (I default to 'Archie', but you can pick any name)",
            "asked_assistant_name"
        )
    
    elif state == "asked_assistant_name":
        name = user_input if user_input and user_input.lower() != "archie" else "Archie"
        return (
            f"Love it - I'm {name} now! "
            "What are your main goals right now? "
            "(Just a sentence or two - I'll remember this to help you stay focused)",
            "asked_goals"
        )
    
    elif state == "asked_goals":
        return (
            "Got it! Last question: what's your current focus or priority? "
            "(What should I help you concentrate on?)",
            "asked_focus"
        )
    
    elif state == "asked_focus":
        return (
            "Perfect! You're all set up. Here's what I can help you with:\n\n"
            "**Tasks:**\n"
            "- `/add Buy groceries` - Add a task\n"
            "- `/today` - See today's tasks\n"
            "- `/done 1` - Complete task #1\n\n"
            "**Reminders:**\n"
            "- `/remind 3pm Call mom` - Set a reminder\n\n"
            "**Other:**\n"
            "- `/search latest news on X` - Search the web\n"
            "- `/help` - See all commands\n\n"
            "Or just chat naturally - I understand things like "
            "\"remind me to call the dentist tomorrow at 2pm\" or "
            "\"add pick up dry cleaning to my list\".\n\n"
            "What can I help you with?",
            "complete"
        )
    
    return ("I'm ready to help! Type /help to see what I can do.", "complete")


def process_onboarding_step(user_id: int, state: str, user_input: str) -> Tuple[str, bool]:
    """
    Process a step in the onboarding flow.
    
    Args:
        user_id: Database user ID
        state: Current onboarding state
        user_input: User's message
    
    Returns:
        Tuple of (response_message, is_complete)
    """
    # Store the user's response based on current state
    if state == "asked_name":
        db.update_user(user_id, user_name=user_input.strip())
    
    elif state == "asked_assistant_name":
        name = user_input.strip() if user_input.strip() else "Archie"
        db.update_user(user_id, assistant_name=name)
    
    elif state == "asked_goals":
        db.set_context(user_id, "goals", user_input.strip())
    
    elif state == "asked_focus":
        db.set_context(user_id, "current_focus", user_input.strip())
    
    # Get next message and state
    message, next_state = get_onboarding_message(state, user_input)
    
    # Update user's onboarding state
    db.update_user(user_id, onboarding_state=next_state)
    
    is_complete = next_state == "complete"
    return message, is_complete

"""
AnyArchie Onboarding Flow
Handles new user setup via conversation with extensive tutorial
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
    "tutorial_intro": "Tutorial introduction",
    "tutorial_tasks": "Tutorial: tasks",
    "tutorial_reminders": "Tutorial: reminders",
    "tutorial_search": "Tutorial: search",
    "tutorial_contacts": "Tutorial: contacts",
    "tutorial_memory": "Tutorial: memory",
    "setup_google_prompt": "Prompting about Google setup",
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
            "Perfect! Now let's take a quick tour of what I can do. "
            "I'll show you the main features one by one - it'll only take a few minutes!\n\n"
            "Ready to start? (Just say 'yes' or 'skip' to jump ahead)",
            "tutorial_intro"
        )
    
    elif state == "tutorial_intro":
        # Check if user said yes or similar
        if user_input and (user_input.lower() in ['yes', 'y', 'ok', 'okay', 'sure', 'ready', 'let\'s go', 'go'] or 
                          'yes' in user_input.lower() or 'ready' in user_input.lower() or 'start' in user_input.lower()):
            return (
                "Great! Let's start with **Tasks** - your to-do list.\n\n"
                "**Try it now:** Send me `/add Test task` to add your first task!\n\n"
                "(I'll wait for you to try it, or say 'skip' to move on)",
                "tutorial_tasks"
            )
        elif user_input and user_input.lower() in ['skip', 'no', 'n']:
            return (
                "**You're all set!** 🎉\n\n"
                "**Quick reference:**\n"
                "- `/help` - See all commands\n"
                "- `/today` - Your tasks for today\n"
                "- `/setup google` - Configure Google integrations\n\n"
                "Or just chat naturally - I understand things like \"remind me to call John tomorrow\" or \"add buy groceries to my list\".\n\n"
                "What can I help you with?",
                "complete"
            )
        else:
            # User said something else, interpret as yes and continue
            return (
                "Great! Let's start with **Tasks** - your to-do list.\n\n"
                "**Try it now:** Send me `/add Test task` to add your first task!\n\n"
                "(I'll wait for you to try it, or say 'skip' to move on)",
                "tutorial_tasks"
            )
    
    elif state == "tutorial_tasks":
        # Check if user added a task
        if user_input and user_input.lower().startswith('/add'):
            return (
                "✅ Perfect! You added a task!\n\n"
                "**More task commands:**\n"
                "- `/today` - See today's tasks\n"
                "- `/tasks` - See all pending tasks\n"
                "- `/done 1` - Mark task #1 as complete\n\n"
                "You can also just say things like \"add buy milk to my list\" and I'll understand!\n\n"
                "Ready for the next feature? (say 'next' or 'skip')",
                "tutorial_reminders"
            )
        elif user_input and user_input.lower() in ['skip', 'next', 'done', 'finished']:
            return (
                "**Reminders** - I can remind you about anything!\n\n"
                "**Try it:** Send me `/remind 5 minutes Test reminder`\n\n"
                "(I'll wait, or say 'skip')",
                "tutorial_reminders"
            )
        elif user_input and len(user_input.strip()) > 0:
            # User sent something that's not /add, skip, or next
            # Don't loop - just move forward after acknowledging
            return (
                "Got it! Let's move on to the next feature.\n\n"
                "**Reminders** - I can remind you about anything!\n\n"
                "**Try it:** Send me `/remind 5 minutes Test reminder`\n\n"
                "(or say 'skip' to continue)",
                "tutorial_reminders"
            )
        else:
            # Empty input - stay in same state but don't spam
            return (
                "Try sending `/add Test task` to add a task, or say 'skip' to move on.",
                "tutorial_tasks"
            )
    
    elif state == "tutorial_reminders":
        if user_input and user_input.lower().startswith('/remind'):
            return (
                "✅ Great! I'll remind you!\n\n"
                "**Reminder formats:**\n"
                "- `/remind 3pm Call mom`\n"
                "- `/remind tomorrow at 9am Check emails`\n"
                "- `/remind in 30 minutes Take a break`\n\n"
                "Ready for the next feature? (say 'next' or 'skip')",
                "tutorial_search"
            )
        elif user_input and user_input.lower() in ['skip', 'next']:
            return (
                "**Web Search** - I can search the internet for you!\n\n"
                "**Try it:** Send me `/search latest AI news`\n\n"
                "(or say 'skip')",
                "tutorial_search"
            )
        else:
            return (
                "Try sending `/remind 5 minutes Test reminder`, or say 'skip' to move on.",
                "tutorial_reminders"
            )
    
    elif state == "tutorial_search":
        if user_input and user_input.lower().startswith('/search'):
            return (
                "✅ Awesome! I can search the web for anything.\n\n"
                "Ready for the next feature? (say 'next' or 'skip')",
                "tutorial_contacts"
            )
        elif user_input and user_input.lower() in ['skip', 'next']:
            return (
                "**Contacts** - Keep track of people you meet!\n\n"
                "**Try it:** Send me `/addcontact John Smith`\n\n"
                "📸 **Pro tip:** Send me a photo of a business card and I'll extract the contact info automatically!\n\n"
                "(or say 'skip')",
                "tutorial_contacts"
            )
        else:
            return (
                "Try sending `/search latest AI news`, or say 'skip' to move on.",
                "tutorial_search"
            )
    
    elif state == "tutorial_contacts":
        if user_input and user_input.lower().startswith('/addcontact'):
            return (
                "✅ Contact added!\n\n"
                "**More contact commands:**\n"
                "- `/findcontact John` - Search contacts\n"
                "- `/contacts` - List all contacts\n"
                "- `/editcontact 1 email john@example.com` - Add details\n\n"
                "Ready for the next feature? (say 'next' or 'skip')",
                "tutorial_memory"
            )
        elif user_input and user_input.lower() in ['skip', 'next']:
            return (
                "**Memory** - I remember important things about you!\n\n"
                "**Try it:** Send me `/remember I prefer morning workouts`\n\n"
                "I'll automatically remember preferences, goals, and important info you share!\n\n"
                "(or say 'skip')",
                "tutorial_memory"
            )
        else:
            return (
                "Try sending `/addcontact John Smith`, or say 'skip' to move on.",
                "tutorial_contacts"
            )
    
    elif state == "tutorial_memory":
        if user_input and user_input.lower().startswith('/remember'):
            return (
                "✅ I'll remember that!\n\n"
                "**Memory commands:**\n"
                "- `/facts` - See what I remember\n"
                "- `/searchfacts workout` - Search memories\n\n"
                "Ready to finish? (say 'next' or 'skip')",
                "setup_google_prompt"
            )
        elif user_input and user_input.lower() in ['skip', 'next']:
            return (
                "**Google Integrations** - Connect your Calendar, Gmail, and Sheets!\n\n"
                "Would you like to set up Google integrations now?\n\n"
                "Say 'yes' to start setup, or 'skip' to finish the tutorial.",
                "setup_google_prompt"
            )
        else:
            return (
                "Try sending `/remember I prefer morning workouts`, or say 'skip' to move on.",
                "tutorial_memory"
            )
    
    elif state == "setup_google_prompt":
        if user_input and user_input.lower() in ['yes', 'y', 'setup']:
            return (
                "Great! Use `/setup google` anytime to configure Google Calendar, Gmail, or Sheets.\n\n"
                "**You're all set!** 🎉\n\n"
                "Here's a quick reference:\n"
                "- `/help` - See all commands\n"
                "- `/today` - Your tasks for today\n"
                "- `/setup google` - Configure Google integrations\n\n"
                "Or just chat naturally - I understand things like \"remind me to call John tomorrow\" or \"add buy groceries to my list\".\n\n"
                "What can I help you with?",
                "complete"
            )
        else:
            return (
                "**You're all set!** 🎉\n\n"
                "**Quick reference:**\n"
                "- `/help` - See all commands\n"
                "- `/today` - Your tasks for today\n"
                "- `/setup google` - Configure Google integrations (Calendar, Gmail, Sheets)\n\n"
                "Or just chat naturally - I understand things like \"remind me to call John tomorrow\" or \"add buy groceries to my list\".\n\n"
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
    
    # Special handling for tutorial states - check if user completed the action
    if state == "tutorial_tasks" and user_input and user_input.lower().startswith('/add'):
        # User added a task - move to next step
        pass  # Already handled in get_onboarding_message
    elif state == "tutorial_reminders" and user_input and user_input.lower().startswith('/remind'):
        # User set a reminder - move to next step
        pass
    elif state == "tutorial_search" and user_input and user_input.lower().startswith('/search'):
        # User searched - move to next step
        pass
    elif state == "tutorial_contacts" and user_input and user_input.lower().startswith('/addcontact'):
        # User added contact - move to next step
        pass
    elif state == "tutorial_memory" and user_input and user_input.lower().startswith('/remember'):
        # User remembered something - move to next step
        pass
    
    # Update user's onboarding state
    db.update_user(user_id, onboarding_state=next_state)
    
    is_complete = next_state == "complete"
    return message, is_complete

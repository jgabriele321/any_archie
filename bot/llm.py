"""
AnyArchie LLM Integration
Uses OpenRouter for Claude access
"""
import httpx
from typing import List, Dict, Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, DEFAULT_MODEL, MAX_TOKENS


def chat(
    messages: List[Dict[str, str]],
    system_prompt: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = MAX_TOKENS
) -> str:
    """
    Send messages to LLM and get response.
    
    Args:
        messages: List of {"role": "user"|"assistant", "content": "..."}
        system_prompt: Optional system prompt
        model: Model to use
        max_tokens: Max response tokens
    
    Returns:
        Assistant's response text
    """
    if not OPENROUTER_API_KEY:
        return "Error: OpenRouter API key not configured."
    
    # Build messages list
    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)
    
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://anyarchie.app",
                    "X-Title": "AnyArchie"
                },
                json={
                    "model": model,
                    "messages": full_messages,
                    "max_tokens": max_tokens
                }
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    except httpx.TimeoutException:
        return "Sorry, the request timed out. Please try again."
    except httpx.HTTPStatusError as e:
        return f"Error communicating with AI: {e.response.status_code}"
    except Exception as e:
        return f"Error: {str(e)}"


def build_system_prompt(user_name: str, assistant_name: str, context: Dict[str, str]) -> str:
    """
    Build a personalized system prompt for the user.
    
    Args:
        user_name: The user's name
        assistant_name: What they named their assistant
        context: Dict of context key-values (goals, focus, etc.)
    """
    prompt = f"""You are {assistant_name}, a personal assistant for {user_name}.

Your personality:
- Friendly but efficient
- You remember context about {user_name}'s life and priorities
- You help with task management, reminders, and general questions
- You can search the web when asked about current events or facts you're unsure of
- Keep responses concise unless asked to elaborate

"""
    
    # Add context
    if context:
        prompt += f"About {user_name}:\n"
        for key, value in context.items():
            if value:
                prompt += f"- {key.replace('_', ' ').title()}: {value}\n"
        prompt += "\n"
    
    prompt += """Commands the user can use:
- /add <task> - Add a task
- /today - Show today's tasks
- /done <number> - Mark a task as done
- /remind <time> <message> - Set a reminder
- /search <query> - Search the web
- /clear - Clear conversation history
- /help - Show help

But the user can also just chat naturally - you understand intent and can add tasks, set reminders, etc. from natural language."""
    
    return prompt

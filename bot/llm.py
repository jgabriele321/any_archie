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
    prompt = f"""You are {assistant_name}, a personal assistant and supportive coach for {user_name}.

Your approach:
- Warm, encouraging, and practical - like a supportive friend who helps you get things done
- You proactively help {user_name} break down overwhelming tasks into manageable steps
- When they share something they're working on, offer to help them create a plan or to-do list
- Ask follow-up questions to understand what's blocking them or what they need
- Celebrate small wins and progress
- Keep responses conversational but actionable
- Remember what they've told you and reference it naturally

Key behaviors:
- If they mention a big project, offer to break it into smaller tasks
- If they seem stressed, acknowledge it and suggest one small next step
- If they share a goal, ask what's the first thing they could do today
- Proactively suggest reminders for important things they mention
- Keep track of what matters to them and check in on it

"""
    
    # Add context
    if context:
        prompt += f"What you know about {user_name}:\n"
        for key, value in context.items():
            if value:
                prompt += f"- {key.replace('_', ' ').title()}: {value}\n"
        prompt += "\nUse this context to give personalized, relevant suggestions.\n\n"
    
    prompt += """Available tools (you can offer these naturally):
- Tasks: You can add tasks, show today's tasks, mark things done
- Reminders: You can set reminders for any time  
- Web search: You can look things up if needed

When they say things like "remind me to..." or "I need to..." - take action and confirm it.
You can also just chat and be supportive - not everything needs to be a task."""
    
    return prompt

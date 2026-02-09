"""
Skill loader and registry for AnyArchie.

This module handles:
- Loading skills configuration
- Importing and instantiating enabled skills
- Routing commands and LLM actions to the appropriate skill
"""
import importlib
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type

from .base import BaseSkill, CommandInfo, LLMActionInfo

# Registry of available skills (name -> class)
_SKILL_REGISTRY: Dict[str, Type[BaseSkill]] = {}

# Loaded skill instances
_loaded_skills: Dict[str, BaseSkill] = {}


def register_skill(skill_class: Type[BaseSkill]) -> Type[BaseSkill]:
    """
    Decorator to register a skill class.
    
    Usage:
        @register_skill
        class ContactsSkill(BaseSkill):
            ...
    """
    # Create a temporary instance to get the name
    temp = skill_class.__new__(skill_class)
    temp.config = {}
    name = temp.name
    _SKILL_REGISTRY[name] = skill_class
    return skill_class


def load_skills() -> Dict[str, BaseSkill]:
    """
    Load and instantiate all enabled skills.
    
    Returns:
        Dictionary of skill name -> skill instance
    """
    global _loaded_skills
    
    if _loaded_skills:
        return _loaded_skills
    
    # Import skill modules to trigger registration
    # Add new skills here as they're created
    skill_modules = [
        "contacts",
        "memory",
        "calendar",
        "email",
        "research",
    ]
    
    for module_name in skill_modules:
        try:
            importlib.import_module(f".{module_name}", package=__name__)
        except ImportError as e:
            print(f"Warning: Could not import {module_name} skill: {e}")
    
    # Instantiate all registered skills (for now, all enabled by default)
    for skill_name, skill_class in _SKILL_REGISTRY.items():
        try:
            _loaded_skills[skill_name] = skill_class(config={})
        except Exception as e:
            print(f"Warning: Could not load skill '{skill_name}': {e}")
    
    return _loaded_skills


def get_skill(name: str) -> Optional[BaseSkill]:
    """Get a loaded skill by name."""
    skills = load_skills()
    return skills.get(name)


def get_all_skills() -> List[BaseSkill]:
    """Get all loaded skills."""
    return list(load_skills().values())


def get_all_commands() -> List[CommandInfo]:
    """Get all commands from all loaded skills."""
    commands = []
    for skill in get_all_skills():
        commands.extend(skill.commands)
    return commands


def get_all_llm_actions() -> List[LLMActionInfo]:
    """Get all LLM actions from all loaded skills."""
    actions = []
    for skill in get_all_skills():
        actions.extend(skill.llm_actions)
    return actions


def route_command(
    user_id: int,
    command: str,
    args: str,
    send_message: Callable[[int, str], None],
    send_document: Callable[[int, Any, str], None] = None,
    send_photo: Callable[[int, bytes, str], None] = None,
) -> bool:
    """
    Route a command to the appropriate skill.
    
    Args:
        user_id: Database user ID
        command: The command (e.g., "/addcontact")
        args: Arguments after the command
        send_message: Function to send a message (takes telegram_id, message)
        send_document: Function to send a document
        send_photo: Function to send a photo
        
    Returns:
        True if a skill handled the command, False otherwise
    """
    all_skills = get_all_skills()
    for skill in all_skills:
        if skill.handles_command(command):
            return skill.handle_command(
                user_id=user_id,
                command=command,
                args=args,
                send_message=send_message,
                send_photo=send_photo,
                send_document=send_document,
            )
    return False


def route_llm_actions(user_id: int, response: str) -> List[str]:
    """
    Route LLM actions in a response to appropriate skills.
    
    Args:
        user_id: Database user ID
        response: The full LLM response
        
    Returns:
        List of result strings from handled actions
    """
    results = []
    for skill in get_all_skills():
        for action in skill.llm_actions:
            result = skill.handle_llm_action(user_id, action.name, response)
            if result:
                results.append(result)
    return results


def clean_llm_response(response: str) -> str:
    """
    Remove all skill action tags from an LLM response.
    
    Args:
        response: The LLM response text
        
    Returns:
        Response with all action tags removed
    """
    cleaned = response
    for skill in get_all_skills():
        cleaned = skill.clean_llm_response(cleaned)
    return cleaned


def get_combined_help_text() -> str:
    """
    Get combined help text from all loaded skills.
    
    Returns:
        Formatted help text for all skills
    """
    sections = []
    for skill in get_all_skills():
        help_text = skill.get_help_text()
        if help_text:
            sections.append(help_text)
    return "\n".join(sections)


def get_combined_llm_prompt() -> str:
    """
    Get combined LLM prompt sections from all loaded skills.
    
    Returns:
        Combined prompt text for system prompt
    """
    sections = []
    for skill in get_all_skills():
        prompt = skill.get_llm_prompt_section()
        if prompt:
            sections.append(prompt)
    return "\n\n".join(sections)


# Export public API
__all__ = [
    "BaseSkill",
    "CommandInfo",
    "LLMActionInfo",
    "register_skill",
    "load_skills",
    "get_skill",
    "get_all_skills",
    "get_all_commands",
    "get_all_llm_actions",
    "route_command",
    "route_llm_actions",
    "clean_llm_response",
    "get_combined_help_text",
    "get_combined_llm_prompt",
]
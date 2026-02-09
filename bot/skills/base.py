"""
Base class for all AnyArchie skills.

Skills are modular components that handle specific functionality
(contacts, memory, calendar, etc.) and can be enabled/disabled via config.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass
class CommandInfo:
    """Information about a command."""
    name: str  # e.g., "/addcontact"
    description: str  # e.g., "Add a new contact"
    usage: str = ""  # e.g., "/addcontact <name>"


@dataclass
class LLMActionInfo:
    """Information about an LLM action."""
    name: str  # e.g., "LIST_CONTACTS"
    description: str  # e.g., "List all contacts"
    pattern: str  # Regex pattern to match


class BaseSkill(ABC):
    """
    Abstract base class for all skills.
    
    Each skill must implement:
    - name: Unique identifier for the skill
    - commands: List of Telegram commands this skill handles
    - llm_actions: List of LLM actions this skill handles
    - handle_command(): Process a Telegram command
    - handle_llm_action(): Process an LLM action from Claude
    - get_help_text(): Return help text for /help command
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the skill with optional config.
        
        Args:
            config: Skill-specific configuration
        """
        self.config = config or {}
        self._setup()
    
    def _setup(self) -> None:
        """
        Optional setup hook called after __init__.
        Override in subclasses for initialization logic.
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this skill (e.g., 'contacts')."""
        pass
    
    @property
    @abstractmethod
    def commands(self) -> List[CommandInfo]:
        """List of commands this skill handles."""
        pass
    
    @property
    @abstractmethod
    def llm_actions(self) -> List[LLMActionInfo]:
        """List of LLM actions this skill handles."""
        pass
    
    @abstractmethod
    def handle_command(
        self,
        user_id: int,  # Database user ID (not Telegram chat_id)
        command: str,
        args: str,
        send_message: Callable[[int, str], None],  # Takes telegram_id, message
        send_document: Callable[[int, Any, str], None] = None,
        send_photo: Callable[[int, bytes, str], None] = None,
    ) -> bool:
        """
        Handle a Telegram command.
        
        Args:
            user_id: Database user ID
            command: The command (e.g., "/addcontact")
            args: Arguments after the command
            send_message: Function to send a message (takes telegram_id, message)
            send_document: Function to send a document (optional)
            send_photo: Function to send a photo (optional)
            
        Returns:
            True if the command was handled, False otherwise
        """
        pass
    
    @abstractmethod
    def handle_llm_action(
        self,
        user_id: int,
        action: str,
        response: str,
    ) -> Optional[str]:
        """
        Handle an LLM action from Claude's response.
        
        Args:
            user_id: Database user ID
            action: The action name (e.g., "LIST_CONTACTS")
            response: The full LLM response containing the action
            
        Returns:
            Result string if action was handled, None otherwise
        """
        pass
    
    @abstractmethod
    def get_help_text(self) -> str:
        """
        Return help text for this skill's commands.
        
        Returns:
            Formatted help text for /help command
        """
        pass
    
    @abstractmethod
    def get_llm_prompt_section(self) -> str:
        """
        Return the LLM prompt section describing this skill's actions.
        
        Returns:
            Text to include in the system prompt for Claude
        """
        pass
    
    def get_command_names(self) -> List[str]:
        """Get list of command names (e.g., ['/addcontact', '/findcontact'])."""
        return [cmd.name for cmd in self.commands]
    
    def get_llm_action_names(self) -> List[str]:
        """Get list of LLM action names."""
        return [action.name for action in self.llm_actions]
    
    def handles_command(self, command: str) -> bool:
        """Check if this skill handles the given command."""
        cmd_lower = command.lower()
        return any(cmd.name.lower() == cmd_lower or cmd_lower.startswith(cmd.name.lower()) 
                   for cmd in self.commands)
    
    def clean_llm_response(self, response: str) -> str:
        """
        Remove this skill's action tags from an LLM response.
        
        Args:
            response: The LLM response text
            
        Returns:
            Response with action tags removed
        """
        import re
        cleaned = response
        for action in self.llm_actions:
            cleaned = re.sub(action.pattern, '', cleaned, flags=re.IGNORECASE).strip()
        return cleaned
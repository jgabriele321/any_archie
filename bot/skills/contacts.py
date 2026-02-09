"""
Contacts skill for AnyArchie.

Handles contact management including:
- Adding, editing, finding, deleting contacts
- Business card scanning via photo
- Natural language contact queries via LLM actions
"""
import base64
import json
import re
from typing import Any, Callable, Dict, List, Optional

from .base import BaseSkill, CommandInfo, LLMActionInfo
from . import register_skill
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import db
from bot import llm


def format_contact(contact: Dict, verbose: bool = False) -> str:
    """Format a contact for display"""
    lines = [f"**{contact['name']}**"]
    
    if contact.get('company'):
        lines.append(f"Company: {contact['company']}")
    if contact.get('title'):
        lines.append(f"Title: {contact['title']}")
    if contact.get('email'):
        lines.append(f"Email: {contact['email']}")
    if contact.get('phone'):
        lines.append(f"Phone: {contact['phone']}")
    if contact.get('telegram'):
        lines.append(f"Telegram: @{contact['telegram']}")
    if contact.get('twitter'):
        lines.append(f"Twitter: @{contact['twitter']}")
    if contact.get('linkedin'):
        lines.append(f"LinkedIn: {contact['linkedin']}")
    if contact.get('website'):
        lines.append(f"Website: {contact['website']}")
    if contact.get('met_at'):
        lines.append(f"Met at: {contact['met_at']}")
    if verbose and contact.get('notes'):
        lines.append(f"Notes: {contact['notes']}")
    if contact.get('tags'):
        lines.append(f"Tags: {contact['tags']}")
    
    return "\n".join(lines)


@register_skill
class ContactsSkill(BaseSkill):
    """Skill for managing contacts."""
    
    @property
    def name(self) -> str:
        return "contacts"
    
    @property
    def commands(self) -> List[CommandInfo]:
        return [
            CommandInfo("/addcontact", "Add a new contact", "/addcontact <name>"),
            CommandInfo("/editcontact", "Edit a contact field", "/editcontact <id> <field> <value>"),
            CommandInfo("/findcontact", "Search contacts", "/findcontact <query>"),
            CommandInfo("/deletecontact", "Delete a contact", "/deletecontact <id>"),
            CommandInfo("/contacts", "List all contacts", "/contacts [event]"),
        ]
    
    @property
    def llm_actions(self) -> List[LLMActionInfo]:
        return [
            LLMActionInfo("LIST_CONTACTS", "List all contacts", r'\[LIST_CONTACTS\]'),
            LLMActionInfo("FIND_CONTACT", "Search for a contact", r'\[FIND_CONTACT:\s*["\']?(.+?)["\']?\]'),
            LLMActionInfo("SHOW_CONTACT", "Show contact details", r'\[SHOW_CONTACT:\s*(\d+)\]'),
            LLMActionInfo("ADD_CONTACT", "Add a new contact", r'\[ADD_CONTACT:\s*["\']?(.+?)["\']?\]'),
            LLMActionInfo("UPDATE_CONTACT", "Update a contact field", r'\[UPDATE_CONTACT:\s*(\d+),\s*(\w+),\s*["\']?(.+?)["\']?\]'),
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
        """Handle contact-related commands."""
        cmd_lower = command.lower()
        
        if cmd_lower.startswith("/addcontact"):
            self._handle_add_contact(user_id, args, send_message)
            return True
        
        elif cmd_lower.startswith("/editcontact"):
            self._handle_edit_contact(user_id, args, send_message)
            return True
        
        elif cmd_lower.startswith("/findcontact"):
            self._handle_find_contact(user_id, args, send_message)
            return True
        
        elif cmd_lower.startswith("/deletecontact"):
            self._handle_delete_contact(user_id, args, send_message)
            return True
        
        elif cmd_lower.startswith("/contacts"):
            self._handle_list_contacts(user_id, args, send_message)
            return True
        
        return False
    
    def handle_photo(self, user_id: int, photo_bytes: bytes, send_message: Callable[[int, str], None]) -> bool:
        """Handle photo upload - scan for business card"""
        try:
            # Convert photo to base64
            image_base64 = base64.b64encode(photo_bytes).decode('utf-8')
            
            # Use vision model to extract contact info
            prompt = """Extract contact information from this business card or photo. 
Return ONLY a JSON object with these fields (use null for missing fields):
{
  "name": "Full name",
  "email": "email@example.com",
  "phone": "phone number",
  "company": "Company name",
  "title": "Job title",
  "website": "website URL",
  "linkedin": "LinkedIn URL or username",
  "twitter": "Twitter handle",
  "telegram": "Telegram username"
}

Extract all visible information. Return ONLY the JSON, no other text."""
            
            response = llm.chat_with_vision(prompt, image_base64)
            
            # Try to extract JSON from response
            json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
            if json_match:
                contact_data = json.loads(json_match.group(0))
                
                # Get user's telegram_id for sending message
                user = db.get_user_by_id(user_id)
                if not user:
                    return False
                telegram_id = user['telegram_id']
                
                # Create contact
                contact = db.add_contact(
                    user_id=user_id,
                    name=contact_data.get('name', 'Unknown'),
                    email=contact_data.get('email', ''),
                    phone=contact_data.get('phone', ''),
                    company=contact_data.get('company', ''),
                    title=contact_data.get('title', ''),
                    website=contact_data.get('website', ''),
                    linkedin=contact_data.get('linkedin', ''),
                    twitter=contact_data.get('twitter', ''),
                    telegram=contact_data.get('telegram', ''),
                )
                
                send_message(
                    telegram_id,
                    f"✅ Contact added from business card!\n\n{format_contact(contact, verbose=True)}\n\n"
                    f"ID: `{contact['id']}`\n\n"
                    "Edit with: `/editcontact {contact['id']} <field> <value>`"
                )
                return True
            else:
                user = db.get_user_by_id(user_id)
                if user:
                    send_message(user['telegram_id'], "Couldn't extract contact info from the photo. Try adding manually with /addcontact")
                return False
        except Exception as e:
            user = db.get_user_by_id(user_id)
            if user:
                send_message(user['telegram_id'], f"Error scanning business card: {str(e)[:100]}")
            return False
    
    def _handle_add_contact(self, user_id: int, args: str, send_message: Callable) -> None:
        """Handle /addcontact command."""
        user = db.get_user_by_id(user_id)
        if not user:
            return
        
        telegram_id = user['telegram_id']
        
        if not args.strip():
            send_message(
                telegram_id,
                "Usage: /addcontact <name>\n\n"
                "Example: /addcontact John Smith\n\n"
                "After adding, use /editcontact to add more details like email, company, etc."
            )
            return
        
        name = args.strip()
        try:
            met_at = self.config.get("default_met_at", "")
            contact = db.add_contact(user_id=user_id, name=name, met_at=met_at) if met_at else db.add_contact(user_id=user_id, name=name)
            send_message(
                telegram_id,
                f"✅ Contact added!\n\n{format_contact(contact)}\n\n"
                f"ID: `{contact['id']}`\n\n"
                "Add details with:\n"
                f"`/editcontact {contact['id']} email john@example.com`\n"
                f"`/editcontact {contact['id']} company Acme Inc`\n"
                f"`/editcontact {contact['id']} met_at Conference 2026`"
            )
        except Exception as e:
            send_message(telegram_id, f"Error adding contact: {str(e)[:100]}")
    
    def _handle_edit_contact(self, user_id: int, args: str, send_message: Callable) -> None:
        """Handle /editcontact command."""
        user = db.get_user_by_id(user_id)
        if not user:
            return
        
        telegram_id = user['telegram_id']
        
        parts = args.split(" ", 2) if args else []
        if len(parts) < 3:
            send_message(
                telegram_id,
                "Usage: /editcontact <id> <field> <value>\n\n"
                "Fields: name, email, phone, company, title, twitter, telegram, linkedin, website, met_at, notes, tags\n\n"
                "Examples:\n"
                "• `/editcontact 1 email john@example.com`\n"
                "• `/editcontact 1 company Acme Inc`\n"
                "• `/editcontact 1 met_at Conference 2026`\n"
                "• `/editcontact 1 notes Great conversation about AI`"
            )
            return
        
        try:
            contact_id = int(parts[0])
            field = parts[1].lower()
            value = parts[2]
            
            valid_fields = {"name", "email", "phone", "company", "title", "twitter",
                          "telegram", "linkedin", "website", "met_at", "notes", "tags"}
            if field not in valid_fields:
                send_message(telegram_id, f"Invalid field. Use one of: {', '.join(valid_fields)}")
                return
            
            contact = db.update_contact(user_id, contact_id, **{field: value})
            if contact:
                send_message(telegram_id, f"✅ Updated!\n\n{format_contact(contact, verbose=True)}")
            else:
                send_message(telegram_id, f"Contact ID {contact_id} not found.")
        except ValueError:
            send_message(telegram_id, "Invalid contact ID. Use a number.")
        except Exception as e:
            send_message(telegram_id, f"Error: {str(e)[:100]}")
    
    def _handle_find_contact(self, user_id: int, args: str, send_message: Callable) -> None:
        """Handle /findcontact command."""
        user = db.get_user_by_id(user_id)
        if not user:
            return
        
        telegram_id = user['telegram_id']
        
        if not args.strip():
            send_message(telegram_id, "Usage: /findcontact <query>\n\nSearches name, company, email, notes, and tags.")
            return
        
        query = args.strip()
        try:
            contacts = db.find_contacts(user_id, query)
            if not contacts:
                send_message(telegram_id, f"No contacts found matching '{query}'.")
                return
            
            lines = [f"🔍 Found {len(contacts)} contact(s):\n"]
            for c in contacts[:10]:
                lines.append(format_contact(c))
                lines.append(f"   ID: `{c['id']}`\n")
            if len(contacts) > 10:
                lines.append(f"\n_...and {len(contacts) - 10} more_")
            send_message(telegram_id, "\n".join(lines))
        except Exception as e:
            send_message(telegram_id, f"Error searching: {str(e)[:100]}")
    
    def _handle_delete_contact(self, user_id: int, args: str, send_message: Callable) -> None:
        """Handle /deletecontact command."""
        user = db.get_user_by_id(user_id)
        if not user:
            return
        
        telegram_id = user['telegram_id']
        
        if not args.strip():
            send_message(telegram_id, "Usage: /deletecontact <id>")
            return
        
        try:
            contact_id = int(args.strip())
            contact = db.get_contact_by_id(user_id, contact_id)
            if contact and db.delete_contact(user_id, contact_id):
                send_message(telegram_id, f"✅ Deleted contact: {contact['name']}")
            else:
                send_message(telegram_id, f"Contact ID {contact_id} not found.")
        except ValueError:
            send_message(telegram_id, "Invalid contact ID. Use a number.")
    
    def _handle_list_contacts(self, user_id: int, args: str, send_message: Callable) -> None:
        """Handle /contacts command."""
        user = db.get_user_by_id(user_id)
        if not user:
            return
        
        telegram_id = user['telegram_id']
        
        event_filter = args.strip() if args else None
        
        try:
            contacts = db.list_contacts(user_id, limit=20, event=event_filter)
            total = db.get_contact_count(user_id)
            
            if not contacts:
                send_message(telegram_id, "No contacts yet. Add one with /addcontact <name>")
                return
            
            lines = [f"📇 **Contacts** ({len(contacts)} of {total})\n"]
            if event_filter:
                lines[0] = f"📇 **Contacts from '{event_filter}'** ({len(contacts)})\n"
            
            for c in contacts:
                lines.append(format_contact(c))
                lines.append(f"   ID: `{c['id']}`\n")
            
            lines.append("\nCommands: /findcontact, /addcontact, /editcontact")
            send_message(telegram_id, "\n".join(lines))
        except Exception as e:
            send_message(telegram_id, f"Error listing contacts: {str(e)[:100]}")
    
    def handle_llm_action(self, user_id: int, action: str, response: str) -> Optional[str]:
        """Handle LLM actions for contacts."""
        results = []
        
        # [LIST_CONTACTS]
        if re.search(r'\[LIST_CONTACTS\]', response, re.IGNORECASE):
            try:
                contacts = db.list_contacts(user_id, limit=100)
                if contacts:
                    names = [f"• {c['name']}" + (f" ({c['company']})" if c.get('company') else "") for c in contacts]
                    results.append(f"📇 {len(contacts)} contacts:\n" + "\n".join(names))
                else:
                    results.append("No contacts in database yet.")
            except Exception as e:
                results.append(f"Error listing contacts: {str(e)[:50]}")
        
        # [FIND_CONTACT: "query"]
        find_match = re.search(r'\[FIND_CONTACT:\s*["\']?(.+?)["\']?\]', response, re.IGNORECASE)
        if find_match:
            query = find_match.group(1).strip()
            try:
                contacts = db.find_contacts(user_id, query, limit=5)
                if contacts:
                    lines = []
                    for c in contacts:
                        lines.append(format_contact(c, verbose=True))
                        lines.append(f"   ID: `{c['id']}`\n")
                    results.append("\n".join(lines))
                else:
                    results.append(f"No contacts found matching '{query}'.")
            except Exception as e:
                results.append(f"Error searching: {str(e)[:50]}")
        
        # [SHOW_CONTACT: id]
        show_match = re.search(r'\[SHOW_CONTACT:\s*(\d+)\]', response, re.IGNORECASE)
        if show_match:
            contact_id = int(show_match.group(1))
            try:
                contact = db.get_contact_by_id(user_id, contact_id)
                if contact:
                    results.append(format_contact(contact, verbose=True) + f"\n   ID: `{contact['id']}`")
                else:
                    results.append(f"Contact ID {contact_id} not found.")
            except Exception as e:
                results.append(f"Error: {str(e)[:50]}")
        
        # [ADD_CONTACT: "name"]
        add_match = re.search(r'\[ADD_CONTACT:\s*["\']?(.+?)["\']?\]', response, re.IGNORECASE)
        if add_match:
            name = add_match.group(1).strip()
            try:
                met_at = self.config.get("default_met_at", "")
                contact = db.add_contact(user_id=user_id, name=name, met_at=met_at) if met_at else db.add_contact(user_id=user_id, name=name)
                results.append(f"✅ Added contact: {contact['name']} (ID: {contact['id']})")
            except Exception as e:
                results.append(f"Error adding contact: {str(e)[:50]}")
        
        # [UPDATE_CONTACT: id, field, value]
        update_match = re.search(r'\[UPDATE_CONTACT:\s*(\d+),\s*(\w+),\s*["\']?(.+?)["\']?\]', response, re.IGNORECASE)
        if update_match:
            contact_id = int(update_match.group(1))
            field = update_match.group(2).lower()
            value = update_match.group(3).strip()
            try:
                contact = db.update_contact(user_id, contact_id, **{field: value})
                if contact:
                    results.append(f"✅ Updated contact: {format_contact(contact)}")
                else:
                    results.append(f"Contact ID {contact_id} not found.")
            except Exception as e:
                results.append(f"Error updating: {str(e)[:50]}")
        
        return "\n".join(results) if results else None
    
    def get_help_text(self) -> str:
        """Return help text for contacts commands."""
        return """**Contacts:**
- `/addcontact <name>` - Add a new contact
- `/editcontact <id> <field> <value>` - Edit a contact (fields: name, email, phone, company, title, etc.)
- `/findcontact <query>` - Search contacts
- `/contacts` - List all contacts
- `/deletecontact <id>` - Delete a contact

📸 **Tip:** Send a photo of a business card and I'll extract the contact info automatically!"""
    
    def get_llm_prompt_section(self) -> str:
        """Return LLM prompt section for contacts."""
        return """**Contacts Management:**
You can manage contacts using these actions:
- [LIST_CONTACTS] - List all contacts
- [FIND_CONTACT: "query"] - Search for contacts by name, company, email, etc.
- [SHOW_CONTACT: id] - Show full details for a contact
- [ADD_CONTACT: "name"] - Add a new contact
- [UPDATE_CONTACT: id, field, value] - Update a contact field

When users mention people they know or want to remember, offer to add them as contacts."""
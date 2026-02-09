"""
Credential Manager for AnyArchie.

Handles self-service Google API credential setup via Telegram conversation.
Users can upload JSON credentials files and configure Calendar, Gmail, and Sheets.
"""
import json
import re
from typing import Optional, Dict, Callable
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import db
from bot import encryption


# Setup states
SETUP_STATES = {
    "idle": "Not in setup",
    "choosing_service": "Choosing which Google service to configure",
    "waiting_calendar_json": "Waiting for Calendar credentials JSON",
    "waiting_calendar_id": "Waiting for Calendar ID",
    "waiting_gmail_json": "Waiting for Gmail credentials JSON",
    "waiting_sheets_json": "Waiting for Sheets credentials JSON",
    "waiting_sheets_id": "Waiting for Sheets ID",
}


def get_setup_state(user_id: int) -> str:
    """Get current setup state for user"""
    state = db.get_context(user_id, "setup_state")
    return state if state else "idle"


def set_setup_state(user_id: int, state: str) -> None:
    """Set setup state for user"""
    db.set_context(user_id, "setup_state", state)


def start_setup(user_id: int, send_message: Callable[[int, str], None]) -> None:
    """Start the Google setup flow"""
    user = db.get_user_by_id(user_id)
    if not user:
        return
    
    telegram_id = user['telegram_id']
    
    message = """🔧 **Google Integration Setup**

Which service would you like to configure?

1️⃣ **Google Calendar** - View your calendar events
2️⃣ **Gmail** - Email digests and search
3️⃣ **Google Sheets** - Read from your spreadsheets

Reply with the number (1, 2, or 3) or the service name."""
    
    send_message(telegram_id, message)
    set_setup_state(user_id, "choosing_service")


def handle_setup_message(user_id: int, text: str, send_message: Callable[[int, str], None]) -> bool:
    """
    Handle a message during setup flow.
    
    Returns:
        True if message was handled as part of setup, False otherwise
    """
    state = get_setup_state(user_id)
    
    if state == "idle":
        return False
    
    user = db.get_user_by_id(user_id)
    if not user:
        return False
    
    telegram_id = user['telegram_id']
    
    if state == "choosing_service":
        return _handle_service_choice(user_id, text, send_message, telegram_id)
    
    elif state == "waiting_calendar_json":
        return _handle_calendar_json(user_id, text, send_message, telegram_id)
    
    elif state == "waiting_calendar_id":
        return _handle_calendar_id(user_id, text, send_message, telegram_id)
    
    elif state == "waiting_gmail_json":
        return _handle_gmail_json(user_id, text, send_message, telegram_id)
    
    elif state == "waiting_sheets_json":
        return _handle_sheets_json(user_id, text, send_message, telegram_id)
    
    elif state == "waiting_sheets_id":
        return _handle_sheets_id(user_id, text, send_message, telegram_id)
    
    return False


def _handle_service_choice(user_id: int, text: str, send_message: Callable, telegram_id: int) -> bool:
    """Handle user choosing which service to configure"""
    text_lower = text.lower().strip()
    
    if text_lower in ["1", "calendar", "google calendar"]:
        _start_calendar_setup(user_id, send_message, telegram_id)
        return True
    
    elif text_lower in ["2", "gmail", "email"]:
        _start_gmail_setup(user_id, send_message, telegram_id)
        return True
    
    elif text_lower in ["3", "sheets", "google sheets"]:
        _start_sheets_setup(user_id, send_message, telegram_id)
        return True
    
    elif text_lower in ["cancel", "skip", "done"]:
        set_setup_state(user_id, "idle")
        send_message(telegram_id, "Setup cancelled. Use /setup google to start again.")
        return True
    
    return False


def _start_calendar_setup(user_id: int, send_message: Callable, telegram_id: int) -> None:
    """Start Google Calendar setup"""
    message = """📅 **Google Calendar Setup**

To connect your Google Calendar:

**Step 1:** Go to https://console.cloud.google.com/
**Step 2:** Create a new project (or select existing)
**Step 3:** Enable "Google Calendar API"
**Step 4:** Create credentials → Service Account
**Step 5:** Download the JSON key file
**Step 6:** Send me that JSON file here

Or reply "skip" to cancel."""
    
    send_message(telegram_id, message)
    set_setup_state(user_id, "waiting_calendar_json")


def _handle_calendar_json(user_id: int, text: str, send_message: Callable, telegram_id: int) -> bool:
    """Handle Calendar credentials JSON upload"""
    # Check if it's a skip command
    if text.lower().strip() in ["skip", "cancel"]:
        set_setup_state(user_id, "idle")
        send_message(telegram_id, "Calendar setup cancelled.")
        return True
    
    # Try to parse as JSON
    try:
        creds_json = json.loads(text)
        
        # Validate it looks like a service account JSON
        if "type" not in creds_json or creds_json.get("type") != "service_account":
            send_message(
                telegram_id,
                "❌ This doesn't look like a service account JSON file.\n\n"
                "Make sure you downloaded the service account credentials, not OAuth credentials."
            )
            return True
        
        # Encrypt and save
        encrypted = encryption.encrypt_data(text)
        db.save_user_credential(user_id, "google_calendar", encrypted)
        
        # Now ask for Calendar ID
        send_message(
            telegram_id,
            "✅ Credentials saved!\n\n"
            "**Step 7:** Now I need your Calendar ID.\n\n"
            "To find it:\n"
            "1. Go to https://calendar.google.com/\n"
            "2. Click the three dots next to your calendar\n"
            "3. Select 'Settings and sharing'\n"
            "4. Scroll to 'Integrate calendar'\n"
            "5. Copy the 'Calendar ID' (usually your email address)\n\n"
            "Send me your Calendar ID, or reply 'skip' to cancel."
        )
        set_setup_state(user_id, "waiting_calendar_id")
        return True
    
    except json.JSONDecodeError:
        send_message(
            telegram_id,
            "❌ That doesn't look like valid JSON. Please send the JSON file contents, or reply 'skip' to cancel."
        )
        return True
    except Exception as e:
        send_message(telegram_id, f"❌ Error saving credentials: {str(e)[:100]}")
        return True


def _handle_calendar_id(user_id: int, text: str, send_message: Callable, telegram_id: int) -> bool:
    """Handle Calendar ID input"""
    if text.lower().strip() in ["skip", "cancel"]:
        set_setup_state(user_id, "idle")
        send_message(telegram_id, "Calendar setup cancelled.")
        return True
    
    calendar_id = text.strip()
    
    # Save calendar ID to context
    db.set_context(user_id, "calendar_id", calendar_id)
    
    set_setup_state(user_id, "idle")
    send_message(
        telegram_id,
        f"✅ Google Calendar setup complete!\n\n"
        f"Calendar ID: `{calendar_id}`\n\n"
        "You can now use `/calendar` to view your events.\n\n"
        "Use `/setup google` to configure other services."
    )
    return True


def _start_gmail_setup(user_id: int, send_message: Callable, telegram_id: int) -> None:
    """Start Gmail setup"""
    message = """📧 **Gmail Setup**

To connect your Gmail:

**Step 1:** Go to https://myaccount.google.com/apppasswords
**Step 2:** Sign in and enable 2-Step Verification if needed
**Step 3:** Create an app password for "Mail"
**Step 4:** Copy the 16-character password
**Step 5:** Send me:\n\n`
EMAIL_ADDRESS=your.email@gmail.com
EMAIL_APP_PASSWORD=your-16-char-password
`\n\nOr reply "skip" to cancel."""
    
    send_message(telegram_id, message)
    set_setup_state(user_id, "waiting_gmail_json")


def _handle_gmail_json(user_id: int, text: str, send_message: Callable, telegram_id: int) -> bool:
    """Handle Gmail credentials"""
    if text.lower().strip() in ["skip", "cancel"]:
        set_setup_state(user_id, "idle")
        send_message(telegram_id, "Gmail setup cancelled.")
        return True
    
    # Parse email and password from text
    email_match = re.search(r'EMAIL_ADDRESS=([^\s]+)', text)
    password_match = re.search(r'EMAIL_APP_PASSWORD=([^\s]+)', text)
    
    if not email_match or not password_match:
        send_message(
            telegram_id,
            "❌ Please send in format:\n\n"
            "`EMAIL_ADDRESS=your.email@gmail.com\n"
            "EMAIL_APP_PASSWORD=your-16-char-password`\n\n"
            "Or reply 'skip' to cancel."
        )
        return True
    
    email = email_match.group(1)
    password = password_match.group(1)
    
    # Encrypt and save
    creds_data = json.dumps({"email": email, "password": password})
    encrypted = encryption.encrypt_data(creds_data)
    db.save_user_credential(user_id, "gmail", encrypted)
    
    # Also save email to context for easy access
    db.set_context(user_id, "email_address", email)
    
    set_setup_state(user_id, "idle")
    send_message(
        telegram_id,
        f"✅ Gmail setup complete!\n\n"
        f"Email: `{email}`\n\n"
        "You can now use `/emails` to get email digests.\n\n"
        "Use `/setup google` to configure other services."
    )
    return True


def _start_sheets_setup(user_id: int, send_message: Callable, telegram_id: int) -> None:
    """Start Google Sheets setup"""
    message = """📊 **Google Sheets Setup**

To connect your Google Sheets:

**Step 1:** Go to https://console.cloud.google.com/
**Step 2:** Create a new project (or select existing)
**Step 3:** Enable "Google Sheets API"
**Step 4:** Create credentials → Service Account
**Step 5:** Download the JSON key file
**Step 6:** Send me that JSON file here

Or reply "skip" to cancel."""
    
    send_message(telegram_id, message)
    set_setup_state(user_id, "waiting_sheets_json")


def _handle_sheets_json(user_id: int, text: str, send_message: Callable, telegram_id: int) -> bool:
    """Handle Sheets credentials JSON upload"""
    if text.lower().strip() in ["skip", "cancel"]:
        set_setup_state(user_id, "idle")
        send_message(telegram_id, "Sheets setup cancelled.")
        return True
    
    try:
        creds_json = json.loads(text)
        
        if "type" not in creds_json or creds_json.get("type") != "service_account":
            send_message(
                telegram_id,
                "❌ This doesn't look like a service account JSON file.\n\n"
                "Make sure you downloaded the service account credentials."
            )
            return True
        
        # Encrypt and save
        encrypted = encryption.encrypt_data(text)
        db.save_user_credential(user_id, "google_sheets", encrypted)
        
        # Now ask for Sheet ID
        send_message(
            telegram_id,
            "✅ Credentials saved!\n\n"
            "**Step 7:** Now I need your Sheet ID.\n\n"
            "To find it:\n"
            "1. Open your Google Sheet\n"
            "2. Look at the URL: `https://docs.google.com/spreadsheets/d/SHEET_ID_HERE/edit`\n"
            "3. Copy the SHEET_ID_HERE part\n\n"
            "Send me your Sheet ID, or reply 'skip' to cancel."
        )
        set_setup_state(user_id, "waiting_sheets_id")
        return True
    
    except json.JSONDecodeError:
        send_message(
            telegram_id,
            "❌ That doesn't look like valid JSON. Please send the JSON file contents, or reply 'skip' to cancel."
        )
        return True
    except Exception as e:
        send_message(telegram_id, f"❌ Error saving credentials: {str(e)[:100]}")
        return True


def _handle_sheets_id(user_id: int, text: str, send_message: Callable, telegram_id: int) -> bool:
    """Handle Sheets ID input"""
    if text.lower().strip() in ["skip", "cancel"]:
        set_setup_state(user_id, "idle")
        send_message(telegram_id, "Sheets setup cancelled.")
        return True
    
    sheet_id = text.strip()
    
    # Save sheet ID to context
    db.set_context(user_id, "google_sheet_id", sheet_id)
    
    set_setup_state(user_id, "idle")
    send_message(
        telegram_id,
        f"✅ Google Sheets setup complete!\n\n"
        f"Sheet ID: `{sheet_id}`\n\n"
        "You can now use `/sheet` to read from your spreadsheet.\n\n"
        "Use `/setup google` to configure other services."
    )
    return True


def get_user_credential(user_id: int, credential_type: str) -> Optional[Dict]:
    """
    Get and decrypt user credential.
    
    Returns:
        Decrypted credential data as dict, or None if not found
    """
    cred = db.get_user_credential(user_id, credential_type)
    if not cred:
        return None
    
    try:
        decrypted = encryption.decrypt_data(cred['encrypted_data'])
        return json.loads(decrypted)
    except Exception:
        return None
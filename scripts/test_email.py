#!/usr/bin/env python3
"""
Test email fetch for Miranda
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import db
from bot import email_client


def main():
    # Get Miranda's user record
    user = db.get_user_by_telegram_id(8506315004)
    
    if not user:
        print("User not found!")
        return
    
    email_address = user.get('email_address')
    app_password = user.get('email_app_password')
    
    if not email_address or not app_password:
        print("Email not configured for this user")
        return
    
    print(f"Fetching emails for: {email_address[:3]}***")
    print("-" * 40)
    
    try:
        emails = email_client.fetch_emails(
            email_address=email_address,
            app_password=app_password,
            hours=48
        )
        
        print(f"Found {len(emails)} emails in last 48 hours\n")
        
        # Show first 3 (sanitized)
        for i, e in enumerate(emails[:3], 1):
            # Sanitize sender - just show first name or domain
            sender_display = e.sender.split()[0] if e.sender else e.sender_email.split('@')[1]
            time_str = e.date.strftime("%b %d %I:%M %p")
            junk_tag = " [JUNK]" if e.is_junk else ""
            
            print(f"{i}. From: {sender_display}... ({time_str}){junk_tag}")
            print(f"   Subject: {e.subject[:50]}...")
            print()
            
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()

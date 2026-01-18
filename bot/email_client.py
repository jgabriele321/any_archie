"""
AnyArchie Email Client
Fetches and summarizes emails via IMAP
"""
import email
import imaplib
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from dataclasses import dataclass
from typing import List, Tuple, Optional


@dataclass
class EmailMessage:
    """Represents a parsed email message."""
    subject: str
    sender: str
    sender_email: str
    date: datetime
    snippet: str
    is_junk: bool


# Common junk patterns
JUNK_DOMAINS = [
    "noreply", "no-reply", "newsletter", "marketing", "promo",
    "notifications", "updates", "info@", "hello@", "support@",
]

JUNK_SUBJECT_PATTERNS = [
    "% off", "save $", "sale", "discount", "limited time",
    "act now", "free", "unsubscribe", "weekly digest",
]


def _decode_str(s) -> str:
    """Decode email header string."""
    if s is None:
        return ""
    decoded_parts = decode_header(s)
    result = []
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            result.append(part.decode(encoding or 'utf-8', errors='replace'))
        else:
            result.append(part)
    return ''.join(result)


def _parse_sender(from_header: str) -> Tuple[str, str]:
    """Parse sender name and email from From header."""
    from_header = _decode_str(from_header)
    if '<' in from_header and '>' in from_header:
        name = from_header.split('<')[0].strip().strip('"')
        email_addr = from_header.split('<')[1].split('>')[0]
    else:
        name = ""
        email_addr = from_header.strip()
    return name, email_addr


def _get_body_snippet(msg) -> str:
    """Extract first ~200 chars of email body."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode('utf-8', errors='replace')
                        break
                except:
                    pass
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode('utf-8', errors='replace')
        except:
            pass
    body = ' '.join(body.strip().split())
    return body[:200] if body else ""


def _classify_email(subject: str, sender_email: str) -> bool:
    """Returns True if junk, False if important."""
    sender_lower = sender_email.lower()
    subject_lower = subject.lower()
    
    # Check junk patterns in sender
    for pattern in JUNK_DOMAINS:
        if pattern in sender_lower:
            return True
    
    # Check junk patterns in subject
    for pattern in JUNK_SUBJECT_PATTERNS:
        if pattern in subject_lower:
            return True
    
    return False


def fetch_emails(
    email_address: str,
    app_password: str,
    hours: int = 24,
    imap_server: str = "imap.gmail.com",
    imap_port: int = 993
) -> List[EmailMessage]:
    """
    Fetch recent emails from inbox.
    
    Args:
        email_address: User's email address
        app_password: Gmail app password
        hours: How many hours back to fetch
        imap_server: IMAP server address
        imap_port: IMAP port
    
    Returns:
        List of EmailMessage objects
    """
    mail = imaplib.IMAP4_SSL(imap_server, imap_port)
    mail.login(email_address, app_password)
    mail.select("INBOX")
    
    # Search for emails from the last few days (IMAP date search is date-only)
    since_date = (datetime.now() - timedelta(days=3)).strftime("%d-%b-%Y")
    _, message_numbers = mail.search(None, f'(SINCE "{since_date}")')
    
    emails = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    for num in reversed(message_numbers[0].split()[-100:]):
        try:
            _, msg_data = mail.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])
            
            subject = _decode_str(msg.get("Subject", "(no subject)"))
            sender_name, sender_email = _parse_sender(msg.get("From", ""))
            
            # Parse date
            date_str = msg.get("Date", "")
            date = None
            for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%d %b %Y %H:%M:%S %z"]:
                try:
                    date = datetime.strptime(date_str[:31], fmt)
                    break
                except:
                    pass
            if not date:
                date = datetime.now(timezone.utc)
            
            # Filter by time
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            if date < cutoff:
                continue
            
            snippet = _get_body_snippet(msg)
            is_junk = _classify_email(subject, sender_email)
            
            emails.append(EmailMessage(
                subject=subject,
                sender=sender_name or sender_email,
                sender_email=sender_email,
                date=date,
                snippet=snippet,
                is_junk=is_junk,
            ))
        except Exception as e:
            continue
    
    mail.logout()
    return emails


def get_email_digest(
    email_address: str,
    app_password: str,
    hours: int = 24,
    imap_server: str = "imap.gmail.com"
) -> str:
    """
    Get a formatted digest of recent emails.
    
    Returns:
        Formatted string with important emails first, then junk summary.
    """
    try:
        emails = fetch_emails(email_address, app_password, hours, imap_server)
    except imaplib.IMAP4.error as e:
        return f"❌ Couldn't connect to email: Authentication failed. Please check your email credentials."
    except Exception as e:
        return f"❌ Couldn't fetch emails: {str(e)}"
    
    if not emails:
        return f"📭 No emails in the last {hours} hours."
    
    important = [e for e in emails if not e.is_junk]
    junk = [e for e in emails if e.is_junk]
    
    lines = [f"📧 **Email Digest** (last {hours} hours)\n"]
    
    # Important emails
    if important:
        lines.append(f"**📬 Important ({len(important)}):**\n")
        for e in important[:15]:
            time_str = e.date.strftime("%I:%M %p").lstrip("0")
            lines.append(f"• **{e.sender}** ({time_str})")
            lines.append(f"  {e.subject[:60]}")
    else:
        lines.append("✅ No important emails.\n")
    
    # Junk summary
    if junk:
        lines.append(f"\n**🗑️ Filtered ({len(junk)}):**")
        junk_senders = {}
        for e in junk:
            junk_senders[e.sender] = junk_senders.get(e.sender, 0) + 1
        for sender, count in sorted(junk_senders.items(), key=lambda x: -x[1])[:5]:
            lines.append(f"• {sender}: {count}")
    
    return "\n".join(lines)

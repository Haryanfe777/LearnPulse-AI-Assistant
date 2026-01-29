"""Support ticket creation and escalation handling.

This module handles:
- Detecting teacher dissatisfaction
- Creating support tickets with conversation context
- Sending notifications to support team
"""
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.core.logging import get_logger

logger = get_logger(__name__)

# Support email configuration
SUPPORT_EMAIL = "support@learnpulse.ai"
ESCALATION_THRESHOLD = 3  # Number of dissatisfaction signals before auto-escalation


def detect_dissatisfaction(message: str) -> bool:
    """
    Detect if a teacher's message indicates dissatisfaction.
    
    Args:
        message: The teacher's message text
        
    Returns:
        True if dissatisfaction is detected, False otherwise
    """
    dissatisfaction_keywords = [
        "not satisfied",
        "doesn't help",
        "still wrong",
        "not working",
        "i need help",
        "speak to someone",
        "talk to support",
        "contact support",
        "human support",
        "this is wrong",
        "not what i asked",
        "doesn't answer",
        "unclear",
        "confusing",
        "frustrated",
        "not helpful"
    ]
    
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in dissatisfaction_keywords)


def create_conversation_file(
    conversation_history: List[Dict[str, str]],
    session_id: str,
    user_info: Dict[str, Any]
) -> Path:
    """
    Create a .txt file with conversation history.
    
    Args:
        conversation_history: List of message dicts with 'role' and 'content'
        session_id: Session identifier
        user_info: Dictionary with user details (email, name, etc.)
        
    Returns:
        Path to the created file
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"support_ticket_{session_id}_{timestamp}.txt"
    filepath = Path("support_tickets") / filename
    
    # Ensure directory exists
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    # Write conversation to file
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("LEARNPULSE AI INSTRUCTOR ASSISTANT - SUPPORT TICKET\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"Ticket ID: {session_id}\n")
        f.write(f"Timestamp: {datetime.now().isoformat()}\n")
        f.write(f"Teacher Email: {user_info.get('email', 'N/A')}\n")
        f.write(f"Teacher Name: {user_info.get('name', 'N/A')}\n")
        f.write(f"User ID: {user_info.get('user_id', 'N/A')}\n")
        f.write(f"Role: {user_info.get('role', 'N/A')}\n")
        f.write("\n" + "=" * 80 + "\n")
        f.write("CONVERSATION HISTORY\n")
        f.write("=" * 80 + "\n\n")
        
        for i, msg in enumerate(conversation_history, 1):
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")
            f.write(f"[{i}] {role}:\n")
            f.write(f"{content}\n")
            f.write("\n" + "-" * 80 + "\n\n")
        
        f.write("=" * 80 + "\n")
        f.write("END OF CONVERSATION\n")
        f.write("=" * 80 + "\n")
    
    logger.info(f"Created conversation file: {filepath}")
    return filepath


def send_support_ticket_email(
    user_info: Dict[str, Any],
    issue_summary: str,
    conversation_file: Path,
    smtp_config: Optional[Dict[str, str]] = None
) -> bool:
    """
    Send support ticket email with conversation attachment.
    
    Args:
        user_info: Dictionary with user details
        issue_summary: Brief summary of the issue
        conversation_file: Path to conversation .txt file
        smtp_config: Optional SMTP configuration (for production)
        
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        # In development, just log the ticket
        if not smtp_config:
            logger.warning("SMTP not configured - logging ticket instead of sending email")
            logger.info(f"SUPPORT TICKET WOULD BE SENT:")
            logger.info(f"  To: {SUPPORT_EMAIL}")
            logger.info(f"  From: {user_info.get('email', 'N/A')}")
            logger.info(f"  Subject: Support Request - {issue_summary}")
            logger.info(f"  Attachment: {conversation_file}")
            return True
        
        # Production: Send actual email via SMTP
        msg = MIMEMultipart()
        msg['From'] = smtp_config.get('from_email', 'noreply@learnpulse.ai')
        msg['To'] = SUPPORT_EMAIL
        msg['Subject'] = f"Teacher Support Request - {issue_summary}"
        
        # Email body
        body = f"""
A teacher has requested support assistance.

Teacher Details:
- Name: {user_info.get('name', 'N/A')}
- Email: {user_info.get('email', 'N/A')}
- User ID: {user_info.get('user_id', 'N/A')}
- Role: {user_info.get('role', 'N/A')}

Issue Summary:
{issue_summary}

Full conversation history is attached.

---
LearnPulse AI Instructor Assistant
Generated: {datetime.now().isoformat()}
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Attach conversation file
        with open(conversation_file, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {conversation_file.name}'
            )
            msg.attach(part)
        
        # Send email
        with smtplib.SMTP(smtp_config['host'], smtp_config.get('port', 587)) as server:
            server.starttls()
            if 'username' in smtp_config and 'password' in smtp_config:
                server.login(smtp_config['username'], smtp_config['password'])
            server.send_message(msg)
        
        logger.info(f"Support ticket email sent successfully to {SUPPORT_EMAIL}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send support ticket email: {e}")
        return False


def create_support_ticket(
    session_id: str,
    user_info: Dict[str, Any],
    conversation_history: List[Dict[str, str]],
    issue_summary: str,
    smtp_config: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Create a support ticket with conversation context.
    
    This is the main function called by the /chat endpoint when escalation is triggered.
    
    Args:
        session_id: Session identifier
        user_info: Dictionary with user details (email, name, user_id, role)
        conversation_history: List of message dicts
        issue_summary: Brief summary of the issue
        smtp_config: Optional SMTP configuration for email sending
        
    Returns:
        Dictionary with ticket details and status
    """
    try:
        # Create conversation file
        conversation_file = create_conversation_file(
            conversation_history=conversation_history,
            session_id=session_id,
            user_info=user_info
        )
        
        # Send email (or log if SMTP not configured)
        email_sent = send_support_ticket_email(
            user_info=user_info,
            issue_summary=issue_summary,
            conversation_file=conversation_file,
            smtp_config=smtp_config
        )
        
        ticket_id = f"TICKET-{session_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        return {
            "success": True,
            "ticket_id": ticket_id,
            "email_sent": email_sent,
            "conversation_file": str(conversation_file),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to create support ticket: {e}")
        return {
            "success": False,
            "error": str(e)
        }

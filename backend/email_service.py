"""Email service for sending contact form submissions via Mailgun."""

import logging
from datetime import UTC, datetime

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)


class EmailServiceError(Exception):
    """Raised when email sending fails."""


def generate_email_html(name: str, email: str, subject: str, message: str) -> str:
    """
    Generate HTML email content for contact form submission.

    Args:
        name: Sender's name
        email: Sender's email address
        subject: Subject of the message
        message: Message content

    Returns:
        str: HTML formatted email
    """
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: 'IBM Plex Sans', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background-color: #3778be;
                color: white;
                padding: 20px;
                border-radius: 5px 5px 0 0;
            }}
            .content {{
                background-color: #f9f9f9;
                padding: 20px;
                border: 1px solid #ddd;
                border-top: none;
            }}
            .field {{
                margin-bottom: 15px;
            }}
            .label {{
                font-weight: bold;
                color: #3778be;
            }}
            .value {{
                margin-top: 5px;
                padding: 10px;
                background-color: white;
                border-left: 3px solid #00aa41;
            }}
            .message-content {{
                white-space: pre-wrap;
                word-wrap: break-word;
            }}
            .footer {{
                margin-top: 20px;
                padding-top: 20px;
                border-top: 2px solid #3778be;
                font-size: 0.9em;
                color: #666;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>PyConDE Contact Form Submission</h1>
        </div>
        <div class="content">
            <div class="field">
                <div class="label">From:</div>
                <div class="value">{name}</div>
            </div>
            <div class="field">
                <div class="label">Email:</div>
                <div class="value"><a href="mailto:{email}">{email}</a></div>
            </div>
            <div class="field">
                <div class="label">Subject:</div>
                <div class="value">{subject}</div>
            </div>
            <div class="field">
                <div class="label">Message:</div>
                <div class="value message-content">{message}</div>
            </div>
            <div class="footer">
                <p>Submitted: {timestamp}</p>
                <p>This message was sent via the PyConDE 2026 contact form.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html


def generate_email_text(name: str, email: str, subject: str, message: str) -> str:
    """
    Generate plain text email content for contact form submission.

    Args:
        name: Sender's name
        email: Sender's email address
        subject: Subject of the message
        message: Message content

    Returns:
        str: Plain text formatted email
    """
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    text = f"""
PyConDE Contact Form Submission
================================

From: {name}
Email: {email}
Subject: {subject}

Message:
--------
{message}

--------
Submitted: {timestamp}
This message was sent via the PyConDE 2026 contact form.
    """
    return text.strip()


async def send_contact_email(
    name: str,
    email: str,
    subject: str,
    message: str,
) -> bool:
    """
    Send contact form submission via Mailgun.

    Args:
        name: Sender's name
        email: Sender's email address
        subject: Subject of the message
        message: Message content

    Returns:
        bool: True if email was sent successfully

    Raises:
        EmailServiceError: If email sending fails
    """
    try:
        # Prepare email
        email_subject = f"{settings.email_subject_prefix} {subject}"
        html_body = generate_email_html(name, email, subject, message)
        text_body = generate_email_text(name, email, subject, message)

        # Construct Mailgun API URL
        mailgun_url = (
            f"{settings.mailgun_api_base_url}/{settings.mailgun_domain}/messages"
        )

        # Prepare email data for Mailgun
        email_data = {
            "from": settings.email_sender,
            "to": settings.email_recipient,
            "subject": email_subject,
            "text": text_body,
            "html": html_body,
            "h:Reply-To": email,
        }

        # Send email via Mailgun
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                mailgun_url,
                auth=("api", settings.mailgun_api_key),
                data=email_data,
            )
            response.raise_for_status()
            result = response.json()

        message_id = result.get("id", "unknown")
        logger.info(
            f"Email sent successfully via Mailgun. MessageId: {message_id}, From: {email}"
        )
        return True

    except httpx.HTTPStatusError as e:
        error_msg = f"Mailgun API error (status {e.response.status_code}): {e.response.text}"
        logger.error(error_msg)
        raise EmailServiceError(error_msg) from e
    except httpx.HTTPError as e:
        error_msg = f"Failed to send email via Mailgun: {e}"
        logger.error(error_msg)
        raise EmailServiceError(error_msg) from e
    except Exception as e:
        error_msg = f"Unexpected error sending email: {e}"
        logger.error(error_msg)
        raise EmailServiceError(error_msg) from e

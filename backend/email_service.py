"""Email service for sending contact form submissions via AWS SES."""

import logging
from datetime import UTC, datetime

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from backend.config import settings

logger = logging.getLogger(__name__)


class EmailServiceError(Exception):
    """Raised when email sending fails."""


def get_ses_client():
    """Create and return an AWS SES client."""
    return boto3.client(
        "ses",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )


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
    Send contact form submission via AWS SES.

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
        ses_client = get_ses_client()

        # Prepare email
        email_subject = f"{settings.email_subject_prefix} {subject}"
        html_body = generate_email_html(name, email, subject, message)
        text_body = generate_email_text(name, email, subject, message)

        # Send email
        response = ses_client.send_email(
            Source=settings.email_sender,
            Destination={
                "ToAddresses": [settings.email_recipient],
            },
            Message={
                "Subject": {
                    "Data": email_subject,
                    "Charset": "UTF-8",
                },
                "Body": {
                    "Text": {
                        "Data": text_body,
                        "Charset": "UTF-8",
                    },
                    "Html": {
                        "Data": html_body,
                        "Charset": "UTF-8",
                    },
                },
            },
            ReplyToAddresses=[email],
        )

        message_id = response.get("MessageId")
        logger.info(
            f"Email sent successfully. MessageId: {message_id}, From: {email}"
        )
        return True

    except (BotoCoreError, ClientError) as e:
        error_msg = f"Failed to send email via SES: {e}"
        logger.error(error_msg)
        raise EmailServiceError(error_msg) from e
    except Exception as e:
        error_msg = f"Unexpected error sending email: {e}"
        logger.error(error_msg)
        raise EmailServiceError(error_msg) from e

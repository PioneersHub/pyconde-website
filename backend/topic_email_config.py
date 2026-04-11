"""Topic-based email routing configuration.

Resolves contact form topics to specific recipient email addresses
using the TOPIC_EMAILS environment variable (JSON mapping).
Topics not configured fall back to EMAIL_RECIPIENT.
"""

from config import settings


def get_recipient_for_topic(topic: str, fallback: str) -> str:
    """
    Get the email recipient for a given topic.

    Args:
        topic: The contact form topic (must match TopicEnum value).
        fallback: Fallback email if topic not configured.

    Returns:
        Email address for the topic, or fallback if not found.
    """
    return settings.topic_emails.get(topic, fallback)

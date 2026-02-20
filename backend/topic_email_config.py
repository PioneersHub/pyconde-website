"""Topic-based email routing configuration."""

import logging
from pathlib import Path

import yaml
from pydantic import BaseModel, EmailStr

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path(__file__).parent / "topic_emails.yaml"


class TopicEmailConfig(BaseModel):
    """Configuration for topic-based email routing."""

    topics: dict[str, EmailStr] = {}


def load_topic_email_config(config_path: Path | None = None) -> TopicEmailConfig:
    """
    Load topic email configuration from YAML file.

    Args:
        config_path: Path to YAML config file. Uses default if not provided.

    Returns:
        TopicEmailConfig with loaded settings, or empty config if file missing.
    """
    path = config_path or DEFAULT_CONFIG_PATH

    if not path.exists():
        logger.warning("Topic email config not found at %s", path)
        return TopicEmailConfig()

    try:
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        config = TopicEmailConfig(**data)
        logger.info(
            "Loaded topic email config: %d topics configured",
            len(config.topics),
        )
        return config
    except yaml.YAMLError as e:
        logger.error("Failed to parse topic email config: %s", e)
        return TopicEmailConfig()
    except Exception as e:
        logger.error("Failed to load topic email config: %s", e)
        return TopicEmailConfig()


# Load configuration at module import time
topic_email_config = load_topic_email_config()


def get_recipient_for_topic(topic: str, fallback: str) -> str:
    """
    Get the email recipient for a given topic.

    Args:
        topic: The contact form topic (must match TopicEnum value)
        fallback: Fallback email if topic not configured

    Returns:
        Email address for the topic, or fallback if not found.
    """
    return topic_email_config.topics.get(topic, fallback)

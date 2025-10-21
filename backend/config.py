"""Configuration settings for the contact form backend."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # reCAPTCHA settings
    recaptcha_secret_key: str
    recaptcha_verify_url: str = "https://www.google.com/recaptcha/api/siteverify"
    recaptcha_min_score: float = 0.5

    # Email settings
    email_recipient: str = "info26@pycon.de"
    email_sender: str = "noreply@pycon.de"
    email_subject_prefix: str = "[PyConDE Contact Form]"

    # AWS SES settings
    aws_region: str = "eu-central-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None

    # CORS settings
    allowed_origins: list[str] = [
        "https://2026.pycon.de",
        "https://pycon.de",
        "http://localhost:5001",
        "http://127.0.0.1:5001",
    ]

    # Rate limiting
    rate_limit_per_minute: int = 5
    rate_limit_per_hour: int = 20

    # Application settings
    debug: bool = False
    api_prefix: str = "/api"


settings = Settings()

"""Configuration settings for the contact form backend."""

from pydantic import field_validator
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

    # Mailgun settings
    mailgun_api_key: str
    mailgun_domain: str
    mailgun_api_base_url: str = "https://api.mailgun.net/v3"

    # CORS settings
    # Note: In .env file, use comma-separated string: "origin1,origin2,origin3"
    allowed_origins: str = "https://2026.pycon.de,https://pycon.de,http://localhost:5001,http://127.0.0.1:5001"

    # Rate limiting
    rate_limit_per_minute: int = 5
    rate_limit_per_hour: int = 20

    # Application settings
    debug: bool = False
    api_prefix: str = "/api"

    @field_validator("allowed_origins", mode="after")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse comma-separated CORS origins from environment variable."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


settings = Settings()

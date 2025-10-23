"""Google reCAPTCHA verification service."""

import httpx

from config import settings


class RecaptchaVerificationError(Exception):
    """Raised when reCAPTCHA verification fails."""


async def verify_recaptcha(token: str, remote_ip: str | None = None) -> bool:
    """
    Verify a reCAPTCHA token with Google's API.

    Args:
        token: The reCAPTCHA token from the client
        remote_ip: The user's IP address (optional but recommended)

    Returns:
        bool: True if verification succeeds

    Raises:
        RecaptchaVerificationError: If verification fails or encounters an error
    """
    if not token:
        raise RecaptchaVerificationError("reCAPTCHA token is required")

    payload = {
        "secret": settings.recaptcha_secret_key,
        "response": token,
    }

    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.recaptcha_verify_url,
                data=payload,
                timeout=10.0,
            )
            response.raise_for_status()
            result = response.json()

    except httpx.HTTPError as e:
        raise RecaptchaVerificationError(
            f"Failed to verify reCAPTCHA: {e}"
        ) from e

    if not result.get("success", False):
        error_codes = result.get("error-codes", [])
        raise RecaptchaVerificationError(
            f"reCAPTCHA verification failed: {', '.join(error_codes)}"
        )

    # For reCAPTCHA v3, check the score
    # For reCAPTCHA v2, score is not present but success=true is sufficient
    score = result.get("score")
    if score is not None and score < settings.recaptcha_min_score:
        raise RecaptchaVerificationError(
            f"reCAPTCHA score too low: {score} < {settings.recaptcha_min_score}"
        )

    return True

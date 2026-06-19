"""Certificate share API.

Two endpoints:
- GET /api/certs/{uuid}: returns obfuscated cert metadata plus a short-lived
  signed image URL.
- GET /api/cert-images/{uuid}: streams the cert PNG from a private S3 bucket,
  gated by an HMAC-signed token validated server-side.

PII protection model: cert PNGs (which carry the unobfuscated attendee name)
live exclusively in a private S3 bucket and are never publicly addressable.
The static site contains no per-cert data; this API is the only path through
which a cert holder's image is rendered.
"""

import hmac
import json
import logging
import time
from hashlib import sha256

import boto3
from botocore.exceptions import ClientError
from config import settings
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()

_s3_client = boto3.client("s3", region_name=settings.cert_bucket_region)


class CertResponse(BaseModel):
    """Metadata for a cert share page, returned to the browser JS shell.

    Only the per-cert PII-protected fields are returned. Share text templates
    and conference branding live in the site's databag/certificate_share.yaml
    and are rendered into the static page; the JS substitutes `{share_url}`
    client-side.
    """

    obfuscated_name: str = Field(..., description="Name with most characters masked")
    conference: str
    image_url: str = Field(
        ..., description="Signed, short-lived URL to fetch the cert PNG"
    )


def _require_config() -> tuple[str, str]:
    """Return (bucket, secret) or raise 500 if either is unset.

    Fail-fast: the API must not silently degrade to serving public images
    or unsigned tokens.
    """
    bucket = settings.cert_bucket_name
    secret = settings.cert_token_secret
    if not bucket or not secret:
        logger.error(
            "Cert API misconfigured: CERT_BUCKET_NAME / CERT_TOKEN_SECRET unset"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Certificate service unavailable.",
        )
    return bucket, secret


def _sign(uuid: str, expires_at: int, secret: str) -> str:
    """HMAC-SHA256 of '<uuid>:<expires_at>' as hex."""
    msg = f"{uuid}:{expires_at}".encode()
    return hmac.new(secret.encode(), msg, sha256).hexdigest()


def _mint_image_token(uuid: str, secret: str, ttl_seconds: int) -> str:
    """Return '<expires_at>.<hmac>' suitable for the `token` query param."""
    expires_at = int(time.time()) + ttl_seconds
    return f"{expires_at}.{_sign(uuid, expires_at, secret)}"


def _verify_image_token(uuid: str, token: str, secret: str) -> bool:
    """Constant-time check that the token signs <uuid> and has not expired."""
    try:
        expires_str, sig = token.split(".", 1)
        expires_at = int(expires_str)
    except (ValueError, AttributeError):
        return False
    if expires_at < int(time.time()):
        return False
    expected = _sign(uuid, expires_at, secret)
    return hmac.compare_digest(expected, sig)


def _get_s3_json(bucket: str, key: str) -> dict | None:
    """Return parsed JSON object from S3, or None if missing."""
    try:
        obj = _s3_client.get_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in ("NoSuchKey", "404"):
            return None
        raise
    return json.loads(obj["Body"].read())


def _get_s3_bytes(bucket: str, key: str) -> bytes | None:
    """Return raw bytes from S3, or None if missing."""
    try:
        obj = _s3_client.get_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in ("NoSuchKey", "404"):
            return None
        raise
    return obj["Body"].read()


@router.get(f"{settings.api_prefix}/certs/{{uuid}}", response_model=CertResponse)
async def get_cert(uuid: str, request: Request) -> CertResponse:
    """Return cert metadata and a short-lived signed image URL.

    The UUID itself gates access — no additional auth. Image URL is bound
    to this UUID via HMAC and expires in `CERT_TOKEN_TTL_SECONDS`.
    """
    bucket, secret = _require_config()
    client_ip = request.client.host if request.client else "unknown"

    metadata = _get_s3_json(bucket, f"{uuid}.json")
    if metadata is None:
        logger.info("Cert lookup miss for %s from %s", uuid, client_ip)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate not found.",
        )

    token = _mint_image_token(uuid, secret, settings.cert_token_ttl_seconds)
    base_url = str(request.base_url).rstrip("/")
    image_url = f"{base_url}{settings.api_prefix}/cert-images/{uuid}?token={token}"

    return CertResponse(image_url=image_url, **metadata)


@router.get(f"{settings.api_prefix}/cert-images/{{uuid}}")
async def get_cert_image(uuid: str, token: str, request: Request) -> Response:
    """Stream the cert PNG, gated by a valid HMAC token."""
    bucket, secret = _require_config()
    client_ip = request.client.host if request.client else "unknown"

    if not _verify_image_token(uuid, token, secret):
        logger.warning("Invalid cert image token for %s from %s", uuid, client_ip)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token.",
        )

    png_bytes = _get_s3_bytes(bucket, f"{uuid}.png")
    if png_bytes is None:
        logger.info("Cert image miss for %s from %s", uuid, client_ip)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate image not found.",
        )

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Content-Disposition": 'inline; filename="certificate.png"',
        },
    )

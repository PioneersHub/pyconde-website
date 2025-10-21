"""FastAPI application for PyConDE contact form backend."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from backend.config import settings
from backend.email_service import EmailServiceError, send_contact_email
from backend.recaptcha import RecaptchaVerificationError, verify_recaptcha

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    logger.info("Starting PyConDE Contact Form API")
    yield
    logger.info("Shutting down PyConDE Contact Form API")


# Initialize FastAPI app
app = FastAPI(
    title="PyConDE Contact Form API",
    description="Backend API for PyConDE website contact form with reCAPTCHA protection",
    version="0.1.0",
    lifespan=lifespan,
)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)


class ContactFormRequest(BaseModel):
    """Contact form submission request model."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Sender's name",
    )
    email: EmailStr = Field(
        ...,
        description="Sender's email address",
    )
    subject: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Email subject",
    )
    message: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Message content",
    )
    recaptcha_token: str = Field(
        ...,
        min_length=1,
        description="reCAPTCHA verification token",
    )
    honeypot: str = Field(
        default="",
        max_length=0,
        description="Honeypot field - must be empty",
    )


class ContactFormResponse(BaseModel):
    """Contact form submission response model."""

    success: bool
    message: str


@app.get("/")
async def root():
    """Root endpoint - health check."""
    return {
        "service": "PyConDE Contact Form API",
        "status": "operational",
        "version": "0.1.0",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post(
    f"{settings.api_prefix}/contact",
    response_model=ContactFormResponse,
    status_code=status.HTTP_200_OK,
)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def submit_contact_form(
    request: Request,
    form_data: ContactFormRequest,
) -> ContactFormResponse:
    """
    Submit contact form with reCAPTCHA verification.

    Rate limits:
    - {settings.rate_limit_per_minute} requests per minute per IP
    - {settings.rate_limit_per_hour} requests per hour per IP

    Args:
        request: FastAPI request object
        form_data: Contact form data including reCAPTCHA token

    Returns:
        ContactFormResponse: Success status and message

    Raises:
        HTTPException: On validation or processing errors
    """
    client_ip = get_remote_address(request)
    logger.info(f"Contact form submission from {client_ip}")

    # Check honeypot field (should be empty)
    if form_data.honeypot:
        logger.warning(f"Honeypot triggered from {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid form submission",
        )

    # Verify reCAPTCHA
    try:
        await verify_recaptcha(form_data.recaptcha_token, client_ip)
        logger.info(f"reCAPTCHA verified for {client_ip}")
    except RecaptchaVerificationError as e:
        logger.warning(f"reCAPTCHA verification failed for {client_ip}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="reCAPTCHA verification failed. Please try again.",
        ) from e

    # Send email
    try:
        await send_contact_email(
            name=form_data.name,
            email=form_data.email,
            subject=form_data.subject,
            message=form_data.message,
        )
        logger.info(
            f"Contact email sent successfully from {form_data.email} ({client_ip})"
        )
    except EmailServiceError as e:
        logger.error(f"Failed to send email from {client_ip}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send message. Please try again later.",
        ) from e

    return ContactFormResponse(
        success=True,
        message="Thank you for your message! We'll get back to you soon.",
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with consistent JSON response."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "An unexpected error occurred. Please try again later.",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )

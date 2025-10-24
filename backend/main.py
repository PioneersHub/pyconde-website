"""FastAPI application for PyConDE contact form backend."""

import logging
from contextlib import asynccontextmanager

from config import settings
from email_service import EmailServiceError, send_contact_email
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from recaptcha import RecaptchaVerificationError, verify_recaptcha
from starlette.middleware.base import BaseHTTPMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Minimal startup - Lambda manages lifecycle
    yield
    # Cleanup if needed (currently none required)


# Initialize FastAPI app
# Security: Disable interactive docs in production to prevent exposure
app = FastAPI(
    title="PyConDE Contact Form API",
    description="Backend API for PyConDE website contact form with reCAPTCHA protection",
    version="0.1.0",
    lifespan=lifespan,
    # Disable docs in production (only available when DEBUG=True)
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)


# Security: Optional API Key Middleware
class APIKeyMiddleware(BaseHTTPMiddleware):
    """Middleware to validate API key if configured."""

    async def dispatch(self, request: Request, call_next):
        """Validate API key header if api_key is configured."""
        # Skip validation if no API key is configured
        if settings.api_key is None:
            return await call_next(request)

        # Skip validation for health check and OPTIONS requests
        if request.url.path == "/health" or request.method == "OPTIONS":
            return await call_next(request)

        # Validate API key
        api_key = request.headers.get("X-API-Key")
        if api_key != settings.api_key:
            logger.warning(
                "Invalid or missing API key from %s",
                request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "success": False,
                    "message": "Invalid or missing API key",
                },
            )

        return await call_next(request)


# Add security middleware
app.add_middleware(APIKeyMiddleware)

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
async def submit_contact_form(
    request: Request,
    form_data: ContactFormRequest,
) -> ContactFormResponse:
    """
    Submit contact form with reCAPTCHA verification.

    Args:
        request: FastAPI request object
        form_data: Contact form data including reCAPTCHA token

    Returns:
        ContactFormResponse: Success status and message

    Raises:
        HTTPException: On validation or processing errors
    """
    client_ip = request.client.host if request.client else "unknown"
    logger.info("Contact form submission from %s", client_ip)

    # Check honeypot field (should be empty)
    if form_data.honeypot:
        logger.warning("Honeypot triggered from %s", client_ip)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid form submission",
        )

    # Verify reCAPTCHA
    try:
        await verify_recaptcha(form_data.recaptcha_token, client_ip)
        logger.info("reCAPTCHA verified for %s", client_ip)
    except RecaptchaVerificationError as e:
        logger.warning("reCAPTCHA verification failed for %s: %s", client_ip, e)
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
            "Contact email sent successfully from %s (%s)", form_data.email, client_ip
        )
    except EmailServiceError as e:
        logger.error("Failed to send email from %s: %s", client_ip, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send message. Please try again later.",
        ) from e

    return ContactFormResponse(
        success=True,
        message="Thank you for your message! We'll get back to you soon.",
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    """Handle HTTP exceptions with consistent JSON response."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(_request: Request, exc: Exception):
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

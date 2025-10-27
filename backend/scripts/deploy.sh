#!/usr/bin/env bash
# PyConDE Contact Form API - Automated Deployment Script
# =======================================================
# This script automates the SAM deployment process by loading parameters from .env
# and deploying to AWS Lambda with minimal user interaction.
#
# Usage:
#   ./scripts/deploy.sh [basic|secure]
#
# Examples:
#   ./scripts/deploy.sh secure    # Deploy with template-secure.yaml (recommended)
#   ./scripts/deploy.sh basic     # Deploy with template.yaml
#
# Requirements:
#   - AWS CLI configured with valid credentials
#   - AWS SAM CLI installed
#   - .env file with all required parameters

set -e  # Exit on any error

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
error() {
    echo -e "${RED}✗ Error: $1${NC}" >&2
    exit 1
}

success() {
    echo -e "${GREEN}✓ $1${NC}"
}

info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Check if we're in the backend directory
if [[ ! -f "template.yaml" ]] && [[ ! -f "template-secure.yaml" ]]; then
    error "This script must be run from the backend directory"
fi

# Parse deployment mode
DEPLOY_MODE="${1:-secure}"
if [[ "$DEPLOY_MODE" != "basic" ]] && [[ "$DEPLOY_MODE" != "secure" ]]; then
    error "Invalid deployment mode. Use 'basic' or 'secure'"
fi

# Set template file based on mode
if [[ "$DEPLOY_MODE" == "secure" ]]; then
    TEMPLATE_FILE="template-secure.yaml"
    CONFIG_ENV="secure"
    info "Deploying SECURE configuration (API Gateway + WAF + Rate Limiting)"
else
    TEMPLATE_FILE="template.yaml"
    CONFIG_ENV="default"
    info "Deploying BASIC configuration (Lambda Function URL only)"
fi

# Check for required tools
command -v sam >/dev/null 2>&1 || error "AWS SAM CLI not found. Install with: brew install aws-sam-cli"
command -v aws >/dev/null 2>&1 || error "AWS CLI not found. Install with: brew install awscli"

# Check AWS credentials
aws sts get-caller-identity >/dev/null 2>&1 || error "AWS credentials not configured. Run: aws configure"

# Load .env file
if [[ ! -f ".env" ]]; then
    error ".env file not found. Copy .env.example and fill in your values"
fi

info "Loading environment variables from .env"
set -a  # Export all variables
source .env
set +a

# Validate required environment variables
REQUIRED_VARS=(
    "RECAPTCHA_SECRET_KEY"
    "MAILGUN_API_KEY"
    "MAILGUN_DOMAIN"
    "EMAIL_RECIPIENT"
    "EMAIL_SENDER"
    "ALLOWED_ORIGINS"
)

for var in "${REQUIRED_VARS[@]}"; do
    if [[ -z "${!var}" ]]; then
        error "Required environment variable $var is not set in .env"
    fi
done

success "All required environment variables are set"

# Build the SAM application
info "Building SAM application..."
sam build -t "$TEMPLATE_FILE" || error "SAM build failed"
success "Build completed"

# Prepare parameter overrides
PARAMS=(
    "RecaptchaSecretKey=${RECAPTCHA_SECRET_KEY}"
    "MailgunApiKey=${MAILGUN_API_KEY}"
    "MailgunDomain=${MAILGUN_DOMAIN}"
    "EmailRecipient=${EMAIL_RECIPIENT}"
    "EmailSender=${EMAIL_SENDER}"
    "AllowedOrigins=${ALLOWED_ORIGINS}"
)

# Add optional parameters
if [[ -n "${RECAPTCHA_SITE_KEY}" ]]; then
    PARAMS+=("RecaptchaSiteKey=${RECAPTCHA_SITE_KEY}")
fi

if [[ -n "${API_KEY}" ]]; then
    PARAMS+=("ApiKey=${API_KEY}")
    info "API Key authentication enabled"
fi

# Join parameters with space
PARAM_STRING=$(IFS=' '; echo "${PARAMS[*]}")

# Deploy
info "Deploying to AWS..."
info "Stack name: pyconde-contact-form"
info "Region: eu-central-1"
info "Template: $TEMPLATE_FILE"
echo ""

sam deploy \
    --config-file samconfig.toml \
    --config-env "$CONFIG_ENV" \
    --parameter-overrides "$PARAM_STRING" \
    --no-confirm-changeset \
    --no-fail-on-empty-changeset \
    || error "Deployment failed"

success "Deployment completed successfully!"
echo ""

# Get outputs
info "Retrieving deployment outputs..."
API_URL=$(aws cloudformation describe-stacks \
    --stack-name pyconde-contact-form \
    --query 'Stacks[0].Outputs[?OutputKey==`ContactFormApiUrl`].OutputValue' \
    --output text 2>/dev/null)

if [[ -n "$API_URL" ]]; then
    success "API URL: $API_URL"
    echo ""
    info "Update your frontend configuration with this URL:"
    echo "   content/contact/contents.lr -> api_endpoint: ${API_URL}/api/contact"
    echo ""
else
    warning "Could not retrieve API URL. Check AWS Console for outputs."
fi

# Show next steps
echo ""
info "Next steps:"
echo "  1. Test the API endpoint with curl or your frontend"
echo "  2. Monitor logs: sam logs --stack-name pyconde-contact-form --tail"
echo "  3. View metrics in AWS Console"
echo ""

if [[ "$DEPLOY_MODE" == "secure" ]]; then
    info "Security features enabled:"
    echo "  ✓ AWS WAF with DDoS, SQL injection, XSS protection"
    echo "  ✓ WAF rate limiting (100 req/5min per IP)"
    echo "  ✓ CloudWatch logging and metrics"
fi

success "Done! 🚀"

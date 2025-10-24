# PyConDE Contact Form Backend

FastAPI backend service for the PyConDE website contact form with Google reCAPTCHA protection and Mailgun email delivery.

## Features

- ✅ **reCAPTCHA v3 Integration**: Bot protection with Google reCAPTCHA
- ✅ **Serverless Ready**: Optimized for AWS Lambda deployment
- ✅ **Email Delivery**: Mailgun integration with HTML templates
- ✅ **Honeypot Protection**: Additional bot detection
- ✅ **CORS Support**: Configured for PyConDE domains
- ✅ **Input Validation**: Comprehensive validation with Pydantic
- ✅ **Logging**: Structured logging for monitoring
- ✅ **Auto-scaling**: Built-in redundancy via serverless architecture

## Prerequisites

- Python 3.11+
- Mailgun account (you already have one!)
- Google reCAPTCHA account

## Setup

### 1. Install Dependencies

**Option A: Using uv with pyproject.toml (recommended)**

From the project root:

```bash
# Install all dependencies including backend
uv pip install -e ".[backend]"

# Or sync everything
uv sync --extra backend
```

**Option B: Backend-only installation**

For backend-only development or deployment:

```bash
cd backend
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

**Option C: Using pip**

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and set the following variables:

```env
# reCAPTCHA Configuration
RECAPTCHA_SECRET_KEY=your_recaptcha_secret_key

# Email Configuration
EMAIL_RECIPIENT=info26@pycon.de
EMAIL_SENDER=noreply@pycon.de

# Mailgun Configuration
MAILGUN_API_KEY=your_mailgun_api_key
MAILGUN_DOMAIN=your_mailgun_domain.com
MAILGUN_API_BASE_URL=https://api.mailgun.net/v3

# CORS Configuration
ALLOWED_ORIGINS=https://2026.pycon.de,https://pycon.de,http://localhost:5001

# Debug Mode
DEBUG=False

# Note: Rate limiting removed for serverless deployment
```

### 3. Configure Google reCAPTCHA

1. Go to [Google reCAPTCHA Admin](https://www.google.com/recaptcha/admin)
2. Create a new site with reCAPTCHA v3
3. Add your domains:
   - `2026.pycon.de`
   - `pycon.de`
   - `localhost` (for testing)
4. Copy the **Site Key** (for frontend) and **Secret Key** (for backend)
5. Update `RECAPTCHA_SECRET_KEY` in `.env`
6. Update `recaptcha_site_key` in `content/contact/contents.lr`

### 4. Configure Mailgun

1. **Get your Mailgun credentials** from your dashboard:
   - Go to [Mailgun Dashboard](https://app.mailgun.com/)
   - Navigate to "Sending" → "Domains"
   - Select your domain
   - Copy your **API Key** (looks like: `key-xxxxxxxxxxxxxxxxxxxxxxxxxx`)
   - Copy your **Domain name** (e.g., `mg.yourdomain.com`)

2. **Verify your sending domain** (if not already done):
   - Mailgun requires domain verification with DNS records
   - Follow Mailgun's instructions to add DNS records (SPF, DKIM)
   - This is usually already done for your account

3. **Choose your region**:
   - **US region**: Use `https://api.mailgun.net/v3` (default)
   - **EU region**: Use `https://api.eu.mailgun.net/v3` (for GDPR compliance)
   - Set `MAILGUN_API_BASE_URL` in `.env` accordingly

4. **Set credentials in `.env`**:

   ```env
   MAILGUN_API_KEY=key-your-actual-api-key-here
   MAILGUN_DOMAIN=mg.yourdomain.com
   MAILGUN_API_BASE_URL=https://api.mailgun.net/v3
   ```

5. **Configure sender email**:
   - Ensure `EMAIL_SENDER` uses your verified Mailgun domain
   - Example: `noreply@mg.yourdomain.com` or `noreply@pycon.de` (if domain is verified)

## Running Locally

### Development Server

**From the backend directory:**

```bash
cd backend

# Option 1: Using uv run (recommended)
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Option 2: After activating venv
source .venv/bin/activate  # or venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Option 3: Direct uvicorn
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Note:** The backend uses relative imports, so it must be run from the `backend/` directory.

The API will be available at:

- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

### Run Frontend (Lektor)

In a separate terminal:

```bash
make run
```

The website will be available at http://localhost:5001

## API Endpoints

### `POST /api/contact`

Submit a contact form message.

**Request Body:**

```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "subject": "Question about PyConDE",
  "message": "I have a question...",
  "recaptcha_token": "03AGdBq...",
  "honeypot": ""
}
```

**Response (Success):**

```json
{
  "success": true,
  "message": "Thank you for your message! We'll get back to you soon."
}
```

**Response (Error):**

```json
{
  "success": false,
  "message": "reCAPTCHA verification failed. Please try again."
}
```

### `GET /health`

Health check endpoint.

**Response:**

```json
{
  "status": "healthy"
}
```

## Deployment

### AWS Lambda (Recommended for Serverless)

**See [DEPLOY.md](DEPLOY.md) for comprehensive deployment guide.**

Quick start:

```bash
# Install AWS SAM CLI
brew install aws-sam-cli  # macOS

# Deploy
sam build
sam deploy --guided
```

**Advantages:**

- ✅ Fully serverless (no server management)
- ✅ Auto-scaling and redundancy built-in
- ✅ Pay-per-request pricing (~$0-5/month)
- ✅ Multi-AZ by default
- ✅ No rate limiting complexity

**Files for Lambda deployment:**

- `lambda_handler.py` - Lambda entry point with Mangum
- `template.yaml` - AWS SAM infrastructure as code
- `DEPLOY.md` - Full deployment instructions

### Environment Variables in Production

For AWS Lambda, configure via SAM template parameters:

- `RECAPTCHA_SECRET_KEY`
- `MAILGUN_API_KEY`
- `MAILGUN_DOMAIN`
- `EMAIL_RECIPIENT`
- `EMAIL_SENDER`
- `ALLOWED_ORIGINS`
- `DEBUG=False`

## Testing

### Manual Testing

1. Start the backend:

   ```bash
   uvicorn main:app --reload
   ```

2. Start the frontend:

   ```bash
   make run
   ```

3. Navigate to http://localhost:5001/contact
4. Fill out and submit the form
5. Check email delivery at info26@pycon.de

### API Testing with curl

```bash
curl -X POST http://localhost:8000/api/contact \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test User",
    "email": "test@example.com",
    "subject": "Test Subject",
    "message": "This is a test message with at least 10 characters.",
    "recaptcha_token": "test_token",
    "honeypot": ""
  }'
```

## Security Considerations

1. **reCAPTCHA v3**: Protects against automated bots
2. **Honeypot**: Hidden field that bots fill but humans don't
3. **Input Validation**: Pydantic models validate all inputs
4. **CORS**: Restricted to PyConDE domains
5. **HTTPS**: Lambda Function URLs enforce TLS
6. **Environment Variables**: No secrets in code
7. **Serverless Security**: Isolated execution environments per request

## Monitoring

### Logs

- Application logs are written to stdout
- AWS Lambda: CloudWatch Logs
- ECS: CloudWatch Logs with log driver

### Metrics to Monitor

- Request count
- Error rate
- Response time
- Rate limit hits
- Email delivery success/failure

## Troubleshooting

### Common Issues

**Issue: reCAPTCHA verification fails**

- Check that `RECAPTCHA_SECRET_KEY` is correct
- Verify domain is added in reCAPTCHA admin
- Check network connectivity to Google API

**Issue: Email not sending**

- Verify `MAILGUN_API_KEY` is correct (starts with `key-`)
- Check that `MAILGUN_DOMAIN` matches your verified domain
- Ensure sender email domain is verified in Mailgun
- Check Mailgun dashboard logs for delivery status
- Verify API base URL matches your region (US/EU)
- Check application logs for error details

**Issue: CORS errors**

- Verify frontend domain is in `ALLOWED_ORIGINS`
- Check Lambda Function URL CORS configuration in template.yaml
- Ensure preflight OPTIONS requests are allowed

## License

MIT License - See main project LICENSE file

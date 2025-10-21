# PyConDE Contact Form Backend

FastAPI backend service for the PyConDE website contact form with Google reCAPTCHA protection and AWS SES email delivery.

## Features

- ✅ **reCAPTCHA v2 Integration**: Bot protection with Google reCAPTCHA
- ✅ **Rate Limiting**: 5 requests/minute, 20 requests/hour per IP
- ✅ **Email Delivery**: AWS SES integration with HTML templates
- ✅ **Honeypot Protection**: Additional bot detection
- ✅ **CORS Support**: Configured for PyConDE domains
- ✅ **Input Validation**: Comprehensive validation with Pydantic
- ✅ **Logging**: Structured logging for monitoring

## Prerequisites

- Python 3.11+
- AWS Account with SES configured
- Google reCAPTCHA account

## Setup

### 1. Install Dependencies

Using uv (recommended):
```bash
cd backend
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

Using pip:
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

# AWS Configuration
AWS_REGION=eu-central-1
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key

# CORS Configuration
ALLOWED_ORIGINS=https://2026.pycon.de,https://pycon.de,http://localhost:5001

# Rate Limiting
RATE_LIMIT_PER_MINUTE=5
RATE_LIMIT_PER_HOUR=20

# Debug Mode
DEBUG=False
```

### 3. Configure Google reCAPTCHA

1. Go to [Google reCAPTCHA Admin](https://www.google.com/recaptcha/admin)
2. Create a new site with reCAPTCHA v2 ("I'm not a robot" Checkbox)
3. Add your domains:
   - `2026.pycon.de`
   - `pycon.de`
   - `localhost` (for testing)
4. Copy the **Site Key** (for frontend) and **Secret Key** (for backend)
5. Update `RECAPTCHA_SECRET_KEY` in `.env`
6. Update `recaptcha_site_key` in `content/contact/contents.lr`

### 4. Configure AWS SES

1. Verify the sender email address in AWS SES:
   - Go to AWS SES Console
   - Navigate to "Verified identities"
   - Add and verify `noreply@pycon.de`

2. Verify the recipient email address (if in sandbox):
   - Verify `info26@pycon.de`
   - Or request production access to send to any email

3. Configure AWS credentials:
   - Use existing GitHub secrets or
   - Create IAM user with `ses:SendEmail` permission
   - Set credentials in `.env`

## Running Locally

### Development Server

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

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

### Option 1: AWS Lambda with API Gateway (Recommended)

**Advantages:**
- Serverless (no server management)
- Auto-scaling
- Pay-per-request pricing
- ~$0-5/month for typical usage

**Setup:**

1. Install deployment dependencies:
   ```bash
   pip install mangum
   ```

2. Create Lambda deployment package:
   ```bash
   cd backend
   pip install -r requirements.txt -t ./package
   cp *.py ./package/
   cd package
   zip -r ../deployment.zip .
   ```

3. Deploy to AWS Lambda:
   - Create Lambda function with Python 3.11 runtime
   - Upload `deployment.zip`
   - Set handler to `main.handler` (using Mangum adapter)
   - Configure environment variables
   - Create API Gateway trigger
   - Update frontend `api_endpoint` with API Gateway URL

### Option 2: AWS ECS/Fargate

**Advantages:**
- Better performance (no cold starts)
- Full control over runtime
- Container-based deployment

**Setup:**

1. Create Dockerfile:
   ```dockerfile
   FROM python:3.11-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   COPY . .
   CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
   ```

2. Build and push to ECR
3. Deploy to ECS Fargate
4. Configure Application Load Balancer

### Environment Variables in Production

Set these in Lambda/ECS configuration:
- `RECAPTCHA_SECRET_KEY`
- `AWS_REGION`
- `EMAIL_RECIPIENT`
- `EMAIL_SENDER`
- `ALLOWED_ORIGINS`
- `RATE_LIMIT_PER_MINUTE`
- `RATE_LIMIT_PER_HOUR`
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

1. **reCAPTCHA**: Protects against automated bots
2. **Honeypot**: Hidden field that bots fill but humans don't
3. **Rate Limiting**: Prevents abuse (5 req/min per IP)
4. **Input Validation**: Pydantic models validate all inputs
5. **CORS**: Restricted to PyConDE domains
6. **HTTPS**: API Gateway/ALB enforce TLS
7. **Environment Variables**: No secrets in code

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
- Verify SES sender email is verified
- Check AWS credentials have `ses:SendEmail` permission
- Verify SES is out of sandbox mode
- Check CloudWatch logs for error details

**Issue: CORS errors**
- Verify frontend domain is in `ALLOWED_ORIGINS`
- Check API Gateway CORS configuration
- Ensure preflight OPTIONS requests are allowed

**Issue: Rate limit errors**
- Check if IP is being blocked
- Adjust `RATE_LIMIT_PER_MINUTE` if needed
- Review rate limit logs

## License

MIT License - See main project LICENSE file

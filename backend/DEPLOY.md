# PyConDE Contact Form API - Deployment Guide

Deploy the contact form API to AWS Lambda for redundant, serverless operation.

> **🔒 Security:** See [SECURITY.md](SECURITY.md) for comprehensive security documentation

## Quick Start

### Prerequisites

- AWS CLI configured with credentials
- AWS SAM CLI installed: `brew install aws-sam-cli`
- Python 3.11+
- Google reCAPTCHA credentials
- Mailgun API key and domain

### Choose Deployment Mode

**Option 1: Basic** (`template.yaml`)

- Simple Lambda Function URL
- Cost: ~$0-2/month
- No WAF or API Gateway throttling
- Use for: Development, low-traffic

**Option 2: Secure** (`template-secure.yaml`) ⭐ **Recommended**

- API Gateway + AWS WAF
- DDoS, SQL injection, XSS protection
- Rate limiting: 10 req/min (configurable)
- Cost: ~$5-10/month
- Use for: Production, public sites

## Deploy

### Basic Deployment

```bash
cd backend
sam build -t template.yaml
sam deploy --guided --template-file template.yaml
```

### Secure Deployment ⭐

```bash
cd backend
sam build -t template-secure.yaml
sam deploy --guided --template-file template-secure.yaml
```

**Parameters you'll be prompted for:**

- Stack name (e.g., `pyconde-contact-form`)
- AWS region (e.g., `eu-central-1`)
- `RecaptchaSecretKey` - Your reCAPTCHA secret
- `MailgunApiKey` - Your Mailgun API key
- `MailgunDomain` - Your domain (e.g., `mg.pycon.de`)
- `EmailRecipient` - Recipient email (e.g., `info26@pycon.de`)
- `EmailSender` - Sender email (e.g., `noreply@pycon.de`)
- `AllowedOrigins` - CORS origins (comma-separated)
- `ApiKey` - **(Secure only)** Optional API key for extra security
- `RateLimitPerMinute` - **(Secure only)** Default: 10
- `BurstLimit` - **(Secure only)** Default: 20

### Subsequent Deploys

```bash
cd backend
sam build && sam deploy
```

## Post-Deployment

### Get API URL

```bash
aws cloudformation describe-stacks \
  --stack-name pyconde-contact-form \
  --query 'Stacks[0].Outputs[?OutputKey==`ContactFormApiUrl`].OutputValue' \
  --output text
```

### Update Frontend

Use the API URL in your frontend:

```javascript
// Basic: Function URL
const API_URL = 'https://abc123.lambda-url.eu-central-1.on.aws/api/contact';

// Secure: API Gateway URL
const API_URL = 'https://abc123.execute-api.eu-central-1.amazonaws.com/prod/api/contact';
```

If using API key:

```javascript
fetch(API_URL, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'your_api_key_here'  // Add if API_KEY is set
  },
  body: JSON.stringify(formData)
});
```

## Local Development

```bash
cd backend
cp .env.example .env
# Edit .env with your credentials

# Run locally
uv run uvicorn main:app --reload --port 8000

# Access docs (only works when DEBUG=True)
open http://localhost:8000/docs
```

## Security Features

✅ **FastAPI docs disabled** in production (`DEBUG=False`)
✅ **Optional API key** authentication (`API_KEY` env var)
✅ **AWS WAF** protection (secure template only)
✅ **API Gateway throttling** (secure template only)
✅ **reCAPTCHA v3** verification
✅ **Honeypot** detection
✅ **CORS** validation
✅ **Input validation** (Pydantic)

See [SECURITY.md](SECURITY.md) for complete security documentation.

## Monitoring

```bash
# View logs in real-time
sam logs --stack-name pyconde-contact-form --tail

# View recent logs
sam logs --stack-name pyconde-contact-form --start-time '10min ago'
```

View metrics in AWS Console:

- Lambda: Functions → pyconde-contact-form-api → Monitor
- API Gateway (secure): APIs → pyconde-contact-form-api → Dashboard
- WAF (secure): WAF & Shield → Web ACLs → pyconde-contact-form-waf

## Updating

```bash
# Make code changes, then:
cd backend
sam build && sam deploy
```

## Troubleshooting

**Docs not accessible:**

- Ensure `DEBUG=True` in .env for local development
- In production (Lambda), docs are intentionally disabled for security

**CORS errors:**

- Check `ALLOWED_ORIGINS` matches your frontend domain
- Verify CORS config in template matches FastAPI middleware

**API key errors (403 Forbidden):**

- Ensure frontend includes `X-API-Key` header if `API_KEY` is set
- To disable: Set `API_KEY=` (empty) or leave blank in SAM parameters

**Rate limiting:**

- Basic template: No rate limiting (rely on reCAPTCHA)
- Secure template: 10 req/min per IP (adjust in template parameters)

## Cost Estimate

**Basic deployment:**

- Lambda: $0-1/month (1M requests free tier)
- Total: ~$0-2/month

**Secure deployment:**

- Lambda: $0-1/month
- API Gateway: $0-2/month ($3.50 per million requests)
- WAF: $5-7/month ($5 base + $1 per rule + $0.60 per million requests)
- Total: ~$5-10/month

Plus Mailgun costs (separate).

## Cleanup

```bash
sam delete --stack-name pyconde-contact-form
```

## Support

- [SECURITY.md](SECURITY.md) - Security documentation
- [AWS SAM Docs](https://docs.aws.amazon.com/serverless-application-model/)
- [FastAPI Docs](https://fastapi.tiangolo.com/)

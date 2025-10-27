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
- No WAF
- Use for: Development, low-traffic

**Option 2: Secure** (`template-secure.yaml`) ⭐ **Recommended**

- API Gateway + AWS WAF
- DDoS, SQL injection, XSS protection
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

### Authentication Question

During deployment, you'll see:

```
ContactFormFunction has no authentication. Is this okay? [y/N]:
```

**Answer: Yes (y)** - This is correct and intentional.

**Why?** This is a public contact form that must be accessible to website visitors without login. Security is handled through multiple layers:

- ✅ **reCAPTCHA v3** - Google bot protection validates every request
- ✅ **CORS restrictions** - Only allows requests from `2026.pycon.de` and `pycon.de`
- ✅ **Honeypot field** - Additional bot detection
- ✅ **Input validation** - Pydantic models validate all data
- ✅ **Optional API key** - Application-level auth available if needed (via `ApiKey` parameter)
- ✅ **WAF protection** - (Secure template only) DDoS, SQL injection, XSS protection

AWS authentication (IAM/Cognito) would block public access, which is not desired for a contact form. The current security model follows best practices for public-facing form APIs.

### Using samconfig.toml (Preset Configuration)

To avoid entering parameters manually every time, use the included `samconfig.toml`:

```bash
cd backend

# Build
sam build -t template-secure.yaml

# Load all Variables from .env file
export $(grep -v '^#' .env | xargs)

# Deploy with preset configuration (still need to provide secrets)
sam deploy --config-file samconfig.toml --config-env secure \
  --parameter-overrides \
    RecaptchaSecretKey=$RECAPTCHA_SECRET_KEY \
    MailgunApiKey=$MAILGUN_API_KEY \
    ApiKey=$API_KEY  # Optional
```

The `samconfig.toml` file presets:
- Stack name (without spaces!)
- AWS region
- Non-sensitive parameters (site key, emails, domains)
- Deployment preferences

**Note:** Stack name must be `pyconde-contact-form` (no trailing spaces or special characters).

### Automated Deployment with deploy.sh

For fully automated deployment, use the included script:

```bash
cd backend

# Ensure .env file is configured with all values
cp .env.example .env
# Edit .env with your actual credentials

# Deploy secure configuration (recommended)
./scripts/deploy.sh secure

# Or deploy basic configuration
./scripts/deploy.sh basic
```

The script will:
1. Load all parameters from `.env`
2. Validate required variables
3. Build the SAM application
4. Deploy non-interactively
5. Display the API URL and next steps

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

**IAM permissions error:**

```
User: arn:aws:iam::xxx:user/xxx is not authorized to perform: iam:CreateRole
```

CloudFormation needs IAM permissions to create the Lambda execution role. Solutions:

1. **Grant IAM permissions** (recommended): Have your AWS administrator attach this policy to your user:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [{
       "Effect": "Allow",
       "Action": [
         "iam:CreateRole", "iam:DeleteRole", "iam:PutRolePolicy",
         "iam:DeleteRolePolicy", "iam:AttachRolePolicy", "iam:DetachRolePolicy",
         "iam:GetRole", "iam:GetRolePolicy", "iam:PassRole",
         "iam:TagRole", "iam:UntagRole"
       ],
       "Resource": "arn:aws:iam::*:role/pyconde-contact-form-*"
     }]
   }
   ```

2. **Use different AWS profile**: Switch to a user with admin/IAM permissions:
   ```bash
   export AWS_PROFILE=admin
   sam deploy --config-file samconfig.toml --config-env secure ...
   ```

3. **Clean up failed stack** before retrying:
   ```bash
   aws cloudformation delete-stack --stack-name pyconde-contact-form
   ```

**Stack name validation error:**

```
Error: ValidationError - Value 'pyconde-contact-form -e1bfcfb0-CompanionStack' at 'stackName' failed to satisfy constraint
```

- Check for **trailing spaces** in your stack name
- Stack name must match pattern: `[a-zA-Z][-a-zA-Z0-9]*`
- Use `pyconde-contact-form` exactly (no spaces, no special characters)
- Solution: Use `samconfig.toml` or `deploy.sh` script to avoid typos

**Docs not accessible:**

- Ensure `DEBUG=True` in .env for local development
- In production (Lambda), docs are intentionally disabled for security

**CORS errors:**

- Check `ALLOWED_ORIGINS` matches your frontend domain
- Verify CORS config in template matches FastAPI middleware

**API key errors (403 Forbidden):**

- Ensure frontend includes `X-API-Key` header if `API_KEY` is set
- To disable: Set `API_KEY=` (empty) or leave blank in SAM parameters

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

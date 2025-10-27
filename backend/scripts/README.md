# Deployment Scripts

## deploy.sh

Automated deployment script for AWS Lambda.

### Usage

```bash
# Deploy secure configuration (recommended)
./scripts/deploy.sh secure

# Deploy basic configuration
./scripts/deploy.sh basic
```

### Requirements

- AWS CLI configured with valid credentials
- AWS SAM CLI installed
- `.env` file with all required parameters

### What it does

1. Validates required tools (aws, sam)
2. Loads environment variables from `.env`
3. Validates all required variables are set
4. Builds the SAM application
5. Deploys to AWS with parameters from `.env`
6. Displays API URL and next steps

### Parameters loaded from .env

- `RECAPTCHA_SECRET_KEY`
- `RECAPTCHA_SITE_KEY`
- `MAILGUN_API_KEY`
- `MAILGUN_DOMAIN`
- `EMAIL_RECIPIENT`
- `EMAIL_SENDER`
- `ALLOWED_ORIGINS`
- `API_KEY` (optional)
- `RATE_LIMIT_PER_MINUTE` (secure only)
- `BURST_LIMIT` (secure only)

See [DEPLOY.md](../DEPLOY.md) for more details.

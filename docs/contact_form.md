# Contact Form

The PyConDE website includes a secure contact form with bot protection and email delivery.

## Architecture

- **Frontend**: Lektor page with HTML5 form and JavaScript validation
- **Backend**: FastAPI REST API deployed on AWS Lambda
- **Email**: Mailgun API integration
- **Security**: reCAPTCHA v3, honeypot, API key authentication, AWS WAF

## Local Development

### Start Backend

```bash
cd backend
cp .env.example .env
# Edit .env with your credentials

# Run backend
uv run uvicorn main:app --reload --port 8000
```

Backend available at http://localhost:8000

### Start Frontend

```bash
make run
```

Contact form available at http://localhost:5001/contact

### Test Locally

1. Navigate to http://localhost:5001/contact
2. Fill out form and complete reCAPTCHA
3. Submit and verify email delivery to info26@pycon.de

## Configuration

### Google reCAPTCHA

1. Register at https://www.google.com/recaptcha/admin
2. Create reCAPTCHA v3 site for domains:
   - `2026.pycon.de`
   - `pycon.de`
   - `localhost` (testing)
3. Configure credentials:
   - Backend: Set `RECAPTCHA_SECRET_KEY` in `backend/.env`
   - Frontend: Update `recaptcha_site_key` in `content/contact/contents.lr`

### Mailgun

Configure in `backend/.env`:

```env
MAILGUN_API_KEY=key-your-api-key
MAILGUN_DOMAIN=mg.yourdomain.com
MAILGUN_API_BASE_URL=https://api.eu.mailgun.net/v3
EMAIL_RECIPIENT=info26@pycon.de
EMAIL_SENDER=noreply@pycon.de
```

### Frontend

Update `content/contact/contents.lr`:

```
api_endpoint: https://your-api-gateway-url/prod/api/contact
recaptcha_site_key: your_site_key_here
```

## Deployment

See `backend/DEPLOY.md` for complete deployment instructions.

### Quick Deploy

Choose deployment mode:

**Basic** (Function URL):

```bash
cd backend
sam build -t template.yaml
sam deploy --guided --template-file template.yaml
```

**Secure** (API Gateway + WAF) - Recommended for production:

```bash
cd backend
sam build -t template-secure.yaml
sam deploy --guided --template-file template-secure.yaml
```

After deployment, update frontend `api_endpoint` with the output URL.

## Security Features

- **FastAPI docs disabled** in production (DEBUG=False)
- **Optional API key** authentication
- **AWS WAF** protection against DDoS, SQL injection, XSS (secure template)
- **API Gateway throttling** (10 req/min default)
- **reCAPTCHA v3** verification
- **Honeypot** field for bot detection
- **CORS** validation
- **Input validation** with Pydantic

See `backend/SECURITY.md` for comprehensive security documentation.

## Monitoring

View logs:

```bash
sam logs --stack-name pyconde-contact-form --tail
```

View metrics in AWS Console:

- Lambda: Functions → pyconde-contact-form-api
- API Gateway: APIs → pyconde-contact-form-api
- WAF: Web ACLs → pyconde-contact-form-waf

## Troubleshooting

**Docs not accessible locally:**

- Ensure `DEBUG=True` in `backend/.env`

**CORS errors:**

- Verify `ALLOWED_ORIGINS` in `backend/.env` matches frontend domain

**API key errors (403):**

- Include `X-API-Key` header in frontend requests if `API_KEY` is set

**Rate limiting:**

- Basic: No rate limiting
- Secure: 10 req/min (configurable in template parameters)

## File Structure

```
pyconde-website/
├── backend/
│   ├── main.py                    # FastAPI application
│   ├── lambda_handler.py          # AWS Lambda handler
│   ├── config.py                  # Configuration
│   ├── recaptcha.py               # reCAPTCHA verification
│   ├── email_service.py           # Mailgun integration
│   ├── template.yaml              # Basic SAM template
│   ├── template-secure.yaml       # Production SAM template
│   ├── DEPLOY.md                  # Deployment guide
│   └── SECURITY.md                # Security documentation
├── content/contact/
│   └── contents.lr                # Contact page content
├── templates/
│   └── contact-form.html          # Form template
└── assets/static/
    ├── css/custom.css             # Form styles
    └── js/contact-form.js         # Form handling
```

## Cost Estimate

**Basic deployment:**

- Lambda: $0-1/month
- Total: ~$0-2/month

**Secure deployment:**

- Lambda: $0-1/month
- API Gateway: $0-2/month
- WAF: $5-7/month
- Total: ~$5-10/month

Plus Mailgun costs (separate).

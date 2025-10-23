# Contact Form Implementation Summary

## Overview

Successfully implemented a secure contact form for the PyConDE website with:
- **FastAPI backend** with reCAPTCHA v2 protection
- **Mailgun** email delivery to info26@pycon.de
- **Bot protection** via reCAPTCHA, honeypot, and rate limiting
- **Responsive design** matching the existing PyConDE website style

**Latest Update:** Migrated from AWS SES to Mailgun for simpler setup and better developer experience.

## Implementation Details

### Backend (FastAPI)

**Location:** `/backend/`

**Components:**
1. **`main.py`** - FastAPI application with:
   - POST `/api/contact` endpoint
   - Rate limiting (5 req/min, 20 req/hour per IP)
   - CORS middleware for frontend integration
   - Comprehensive error handling
   - Health check endpoint

2. **`recaptcha.py`** - reCAPTCHA verification service:
   - Async HTTP client for Google's verification API
   - Score validation for v3 compatibility
   - Detailed error handling

3. **`email_service.py`** - Mailgun integration:
   - HTML and plain text email templates
   - PyConDE branding with color scheme
   - Reply-to sender's email address
   - Async HTTP client (httpx) for Mailgun API
   - Comprehensive error handling and logging

4. **`config.py`** - Configuration management:
   - Pydantic settings with environment variable loading
   - Type-safe configuration
   - Sensible defaults

### Frontend (Lektor + HTML/CSS/JS)

**Components:**

1. **Lektor Model** (`models/contact-form.ini`):
   - Defines page structure with API endpoint and reCAPTCHA site key

2. **Content** (`content/contact/contents.lr`):
   - Contact page content with intro text
   - Configurable API endpoint and reCAPTCHA key

3. **Template** (`templates/contact-form.html`):
   - Native HTML5 form with validation
   - Fields: name, email, subject, message
   - reCAPTCHA v2 widget integration
   - Honeypot field for bot detection
   - Success/error message containers

4. **JavaScript** (`assets/static/js/contact-form.js`):
   - Form validation (client-side)
   - Fetch API for form submission
   - reCAPTCHA callbacks
   - Character counter for message field
   - Loading states and error handling
   - Real-time validation feedback

5. **CSS** (`assets/static/css/custom.css`):
   - Form styling matching PyConDE design
   - Color scheme: blue (#3778be) and green (#00aa41)
   - Focus states with green accent
   - Responsive mobile design
   - Accessibility improvements

6. **Navigation** (`databags/links.yaml`):
   - Added "Contact" link after Newsletter

## Security Features

### Bot Protection
- ✅ **reCAPTCHA v2**: Google's "I'm not a robot" checkbox
- ✅ **Honeypot field**: Hidden field that bots fill
- ✅ **Rate limiting**: 5 requests/min, 20 requests/hour per IP
- ✅ **Input validation**: Pydantic models with strict types

### Data Security
- ✅ **HTTPS**: TLS encryption for all communications
- ✅ **CORS**: Restricted to PyConDE domains
- ✅ **Environment variables**: No secrets in code
- ✅ **AWS IAM**: Minimal permissions for SES

### Email Security
- ✅ **Reply-to**: Sender's email for direct replies
- ✅ **HTML escaping**: Prevents injection attacks
- ✅ **Sender verification**: AWS SES verified identities

## Configuration Required

### 1. Google reCAPTCHA Setup

1. Register at https://www.google.com/recaptcha/admin
2. Create reCAPTCHA v2 site with these domains:
   - `2026.pycon.de`
   - `pycon.de`
   - `localhost` (for testing)
3. Get **Site Key** and **Secret Key**
4. Update configuration:
   - **Backend**: Set `RECAPTCHA_SECRET_KEY` in `.env`
   - **Frontend**: Update `recaptcha_site_key` in `content/contact/contents.lr`

### 2. Mailgun Setup

Since you already have a Mailgun account, just gather your credentials:

1. **Get API credentials** from [Mailgun Dashboard](https://app.mailgun.com/):
   - Navigate to "Sending" → "Domains"
   - Select your domain
   - Copy **API Key** (starts with `key-`)
   - Copy **Domain name** (e.g., `mg.yourdomain.com`)

2. **Choose region**:
   - US: `https://api.mailgun.net/v3` (default)
   - EU: `https://api.eu.mailgun.net/v3` (for GDPR)

3. **Verify domain** (if not already done):
   - Ensure SPF and DKIM DNS records are configured
   - Check verification status in Mailgun dashboard

### 3. Backend Environment Variables

Create `/backend/.env` from `/backend/.env.example`:

```env
RECAPTCHA_SECRET_KEY=your_secret_key_here
EMAIL_RECIPIENT=info26@pycon.de
EMAIL_SENDER=noreply@pycon.de
MAILGUN_API_KEY=key-your-mailgun-api-key
MAILGUN_DOMAIN=mg.yourdomain.com
MAILGUN_API_BASE_URL=https://api.mailgun.net/v3
ALLOWED_ORIGINS=https://2026.pycon.de,https://pycon.de,http://localhost:5001
RATE_LIMIT_PER_MINUTE=5
RATE_LIMIT_PER_HOUR=20
DEBUG=False
```

### 4. Frontend Configuration

Update `content/contact/contents.lr`:

```
api_endpoint: https://your-api-gateway-url/api/contact
recaptcha_site_key: your_site_key_here
```

## Local Testing

### 1. Start Backend

```bash
# From project root - install backend dependencies
uv pip install -e ".[backend]"

# Configure environment
cd backend
cp .env.example .env
# Edit .env with your credentials

# Start backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend available at:
- API: http://localhost:8000
- Docs: http://localhost:8000/docs

### 2. Start Frontend

```bash
# In project root
make run
```

Website available at: http://localhost:5001

### 3. Test Form

1. Navigate to http://localhost:5001/contact
2. Fill out the form
3. Complete reCAPTCHA
4. Submit
5. Check email delivery at info26@pycon.de

## Deployment Options

### Option 1: AWS Lambda + API Gateway (Recommended)

**Advantages:**
- Serverless (no infrastructure management)
- Auto-scaling
- Pay-per-request (~$0-5/month)
- Fast deployment

**Steps:**
1. Install Mangum: `pip install mangum`
2. Add handler in `main.py`:
   ```python
   from mangum import Mangum
   handler = Mangum(app)
   ```
3. Create deployment package
4. Deploy to Lambda with Python 3.11 runtime
5. Create API Gateway trigger
6. Configure environment variables
7. Update frontend `api_endpoint`

See `backend/README.md` for detailed instructions.

### Option 2: AWS ECS Fargate

**Advantages:**
- No cold starts
- Better for high traffic
- Container-based

**Steps:**
1. Create Dockerfile
2. Build and push to ECR
3. Deploy to ECS Fargate
4. Configure ALB
5. Set environment variables

## File Structure

```
pyconde-website/
├── backend/                       # NEW
│   ├── __init__.py
│   ├── main.py                    # FastAPI application
│   ├── config.py                  # Configuration
│   ├── recaptcha.py               # reCAPTCHA service
│   ├── email_service.py           # AWS SES integration
│   ├── requirements.txt           # Backend dependencies
│   ├── .env.example               # Example environment file
│   ├── .gitignore                 # Python gitignore
│   └── README.md                  # Backend documentation
├── models/
│   └── contact-form.ini           # NEW: Lektor model
├── content/
│   └── contact/                   # NEW
│       └── contents.lr            # Contact page content
├── templates/
│   └── contact-form.html          # NEW: Form template
├── assets/static/
│   ├── css/
│   │   └── custom.css             # UPDATED: Form styles
│   └── js/
│       └── contact-form.js        # NEW: Form handling
└── databags/
    └── links.yaml                 # UPDATED: Navigation
```

## Git Commits

All changes committed in 9 commits on the `contact` branch:

1. `5b8185c` - Add backend configuration and reCAPTCHA verification
2. `90cad31` - Add AWS SES email service for contact form
3. `bbf828d` - Add FastAPI main application with contact form endpoint
4. `596128e` - Add Lektor model and content for contact form page
5. `2772c6a` - Add HTML template for contact form
6. `4674b11` - Add JavaScript for contact form submission handling
7. `e09023f` - Add CSS styling for contact form
8. `1218f10` - Add Contact link to navigation
9. `b6e5bb7` - Add backend documentation and .gitignore

## Next Steps

### Before Merging to Main:

1. **Configure reCAPTCHA**:
   - Register site at Google reCAPTCHA
   - Get site key and secret key
   - Update configuration files

2. **Configure AWS SES**:
   - Verify sender email (noreply@pycon.de)
   - Verify recipient or exit sandbox
   - Test email delivery

3. **Deploy Backend**:
   - Choose deployment option (Lambda recommended)
   - Deploy backend to AWS
   - Get API endpoint URL
   - Update frontend configuration

4. **Test End-to-End**:
   - Submit test form
   - Verify reCAPTCHA works
   - Confirm email delivery
   - Test rate limiting
   - Check error handling

5. **Update Documentation**:
   - Add deployment instructions to main README
   - Document monitoring and maintenance

### Production Checklist:

- [ ] reCAPTCHA configured for production domains
- [ ] AWS SES in production mode (not sandbox)
- [ ] Backend deployed to AWS Lambda/ECS
- [ ] Environment variables set in production
- [ ] Frontend updated with production API endpoint
- [ ] SSL/TLS certificate configured
- [ ] Monitoring and logging set up
- [ ] Rate limiting tested
- [ ] Error handling tested
- [ ] Email delivery tested
- [ ] Mobile responsiveness verified
- [ ] Accessibility tested

## Monitoring & Maintenance

### Logs to Monitor:
- Backend application logs (CloudWatch)
- API Gateway/ALB access logs
- Email delivery status (SES)
- Rate limit violations
- reCAPTCHA verification failures

### Metrics to Track:
- Form submission rate
- Email delivery success rate
- reCAPTCHA pass/fail rate
- API response times
- Error rates

### Maintenance Tasks:
- Review spam submissions monthly
- Update rate limits if needed
- Monitor AWS SES sending limits
- Review and update dependencies
- Check reCAPTCHA effectiveness

## Cost Estimate

**AWS Costs (Monthly):**
- Lambda: $0 (free tier: 1M requests)
- API Gateway: $0-3 (free tier: 1M requests)
- SES: $0.10 per 1,000 emails
- **Total: ~$0-5/month** for typical contact form usage

## Support

For issues or questions:
- Backend: See `backend/README.md`
- General: Contact PyConDE team
- reCAPTCHA: https://developers.google.com/recaptcha
- AWS SES: https://docs.aws.amazon.com/ses/

## License

Same as main project: MIT License

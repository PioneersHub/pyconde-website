# Mailgun Migration Summary

## Overview

Successfully migrated the contact form backend from AWS SES to Mailgun for simpler configuration and better developer experience.

## Why Mailgun?

✅ **You already have a paid account** - No new service signup needed
✅ **Simpler setup** - No AWS sandbox mode, no IAM permissions
✅ **Better developer experience** - Clean RESTful API, excellent docs
✅ **Better support** - Actual human support vs AWS ticket system
✅ **Email validation API** - Built-in email validation features
✅ **Better analytics** - Dashboard with delivery tracking
✅ **Regional support** - US and EU API endpoints for GDPR compliance

## What Changed

### Code Changes (3 files modified)

1. **`backend/config.py`**
   - Removed: `aws_region`, `aws_access_key_id`, `aws_secret_access_key`
   - Added: `mailgun_api_key`, `mailgun_domain`, `mailgun_api_base_url`

2. **`backend/email_service.py`**
   - Removed: `boto3` and `botocore` imports
   - Removed: `get_ses_client()` function
   - Updated: `send_contact_email()` to use Mailgun HTTP API via `httpx`
   - Kept: Same email templates (HTML and text) - no changes needed
   - Kept: Same function signature - maintains compatibility

3. **`backend/requirements.txt`**
   - Removed: `boto3>=1.37.0`
   - Kept: `httpx>=0.28.0` (already required for reCAPTCHA)

### Documentation Updates (3 files)

4. **`backend/.env.example`** - Updated with Mailgun configuration
5. **`backend/README.md`** - Replaced AWS SES instructions with Mailgun
6. **`CONTACT_FORM_IMPLEMENTATION.md`** - Updated all references

### No Frontend Changes

❌ No changes needed to:
- Templates
- JavaScript
- CSS
- Lektor models
- Frontend configuration

The API contract remains identical - frontend just calls the same endpoint.

## Migration Impact

### Before (AWS SES)
```python
# boto3 synchronous client
ses_client = boto3.client("ses", ...)
response = ses_client.send_email(
    Source=...,
    Destination={...},
    Message={...}
)
```

### After (Mailgun)
```python
# httpx async client (already in use for reCAPTCHA)
async with httpx.AsyncClient() as client:
    response = await client.post(
        f"{mailgun_url}/messages",
        auth=("api", mailgun_api_key),
        data={...}
    )
```

**Benefits:**
- Fully async (better performance)
- No new dependencies (httpx already used)
- Cleaner error handling
- Better response parsing

## Configuration Setup

### 1. Get Mailgun Credentials

From your [Mailgun Dashboard](https://app.mailgun.com/):

1. Navigate to **"Sending"** → **"Domains"**
2. Select your domain
3. Copy your **API Key** (starts with `key-`)
4. Copy your **Domain name** (e.g., `mg.yourdomain.com` or `pycon.de`)

### 2. Choose Region

**US Region** (default):
```env
MAILGUN_API_BASE_URL=https://api.mailgun.net/v3
```

**EU Region** (GDPR compliance):
```env
MAILGUN_API_BASE_URL=https://api.eu.mailgun.net/v3
```

### 3. Update Environment Variables

Create/update `backend/.env`:

```env
# Mailgun Configuration
MAILGUN_API_KEY=key-your-actual-mailgun-api-key-here
MAILGUN_DOMAIN=your-verified-domain.com
MAILGUN_API_BASE_URL=https://api.mailgun.net/v3

# Sender email must use verified domain
EMAIL_SENDER=noreply@your-verified-domain.com
EMAIL_RECIPIENT=info26@pycon.de
```

**Important:** The sender email domain must match your verified Mailgun domain.

## Testing the Migration

### 1. Install Dependencies

```bash
cd backend
uv pip install -r requirements.txt  # boto3 removed, httpx already there
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your Mailgun credentials
```

### 3. Start Backend

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Test Email Sending

**Option A: Via Frontend**
1. Start Lektor: `make run`
2. Visit: http://localhost:5001/contact
3. Submit test form
4. Check email at info26@pycon.de

**Option B: Via API Docs**
1. Open: http://localhost:8000/docs
2. Navigate to POST `/api/contact`
3. Click "Try it out"
4. Fill in test data
5. Execute

**Option C: Via curl**
```bash
curl -X POST http://localhost:8000/api/contact \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test User",
    "email": "test@example.com",
    "subject": "Testing Mailgun",
    "message": "This is a test message via Mailgun API",
    "recaptcha_token": "test_token",
    "honeypot": ""
  }'
```

### 5. Verify Delivery

Check the Mailgun dashboard:
1. Go to **"Sending"** → **"Logs"**
2. Look for your test email
3. Verify status is "Delivered"
4. Check info26@pycon.de inbox

## Troubleshooting

### Issue: 401 Unauthorized

**Cause:** Invalid API key

**Solution:**
- Verify `MAILGUN_API_KEY` starts with `key-`
- Copy key directly from Mailgun dashboard
- Ensure no extra spaces in `.env` file

### Issue: 404 Domain Not Found

**Cause:** Invalid or unverified domain

**Solution:**
- Check `MAILGUN_DOMAIN` matches exactly what's in dashboard
- Verify domain DNS records (SPF, DKIM)
- Ensure domain is in "Active" status

### Issue: Email Not Sending

**Cause:** Sender domain mismatch

**Solution:**
- Ensure `EMAIL_SENDER` uses your verified Mailgun domain
- Example: If domain is `mg.pycon.de`, use `noreply@mg.pycon.de`
- Check Mailgun logs for detailed error

### Issue: Wrong Region

**Cause:** Using EU domain with US API (or vice versa)

**Solution:**
- Check your domain's region in Mailgun dashboard
- US accounts: Use `https://api.mailgun.net/v3`
- EU accounts: Use `https://api.eu.mailgun.net/v3`

## Production Deployment

### Environment Variables to Set

In your production environment (Lambda/ECS/etc.):

```env
MAILGUN_API_KEY=key-your-production-api-key
MAILGUN_DOMAIN=your-production-domain.com
MAILGUN_API_BASE_URL=https://api.mailgun.net/v3
EMAIL_SENDER=noreply@your-production-domain.com
EMAIL_RECIPIENT=info26@pycon.de
RECAPTCHA_SECRET_KEY=your-recaptcha-secret
ALLOWED_ORIGINS=https://2026.pycon.de,https://pycon.de
RATE_LIMIT_PER_MINUTE=5
RATE_LIMIT_PER_HOUR=20
DEBUG=False
```

### Deployment Checklist

- [ ] Mailgun domain verified with SPF/DKIM records
- [ ] API key from production Mailgun account
- [ ] Correct region selected (US/EU)
- [ ] Sender email matches verified domain
- [ ] Environment variables set in deployment platform
- [ ] Test email sending from production environment
- [ ] Monitor Mailgun logs for first 24 hours
- [ ] Update monitoring/alerting for Mailgun deliverability

## Cost Comparison

### AWS SES
- **Pricing:** $0.10 per 1,000 emails
- **Contact form usage:** ~$0/month (negligible)
- **Setup complexity:** High (IAM, SES verification, sandbox mode)
- **Support:** Ticket-based only

### Mailgun (Your Paid Account)
- **Pricing:** Already covered by existing account
- **Contact form usage:** ~10-50 emails/month = negligible impact
- **Setup complexity:** Low (just API key and domain)
- **Support:** Email and chat support

**Result:** Essentially free for contact form usage, much simpler setup.

## Rollback Plan (If Needed)

If you need to revert to AWS SES:

```bash
git revert 5213686  # Revert "Migrate from AWS SES to Mailgun"
git revert 48fb6c1  # Revert "Update backend README"
git revert 2c125f3  # Revert "Update implementation docs"
```

Then:
1. Add `boto3>=1.37.0` back to `requirements.txt`
2. Restore AWS credentials in `.env`
3. Test email delivery

## Git Commits

Migration completed in 3 commits:

1. **`5213686`** - Migrate from AWS SES to Mailgun for email delivery
2. **`48fb6c1`** - Update backend README for Mailgun configuration
3. **`2c125f3`** - Update implementation docs for Mailgun migration

## Next Steps

1. **Get Mailgun credentials** from your dashboard
2. **Update `.env`** with actual values
3. **Test locally** following testing guide above
4. **Update production** environment variables
5. **Deploy** and monitor

## Support

- **Mailgun Docs:** https://documentation.mailgun.com/
- **Mailgun Support:** Available via dashboard
- **Backend README:** See `backend/README.md` for detailed setup

---

**Migration Status:** ✅ Complete and ready for testing

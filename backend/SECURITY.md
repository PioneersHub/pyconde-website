# Security Documentation - PyConDE Contact Form API

This document outlines the security measures implemented to protect the contact form API from spam, abuse, and unauthorized access.

## Table of Contents

- [Security Architecture](#security-architecture)
- [Protection Layers](#protection-layers)
- [Deployment Options](#deployment-options)
- [Configuration Guide](#configuration-guide)
- [Monitoring & Alerts](#monitoring--alerts)
- [Security Best Practices](#security-best-practices)
- [Incident Response](#incident-response)

## Security Architecture

The API implements **defense-in-depth** with multiple security layers:

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: AWS WAF (DDoS, SQL Injection, XSS)           │
├─────────────────────────────────────────────────────────┤
│  Layer 2: API Gateway Throttling (Rate Limiting)        │
├─────────────────────────────────────────────────────────┤
│  Layer 3: API Key Middleware (Optional)                 │
├─────────────────────────────────────────────────────────┤
│  Layer 4: CORS Validation                               │
├─────────────────────────────────────────────────────────┤
│  Layer 5: Honeypot Detection                            │
├─────────────────────────────────────────────────────────┤
│  Layer 6: reCAPTCHA v3 Verification                     │
├─────────────────────────────────────────────────────────┤
│  Layer 7: Input Validation (Pydantic)                   │
└─────────────────────────────────────────────────────────┘
```

## Protection Layers

### Layer 1: AWS WAF (Web Application Firewall)

**Protection against:**

- DDoS attacks (100 requests per 5 minutes per IP)
- SQL injection attempts
- Cross-site scripting (XSS)
- Known bad inputs and attack patterns
- Bot traffic

**Configuration:** See [`template-secure.yaml`](template-secure.yaml)

**Key Rules:**

- Rate-based rule: 100 requests / 5 minutes per IP
- AWS Managed Common Rule Set
- AWS Managed Known Bad Inputs Rule Set
- SQL injection pattern matching
- XSS pattern matching

### Layer 2: API Gateway Throttling

**Protection against:**

- API abuse
- Request flooding
- Resource exhaustion

**Default Limits:**

- **Rate Limit:** 10 requests/minute per user
- **Burst Limit:** 20 requests (for traffic spikes)

**Configurable via SAM parameters:**

```yaml
RateLimitPerMinute: 10  # Adjust as needed
BurstLimit: 20          # Adjust as needed
```

### Layer 3: Optional API Key Authentication

**Protection against:**

- Unauthorized API access
- Scrapers and bots that bypass reCAPTCHA

**When to enable:**

- Public URL exposure concerns
- Need for request tracking per API key
- Additional security for sensitive deployments

**Configuration:**

```bash
# Generate a secure API key
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Set in .env or Lambda environment
API_KEY=your_generated_key_here
```

**Frontend integration:**

```javascript
fetch(API_URL, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'your_generated_key_here'
  },
  body: JSON.stringify(formData)
});
```

⚠️ **Important:** If API key is enabled, update frontend to include the header, otherwise all requests will be rejected with 403 Forbidden.

### Layer 4: CORS (Cross-Origin Resource Sharing)

**Protection against:**

- Cross-site request forgery (CSRF)
- Unauthorized domains using the API

**Configuration:**

- Configured at API Gateway level
- Enforced at FastAPI application level
- Only allows requests from whitelisted domains

**Allowed origins:**

- `https://2026.pycon.de`
- `https://pycon.de`
- `http://localhost:5001` (development only)

### Layer 5: Honeypot Field

**Protection against:**

- Simple bots that auto-fill forms
- Automated spam submissions

**How it works:**

- Hidden form field named `honeypot`
- Must remain empty (humans don't see it)
- Bots often fill all fields, triggering detection

### Layer 6: Google reCAPTCHA v3

**Protection against:**

- Sophisticated bots
- Automated form submissions
- Credential stuffing attacks

**Configuration:**

- Score threshold: 0.5 (configurable)
- No user interaction required (invisible)
- Analyzes user behavior patterns

### Layer 7: Input Validation

**Protection against:**

- Malformed requests
- Oversized payloads
- Invalid email formats

**Validation rules:**

- Name: 1-100 characters
- Email: Valid email format (RFC 5322)
- Subject: 1-200 characters
- Message: 10-5000 characters
- All fields sanitized and validated

## Deployment Options

### Option 1: Basic (Function URL)

**Use template.yaml**

✅ **Pros:**

- Simple deployment
- Lower cost
- Fast setup

❌ **Cons:**

- No WAF protection
- No API Gateway throttling
- Function URL publicly visible

**Suitable for:**

- Low-traffic sites
- Internal use
- Development/testing

**Deploy:**

```bash
sam build -t template.yaml
sam deploy --guided
```

### Option 2: Secure (API Gateway + WAF) ⭐ **Recommended**

**Use template-secure.yaml**

✅ **Pros:**

- Full WAF protection
- API Gateway throttling
- Managed rule sets
- CloudWatch metrics
- Professional-grade security

❌ **Cons:**

- Slightly higher cost (~$1-5/month)
- More complex setup

**Suitable for:**

- Production deployments
- Public-facing sites
- High-security requirements

**Deploy:**

```bash
sam build -t template-secure.yaml
sam deploy --guided --template-file template-secure.yaml
```

## Configuration Guide

### Securing FastAPI Documentation

**Production:** Docs automatically disabled when `DEBUG=False`

```python
# Controlled in main.py
app = FastAPI(
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)
```

**Accessing docs in development:**

```bash
# Set DEBUG=True in .env
DEBUG=True

# Restart server
uv run uvicorn main:app --reload

# Access docs
open http://localhost:8000/docs
```

⚠️ **Never set `DEBUG=True` in production!**

### Enabling API Key Protection

1. **Generate secure key:**

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

2. **Set in environment:**

```bash
# .env file
API_KEY=your_generated_key_here

# Or in SAM template parameters
ApiKey: your_generated_key_here
```

3. **Update frontend:**

```javascript
// Add header to all API requests
headers: {
  'X-API-Key': 'your_generated_key_here'
}
```

4. **Test:**

```bash
# Without API key (should fail)
curl -X POST https://your-api-url/api/contact \
  -H "Content-Type: application/json" \
  -d '{"name":"Test","email":"test@example.com",...}'
# Response: 403 Forbidden

# With API key (should succeed)
curl -X POST https://your-api-url/api/contact \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_generated_key_here" \
  -d '{"name":"Test","email":"test@example.com",...}'
# Response: 200 OK
```

### Adjusting Rate Limits

**API Gateway throttling:**

```yaml
# template-secure.yaml
Parameters:
  RateLimitPerMinute:
    Default: 10  # Adjust this
  BurstLimit:
    Default: 20  # Adjust this
```

**WAF rate limiting:**

```yaml
# template-secure.yaml
RateBasedStatement:
  Limit: 100  # 100 requests per 5 minutes
```

## Monitoring & Alerts

### CloudWatch Metrics

**Lambda Metrics:**

- Invocations
- Errors
- Duration
- Throttles

**API Gateway Metrics:**

- Request count
- 4xx errors (client errors)
- 5xx errors (server errors)
- Latency

**WAF Metrics:**

- Allowed requests
- Blocked requests
- Rate limit violations
- Rule matches

### Viewing Logs

```bash
# Lambda logs
sam logs --stack-name pyconde-contact-form --tail

# API Gateway logs
aws logs tail /aws/apigateway/pyconde-contact-form --follow

# WAF logs (if enabled)
aws wafv2 get-sampled-requests --web-acl-arn <WAF_ARN>
```

### Setting Up Alerts

**CloudWatch Alarms:**

```bash
# High error rate alarm
aws cloudwatch put-metric-alarm \
  --alarm-name pyconde-contact-form-high-errors \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold

# High request rate alarm
aws cloudwatch put-metric-alarm \
  --alarm-name pyconde-contact-form-high-requests \
  --metric-name Count \
  --namespace AWS/ApiGateway \
  --statistic Sum \
  --period 60 \
  --threshold 100 \
  --comparison-operator GreaterThanThreshold
```

## Security Best Practices

### 1. Environment Variables

✅ **Do:**

- Use AWS Systems Manager Parameter Store or Secrets Manager for secrets
- Rotate API keys regularly
- Use strong, randomly generated keys

❌ **Don't:**

- Commit `.env` files to git
- Share API keys in plaintext
- Reuse keys across environments

### 2. CORS Configuration

✅ **Do:**

- Whitelist only necessary origins
- Remove `localhost` origins in production
- Use HTTPS origins only

❌ **Don't:**

- Use wildcard `*` origins
- Allow all methods
- Disable CORS validation

### 3. Logging

✅ **Do:**

- Log failed reCAPTCHA attempts
- Log API key validation failures
- Log honeypot triggers
- Monitor for patterns

❌ **Don't:**

- Log sensitive data (emails, messages)
- Log API keys or secrets
- Disable logging in production

### 4. Updates & Patching

✅ **Do:**

- Keep Python dependencies updated
- Monitor security advisories
- Test updates in staging first
- Review AWS WAF managed rule updates

### 5. Access Control

✅ **Do:**

- Use principle of least privilege for IAM roles
- Enable MFA for AWS console access
- Regularly audit IAM permissions
- Use separate AWS accounts for prod/dev

## Incident Response

### Suspected Attack or Abuse

1. **Immediate Actions:**

   ```bash
   # Check WAF blocked requests
   aws wafv2 list-web-acls --scope REGIONAL

   # Check recent logs for patterns
   sam logs --stack-name pyconde-contact-form --start-time '30min ago'

   # Check API Gateway metrics
   aws cloudwatch get-metric-statistics \
     --namespace AWS/ApiGateway \
     --metric-name Count \
     --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
     --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
     --period 300 \
     --statistics Sum
   ```

2. **Temporary Mitigation:**

   ```bash
   # Enable stricter rate limiting (redeploy with lower limits)
   # Or temporarily enable API key requirement

   # Update Lambda environment variable
   aws lambda update-function-configuration \
     --function-name pyconde-contact-form-api \
     --environment "Variables={API_KEY=temporary_key_12345,...}"
   ```

3. **Block Specific IPs (if needed):**

   ```bash
   # Add IP set to WAF
   aws wafv2 create-ip-set \
     --name BlockedIPs \
     --scope REGIONAL \
     --ip-address-version IPV4 \
     --addresses "1.2.3.4/32" "5.6.7.8/32"

   # Create rule to block IP set
   # (Update WAF WebACL with new rule)
   ```

### Suspected Data Breach

1. Review CloudWatch logs for unauthorized access
2. Rotate all API keys and secrets immediately
3. Check for unusual Lambda invocations
4. Review email sent (check Mailgun logs)
5. Document incident timeline
6. Consider notifying affected users if personal data accessed

### False Positives

If legitimate users are blocked:

1. **Check WAF logs** for specific rule matches
2. **Adjust rule sensitivity** in `template-secure.yaml`
3. **Whitelist specific patterns** if needed
4. **Consider raising rate limits** for legitimate use cases

## Cost Considerations

**Security features cost breakdown:**

| Feature | Cost (Monthly) | Notes |
|---------|----------------|-------|
| Lambda invocations | $0-1 | Free tier: 1M requests |
| API Gateway | $0-2 | $3.50 per million requests |
| WAF (Base) | $5 | $5/month + $1 per rule |
| WAF (Requests) | $0-2 | $0.60 per million requests |
| CloudWatch Logs | $0-1 | First 5GB free |
| **Total (Secure)** | **$5-10/month** | For typical contact form usage |

**Without WAF (basic template.yaml):** ~$0-2/month

## Support & Resources

- [AWS WAF Documentation](https://docs.aws.amazon.com/waf/)
- [API Gateway Security Best Practices](https://docs.aws.amazon.com/apigateway/latest/developerguide/security-best-practices.html)
- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [Google reCAPTCHA Documentation](https://developers.google.com/recaptcha)

## Security Checklist

Before deploying to production:

- [ ] `DEBUG=False` in production environment
- [ ] Removed `localhost` from `ALLOWED_ORIGINS`
- [ ] reCAPTCHA site key and secret configured
- [ ] Mailgun API key secured (not in git)
- [ ] Decided on deployment option (basic vs secure)
- [ ] Reviewed and adjusted rate limits
- [ ] Considered enabling API key authentication
- [ ] Set up CloudWatch alarms
- [ ] Documented API endpoint URL (keep private!)
- [ ] Tested all security layers
- [ ] Reviewed WAF rules and tested blocking
- [ ] Planned incident response procedures

---

**Last Updated:** 2025-10-24
**Security Contact:** [Your security team email]

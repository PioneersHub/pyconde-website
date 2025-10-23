# Google reCAPTCHA Setup Guide

## Current Error

**Error:** "Ungültiger Websiteschlüssel" (Invalid site key)
**Cause:** The contact form is using placeholder reCAPTCHA keys

## Quick Setup Steps

### 1. Register Your Site with Google reCAPTCHA

1. **Go to:** https://www.google.com/recaptcha/admin/create

2. **Fill out the form:**
   - **Label:** PyConDE Contact Form (or any name you prefer)
   - **reCAPTCHA type:** Select **"reCAPTCHA v2"** → **"I'm not a robot" Checkbox**
   - **Domains:** Add these domains:
     ```
     localhost
     127.0.0.1
     2026.pycon.de
     pycon.de
     ```
   - **Accept terms** and click **Submit**

3. **Copy your keys:**
   - **Site Key** (public) - starts with `6Le...`
   - **Secret Key** (private) - Keep this secret!

### 2. Update Frontend Configuration

Edit `content/contact/contents.lr`:

```
_model: contact-form
---
title: Contact Us
---
body:

Have a question, suggestion, or just want to get in touch? We'd love to hear from you!

Please fill out the form below and we'll get back to you as soon as possible.

For sponsorship inquiries, please visit our [sponsoring page](/sponsoring).
---
api_endpoint: http://localhost:8000/api/contact
---
recaptcha_site_key: YOUR_ACTUAL_SITE_KEY_HERE
```

Replace `YOUR_ACTUAL_SITE_KEY_HERE` with the **Site Key** from step 1.

### 3. Update Backend Configuration

Edit `backend/.env`:

```env
RECAPTCHA_SECRET_KEY=YOUR_ACTUAL_SECRET_KEY_HERE
```

Replace `YOUR_ACTUAL_SECRET_KEY_HERE` with the **Secret Key** from step 1.

### 4. Restart Services

**Restart Lektor (if running):**
```bash
# Press Ctrl+C to stop, then:
make run
```

**Backend automatically reloads** (no restart needed due to `--reload` flag)

### 5. Test the Form

1. Visit http://localhost:5001/contact
2. reCAPTCHA should now show properly
3. Fill out the form and submit
4. Check backend logs for verification

## Alternative: Test Keys (Not Recommended for Production)

Google provides test keys that always pass, but they show a warning:

**Test Site Key:**
```
6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI
```

**Test Secret Key:**
```
6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe
```

⚠️ **Warning:** These are public test keys. Use only for initial testing, not for production!

## For Production Deployment

When deploying to production:

1. **Update domains in reCAPTCHA admin:**
   - Remove `localhost` and `127.0.0.1`
   - Keep only `2026.pycon.de` and `pycon.de`

2. **Update frontend `contents.lr`:**
   ```
   api_endpoint: https://your-production-api-url/api/contact
   recaptcha_site_key: YOUR_PRODUCTION_SITE_KEY
   ```

3. **Update backend production environment:**
   - Set `RECAPTCHA_SECRET_KEY` in Lambda/ECS environment variables
   - Ensure it matches the production site key

## Troubleshooting

### Error: "Invalid site key"
- Check that the site key is correct
- Verify the domain is added in reCAPTCHA admin
- Clear browser cache and reload

### Error: "ERROR for site owner: Invalid domain for site key"
- Add the current domain to reCAPTCHA admin
- For local testing, ensure `localhost` is added

### reCAPTCHA verification fails on backend
- Check that `RECAPTCHA_SECRET_KEY` matches the site key
- Verify backend can reach Google's API (https://www.google.com/recaptcha/api/siteverify)
- Check backend logs for detailed error messages

## Quick Test (Using Test Keys)

If you want to test immediately without registration:

1. **Update `content/contact/contents.lr`:**
   ```
   recaptcha_site_key: 6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI
   ```

2. **Update `backend/.env`:**
   ```
   RECAPTCHA_SECRET_KEY=6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe
   ```

3. **Restart Lektor:**
   ```bash
   make run
   ```

4. **Test at:** http://localhost:5001/contact

The form should work, but will show a warning banner about using test keys.

## Next Steps

✅ Register site at https://www.google.com/recaptcha/admin/create
✅ Update `content/contact/contents.lr` with site key
✅ Update `backend/.env` with secret key
✅ Restart Lektor (`make run`)
✅ Test form submission

---

**Need Help?**
- reCAPTCHA Docs: https://developers.google.com/recaptcha/docs/display
- reCAPTCHA Admin: https://www.google.com/recaptcha/admin

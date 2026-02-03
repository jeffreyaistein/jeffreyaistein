# Jeffrey AIstein - Domain Setup Guide

> **Domain**: JeffreyAIstein.fun
> **Target**: jeffreyaistein.fly.dev (Fly.io)
> **Last Updated**: 2026-02-02

---

## Overview

This guide covers pointing the custom domain `JeffreyAIstein.fun` to the Fly.io deployment.

---

## Step 1: Add Custom Domain to Fly.io

Run this command to register the domain with Fly:

```bash
fly certs create JeffreyAIstein.fun --app jeffreyaistein
```

This will output the IP addresses needed for DNS configuration.

**Example output:**
```
Your certificate for JeffreyAIstein.fun is being issued.
Hostname: JeffreyAIstein.fun
DNS Record Type: A
IP Address: 66.241.124.xxx (example)

For IPv6:
DNS Record Type: AAAA
IP Address: 2a09:8280:1::xxx (example)
```

Note the IP addresses - you'll need them for DNS records.

---

## Step 2: Configure DNS Records

Log in to your domain registrar (where you purchased JeffreyAIstein.fun) and add these DNS records:

### Option A: A/AAAA Records (Recommended)

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | @ | (IPv4 from Step 1) | 300 |
| AAAA | @ | (IPv6 from Step 1) | 300 |

**For www subdomain (optional):**
| Type | Name | Value | TTL |
|------|------|-------|-----|
| CNAME | www | JeffreyAIstein.fun | 300 |

### Option B: CNAME Record (if registrar doesn't support A at root)

Some registrars don't allow A records at the root (@). In that case:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| CNAME | @ | jeffreyaistein.fly.dev | 300 |

> Note: CNAME at root may not work with all registrars (ALIAS/ANAME may be needed).

---

## Step 3: Verify DNS Propagation

Wait a few minutes for DNS to propagate, then verify:

```bash
# Check A record
nslookup JeffreyAIstein.fun

# Or with dig
dig JeffreyAIstein.fun A
dig JeffreyAIstein.fun AAAA

# Online tools
# https://dnschecker.org/#A/JeffreyAIstein.fun
```

**Expected result**: Should return the Fly.io IP addresses from Step 1.

---

## Step 4: Verify TLS Certificate

Fly.io automatically provisions a TLS certificate via Let's Encrypt once DNS is configured.

```bash
# Check certificate status
fly certs show JeffreyAIstein.fun --app jeffreyaistein
```

**Expected output:**
```
Hostname: JeffreyAIstein.fun
DNS Configured: true
Certificate Status: issued
```

If `DNS Configured: false`, DNS hasn't propagated yet. Wait and retry.

---

## Step 5: Update CORS / Allowed Origins

Once the domain is live, update the API's CORS configuration to allow requests from the custom domain.

### In Fly Secrets

```bash
fly secrets set CORS_ORIGINS="https://JeffreyAIstein.fun,https://www.JeffreyAIstein.fun,https://jeffreyaistein.fly.dev" --app jeffreyaistein
```

### Or in API Code

If CORS is hardcoded, update `apps/api/main.py`:

```python
origins = [
    "https://JeffreyAIstein.fun",
    "https://www.JeffreyAIstein.fun",
    "https://jeffreyaistein.fly.dev",
    "http://localhost:3000",  # Development
]
```

---

## Step 6: Test the Domain

1. **Visit the site**: https://JeffreyAIstein.fun
2. **Check HTTPS**: Ensure the padlock icon appears (valid TLS)
3. **Test API calls**: Ensure chat and other features work from the new domain
4. **Check health endpoint**: https://JeffreyAIstein.fun/health/ready (if proxied)

---

## Troubleshooting

### DNS Not Propagating

- TTL may be high on old records - wait up to 24 hours
- Check with multiple DNS servers: `dig @8.8.8.8 JeffreyAIstein.fun`
- Verify records are correct at registrar

### Certificate Not Issuing

```bash
# Re-check certificate
fly certs check JeffreyAIstein.fun --app jeffreyaistein

# If stuck, remove and re-add
fly certs remove JeffreyAIstein.fun --app jeffreyaistein
fly certs create JeffreyAIstein.fun --app jeffreyaistein
```

### CORS Errors

- Verify `CORS_ORIGINS` includes the exact domain (with https://)
- Check browser console for specific origin being blocked
- Restart app after updating secrets: `fly apps restart jeffreyaistein`

---

## Admin Checklist

- [ ] Purchase/verify ownership of JeffreyAIstein.fun
- [ ] Run `fly certs create` command
- [ ] Add DNS records at registrar
- [ ] Verify DNS propagation (dnschecker.org)
- [ ] Verify TLS certificate issued (`fly certs show`)
- [ ] Update CORS origins
- [ ] Test site loads at https://JeffreyAIstein.fun
- [ ] Test API endpoints work from custom domain
- [ ] Update docs/BRAND.md with confirmed domain

---

## Quick Reference

| Item | Value |
|------|-------|
| Domain | JeffreyAIstein.fun |
| Fly App | jeffreyaistein |
| Current URL | https://jeffreyaistein.fly.dev |
| Certificate | Auto-provisioned by Fly (Let's Encrypt) |

---

## Related Docs

- [Fly.io Custom Domains](https://fly.io/docs/app-guides/custom-domains-with-fly/)
- [docs/BRAND.md](./BRAND.md) - Canonical links
- [docs/RUNBOOK_3DAY.md](./RUNBOOK_3DAY.md) - Operational procedures

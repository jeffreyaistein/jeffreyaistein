# Jeffrey AIstein - Operations Guide

**Last Updated:** 2026-02-03

Day-to-day operations guide for running and maintaining the Jeffrey AIstein system.

---

## Quick Reference

| Action | Command/URL |
|--------|-------------|
| **Check health** | `curl https://jeffreyaistein.fly.dev/health/ready` |
| **View logs** | `fly logs -a jeffreyaistein` |
| **SSH into container** | `fly ssh console -a jeffreyaistein` |
| **Kill switch ON** | `PATCH /api/admin/social/settings {"safe_mode": true}` |
| **Approve drafts** | `GET /api/admin/social/drafts` then `POST .../approve` |
| **Redeploy backend** | `fly deploy` |
| **Redeploy frontend** | Push to main or manual redeploy in Vercel |

---

## 1. Health Checks

### Basic Health

```bash
curl https://jeffreyaistein.fly.dev/health
```

Returns: `{"status": "healthy", "timestamp": "..."}`

### Full Dependency Check

```bash
curl https://jeffreyaistein.fly.dev/health/ready
```

Returns status of:
- Database connection
- Redis connection
- X bot scheduler (if enabled)

Example response:
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "x_bot": {
    "enabled": false,
    "ingestion_running": false,
    "timeline_running": false
  }
}
```

### TTS Health

```bash
curl https://jeffreyaistein.fly.dev/api/tts/status
```

Returns ElevenLabs configuration status and quota.

---

## 2. Log Access

### Live Logs (Fly.io)

```bash
# All logs
fly logs -a jeffreyaistein

# Last 100 lines
fly logs -a jeffreyaistein -n 100

# Follow mode
fly logs -a jeffreyaistein -f
```

### Filter by Component

```bash
# API requests only
fly logs -a jeffreyaistein | grep "POST\|GET\|PATCH"

# Errors only
fly logs -a jeffreyaistein | grep -i error

# X bot activity
fly logs -a jeffreyaistein | grep -i "ingestion\|timeline\|x_bot"
```

### Vercel Logs (Frontend)

1. Go to Vercel dashboard > jeffreyaistein project
2. Click "Logs" tab
3. Filter by function or time range

---

## 3. X Bot Operations

### Check Bot Status

```bash
curl -H "X-Admin-Key: $ADMIN_KEY" \
  https://jeffreyaistein.fly.dev/api/admin/social/status
```

Returns:
- Scheduler status
- Last ingestion time
- Draft counts
- Rate limit status

### Review Pending Drafts

```bash
# List all pending drafts
curl -H "X-Admin-Key: $ADMIN_KEY" \
  https://jeffreyaistein.fly.dev/api/admin/social/drafts
```

### Approve a Draft

```bash
curl -X POST \
  -H "X-Admin-Key: $ADMIN_KEY" \
  https://jeffreyaistein.fly.dev/api/admin/social/drafts/{draft_id}/approve
```

### Reject a Draft

```bash
curl -X POST \
  -H "X-Admin-Key: $ADMIN_KEY" \
  https://jeffreyaistein.fly.dev/api/admin/social/drafts/{draft_id}/reject
```

### Pause Posting (Safe Mode)

```bash
curl -X PATCH \
  -H "X-Admin-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"safe_mode": true}' \
  https://jeffreyaistein.fly.dev/api/admin/social/settings
```

### Resume Posting

```bash
curl -X PATCH \
  -H "X-Admin-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"safe_mode": false}' \
  https://jeffreyaistein.fly.dev/api/admin/social/settings
```

---

## 4. Style Management

### Check Current Style

```bash
curl -H "X-Admin-Key: $ADMIN_KEY" \
  https://jeffreyaistein.fly.dev/api/admin/persona/status
```

### List Style Versions

```bash
curl -H "X-Admin-Key: $ADMIN_KEY" \
  https://jeffreyaistein.fly.dev/api/admin/persona/style/versions
```

### Activate a Style Version

```bash
curl -X POST \
  -H "X-Admin-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"version": 3}' \
  https://jeffreyaistein.fly.dev/api/admin/persona/style/activate
```

### Rollback Style

```bash
curl -X POST \
  -H "X-Admin-Key: $ADMIN_KEY" \
  https://jeffreyaistein.fly.dev/api/admin/persona/style/rollback
```

### Manually Generate Style Proposal

```bash
curl -X POST \
  -H "X-Admin-Key: $ADMIN_KEY" \
  https://jeffreyaistein.fly.dev/api/admin/persona/style/generate
```

---

## 5. Deployment

### Backend (Fly.io)

```bash
cd api

# Deploy from current directory
fly deploy

# Deploy specific branch
git checkout main
fly deploy
```

**Pre-deploy checklist:**
- [ ] Run tests locally: `pytest`
- [ ] Check for uncommitted changes: `git status`
- [ ] Review secrets are set: `fly secrets list`

### Frontend (Vercel)

**Automatic:** Push to main branch triggers deploy.

**Manual:**
1. Go to Vercel dashboard > jeffreyaistein
2. Click "Deployments"
3. Click "Redeploy" on latest deployment

**Environment changes:**
1. Update in Vercel dashboard > Settings > Environment Variables
2. Trigger new deployment (changes are build-time only)

---

## 6. Database Operations

### Connect to Database

```bash
# Via Fly proxy
fly proxy 15432:5432 -a jeffreyaistein-db

# Then in another terminal
psql postgresql://postgres:PASSWORD@localhost:15432/aistein
```

### Common Queries

```sql
-- Recent conversations
SELECT id, user_id, created_at FROM conversations ORDER BY created_at DESC LIMIT 10;

-- Message counts by day
SELECT DATE(created_at), COUNT(*) FROM messages GROUP BY DATE(created_at) ORDER BY 1 DESC;

-- Pending X drafts
SELECT id, content, created_at FROM x_drafts WHERE status = 'pending';

-- Active runtime settings
SELECT key, value, updated_at FROM x_settings;

-- Memory extraction stats
SELECT type, COUNT(*) FROM memories GROUP BY type;
```

### Backup

```bash
# Fly.io provides daily backups. For manual backup:
fly proxy 15432:5432 -a jeffreyaistein-db &
pg_dump postgresql://postgres:PASSWORD@localhost:15432/aistein > backup.sql
```

---

## 7. Emergency Procedures

### Kill Switch (Stop All Posting)

```bash
curl -X PATCH \
  -H "X-Admin-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"safe_mode": true}' \
  https://jeffreyaistein.fly.dev/api/admin/social/settings
```

**Effect:** Immediately stops all X posting. Ingestion continues but no drafts are posted.

### Disable X Bot Entirely

```bash
fly secrets set X_BOT_ENABLED=false -a jeffreyaistein
fly deploy -a jeffreyaistein
```

**Effect:** Stops ingestion and timeline workers. Requires redeploy.

### Disable TTS

Set in Fly secrets:
```bash
fly secrets set ENABLE_TTS=false -a jeffreyaistein
fly deploy -a jeffreyaistein
```

### Rollback Deployment

```bash
# List recent deployments
fly releases -a jeffreyaistein

# Rollback to previous release
fly deploy --image registry.fly.io/jeffreyaistein:deployment-XXXXX -a jeffreyaistein
```

### Clear Rate Limit (Redis)

```bash
fly ssh console -a jeffreyaistein
# Inside container:
redis-cli -u $REDIS_URL
> DEL rate_limit:*
```

---

## 8. Monitoring Alerts

### What to Watch

| Metric | Normal | Alert Threshold |
|--------|--------|-----------------|
| Health check | 200 OK | Any 5xx |
| Response time | < 500ms | > 2s |
| Error rate | < 1% | > 5% |
| Draft queue | < 50 | > 100 |
| TTS errors | 0 | > 10/hour |

### Setting Up Monitoring

1. **Uptime monitoring**: Use UptimeRobot or similar
   - Monitor: `https://jeffreyaistein.fly.dev/health`
   - Interval: 5 minutes
   - Alert on: 5xx or timeout

2. **Error tracking**: Sentry (if `SENTRY_DSN` is set)
   - Alerts on: New error types, error spikes

3. **Fly.io metrics**: Dashboard shows CPU, memory, network

---

## 9. Troubleshooting

### Chat Not Working

1. Check health endpoint: `curl .../health/ready`
2. Check Vercel console for connection errors
3. Verify `NEXT_PUBLIC_API_BASE_URL` is correct
4. Check Fly.io logs for errors

### TTS Not Playing

1. Check TTS status: `curl .../api/tts/status`
2. Verify ElevenLabs API key is set
3. Check browser console for errors
4. Verify voice button is enabled (user gesture required)

### X Bot Not Posting

1. Check `X_BOT_ENABLED=true`
2. Check `SAFE_MODE=false`
3. Check `APPROVAL_REQUIRED` - if true, drafts need approval
4. Check rate limits: `GET /api/admin/social/status`
5. Check X API credentials: `scripts/verify_x_credentials.py`

### WebSocket Disconnections

1. Check Fly.io logs for connection errors
2. Verify CORS origins include frontend URL
3. Check for proxy/firewall issues
4. Client should auto-reconnect (check reconnect logic)

### Database Connection Issues

1. Check Fly Postgres status: `fly status -a jeffreyaistein-db`
2. Verify `DATABASE_URL` is correct
3. Check connection pool exhaustion in logs

---

## 10. Scheduled Maintenance

### Weekly Tasks

- [ ] Review pending drafts
- [ ] Check error logs for patterns
- [ ] Review memory extraction quality
- [ ] Check TTS usage/quota

### Monthly Tasks

- [ ] Review style proposals
- [ ] Audit rate limit settings
- [ ] Check Fly.io resource usage
- [ ] Review Vercel usage/costs
- [ ] Test backup restoration

### Quarterly Tasks

- [ ] Rotate admin API keys
- [ ] Review and prune old conversations
- [ ] Update dependencies
- [ ] Security audit of exposed endpoints

---

## 11. CLI Scripts Reference

Run from `api/` directory:

```bash
# Verify X credentials
python scripts/verify_x_credentials.py

# Verify learning persistence
python scripts/verify_learning_persistence.py

# Build style guide from KOL tweets
python scripts/build_style_guide.py

# Generate style proposal manually
python scripts/propose_style_guide.py

# Test persona output
python scripts/test_style_output.py

# Ingest Epstein corpus
python scripts/ingest_epstein_corpus.py --sources doj_releases
```

---

## 12. Contact and Escalation

| Issue | Action |
|-------|--------|
| Service down | Check Fly.io status, redeploy |
| Data breach concern | Enable kill switch, audit logs |
| API key compromised | Rotate immediately via Fly secrets |
| X account issue | Contact X Developer support |
| Billing issue | Check Fly.io/Vercel/ElevenLabs dashboards |

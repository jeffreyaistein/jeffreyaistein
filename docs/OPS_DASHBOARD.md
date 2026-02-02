# Jeffrey AIstein - Ops Dashboard Checklist

> **Purpose**: Twice-daily operational health checks during 72-hour validation
> **Frequency**: Morning (~09:00 UTC) and Evening (~21:00 UTC)
> **Period**: 2026-02-02 to 2026-02-05

---

## Quick Commands

### 1. Health/Ready Check
```powershell
# PowerShell
$health = Invoke-RestMethod -Uri "https://jeffreyaistein.fly.dev/health/ready"
$health | ConvertTo-Json -Depth 5
```

```bash
# curl (if available)
curl -s https://jeffreyaistein.fly.dev/health/ready | jq .
```

**Expected Response:**
```json
{
  "ready": true,
  "checks": {
    "database": true,
    "redis": true,
    "llm": true,
    "x_bot": true
  },
  "x_bot_enabled": true,
  "x_bot_running": true
}
```

---

### 2. Admin Social Status

**Note**: Admin key is in `apps/api/.env` (ADMIN_API_KEY) or Fly secrets.

**Supported auth headers** (either works):
- `X-Admin-Key: <key>`
- `Authorization: Bearer <key>`

```powershell
# PowerShell - Get key from .env first
$key = (Get-Content "C:\Users\Louie\apps\api\.env" | Select-String "ADMIN_API_KEY=").ToString().Split("=")[1]
$headers = @{"X-Admin-Key" = $key}
$status = Invoke-RestMethod -Uri "https://jeffreyaistein.fly.dev/api/admin/social/status" -Headers $headers
$status | ConvertTo-Json -Depth 5
```

```bash
# curl - Replace $ADMIN_KEY with actual key from .env
curl -s -H "X-Admin-Key: $ADMIN_KEY" \
  https://jeffreyaistein.fly.dev/api/admin/social/status | jq .
```

**Expected Response:**
```json
{
  "enabled": true,
  "ingestion": {
    "running": true,
    "total_fetched": <number>,
    "since_id": "<string or null>"
  },
  "timeline": {
    "running": true,
    "total_posts": <number>,
    "next_post_in_seconds": <number>
  },
  "safe_mode": true,
  "approval_required": true
}
```

---

### 3. Fly Logs - Error Filter
```powershell
# Get recent logs and filter for errors
"C:\Users\Louie\.fly\bin\fly.exe" logs --app jeffreyaistein --no-tail 2>&1 | Select-String -Pattern "error|ERROR|exception|EXCEPTION|warning|WARNING|failed|FAILED"
```

```bash
# Alternative: direct filter
fly logs --app jeffreyaistein --no-tail 2>&1 | grep -iE "error|exception|warning|failed"
```

**Expected**: No critical errors. Occasional warnings may be acceptable.

---

### 4. Drafts Queue Check
```powershell
$headers = @{"X-Admin-Key" = "YOUR_ADMIN_KEY"}
$drafts = Invoke-RestMethod -Uri "https://jeffreyaistein.fly.dev/api/admin/social/drafts" -Headers $headers
$drafts | ConvertTo-Json -Depth 5
```

---

### 5. App Status Check
```powershell
"C:\Users\Louie\.fly\bin\fly.exe" status --app jeffreyaistein
```

**Check for:**
- Machines: at least 1 running
- No crash loops
- Uptime consistent

---

## Recording Template

Copy this template for each check and fill in the values:

```
## Check: [DATE] [TIME] UTC

### Health Ready
- ready: [ ]
- database: [ ]
- redis: [ ]
- llm: [ ]
- x_bot: [ ]
- x_bot_running: [ ]

### Social Status
- ingestion.running: [ ]
- ingestion.total_fetched: ___
- ingestion.since_id: ___
- timeline.running: [ ]
- timeline.total_posts: ___
- timeline.next_post_in_seconds: ___
- safe_mode: [ ]
- approval_required: [ ]

### Deltas Since Last Check
- ingestion_count_delta: ___
- drafts_created_delta: ___
- posts_made_delta: ___

### Error Log Summary
- Total errors found: ___
- Notable errors: ___

### Redis Lock Status
- Redis connected: [ ]
- Leader lock held: [ ] (if applicable)

### Notes
- ___
```

---

## Day 1 Checks

### Check 1: 2026-02-02 Morning
```
Timestamp: ___
Health: [ ] OK  [ ] ISSUES
Social Status: [ ] OK  [ ] ISSUES
Errors: [ ] None  [ ] See notes
Notes: ___
```

### Check 2: 2026-02-02 Evening
```
Timestamp: ___
Health: [ ] OK  [ ] ISSUES
Social Status: [ ] OK  [ ] ISSUES
Errors: [ ] None  [ ] See notes
Notes: ___
```

---

## Day 2 Checks

### Check 3: 2026-02-03 Morning
```
Timestamp: ___
Health: [ ] OK  [ ] ISSUES
ingestion.total_fetched: ___ (delta: ___)
timeline.total_posts: ___ (delta: ___)
Errors: [ ] None  [ ] See notes
Notes: ___
```

### Check 4: 2026-02-03 Evening
```
Timestamp: ___
Health: [ ] OK  [ ] ISSUES
ingestion.total_fetched: ___ (delta: ___)
timeline.total_posts: ___ (delta: ___)
Errors: [ ] None  [ ] See notes
Notes: ___
```

---

## Day 3 Checks

### Check 5: 2026-02-04 Morning
```
Timestamp: ___
Health: [ ] OK  [ ] ISSUES
ingestion.total_fetched: ___ (delta: ___)
timeline.total_posts: ___ (delta: ___)
Errors: [ ] None  [ ] See notes
Notes: ___
```

### Check 6: 2026-02-04 Evening
```
Timestamp: ___
Health: [ ] OK  [ ] ISSUES
ingestion.total_fetched: ___ (delta: ___)
timeline.total_posts: ___ (delta: ___)
Errors: [ ] None  [ ] See notes
Notes: ___
```

---

## Final Check (End of 72 Hours)

### Check 7: 2026-02-05 16:30 UTC
```
Timestamp: ___
Health: [ ] OK  [ ] ISSUES

### Cumulative Stats
- Total mentions fetched: ___
- Total drafts created: ___
- Total posts made: ___
- Total errors encountered: ___
- Uptime: ___

### Go-Live Decision
[ ] PROCEED - Disable SAFE_MODE
[ ] EXTEND - Continue monitoring
[ ] ROLLBACK - Disable X_BOT_ENABLED

Approved by: ___
Date: ___
```

---

## Alert Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| ingestion loop stall | > 2 min | > 3 min |
| 429 rate limit errors | > 1/hour | > 3/hour |
| Exception count | > 2/check | > 5/check |
| Redis connection | 1 failure | 2+ failures |
| Machine restarts | > 1/day | > 3/day |

See `RUNBOOK_3DAY.md` for incident tripwires and remediation.

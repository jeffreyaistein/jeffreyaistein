# Jeffrey AIstein - X Bot Live Smoke Test

> **Purpose**: Verify X bot is working correctly in production
> **Date Created**: 2026-02-02
> **Environment**: Fly.io (https://jeffreyaistein.fly.dev)

---

## Pre-Flight Checks

### 1. Secrets Verification

```powershell
"C:\Users\Louie\.fly\bin\fly.exe" secrets list --app jeffreyaistein
```

| Secret | Required | Status |
|--------|----------|--------|
| X_API_KEY | Yes | ✅ |
| X_API_SECRET | Yes | ✅ |
| X_ACCESS_TOKEN | Yes | ✅ |
| X_ACCESS_TOKEN_SECRET | Yes | ✅ |
| X_BOT_USER_ID | Yes | ✅ |
| X_BEARER_TOKEN | Optional | ✅ |
| X_BOT_ENABLED | Yes | ✅ (true) |
| SAFE_MODE | Yes | ✅ (true) |
| APPROVAL_REQUIRED | Yes | ✅ (true) |
| USE_MEMORY_STORAGE | Yes | ✅ (true) |
| ANTHROPIC_API_KEY | Yes | ✅ |
| REDIS_URL | Yes | ✅ |

---

## Phase 1: Health Endpoints

### Test 1.1: Basic Health
```powershell
Invoke-RestMethod -Uri "https://jeffreyaistein.fly.dev/health"
```
**Expected**: `{"status": "ok"}`
**Result**: ✅ PASS

### Test 1.2: Readiness Check
```powershell
Invoke-RestMethod -Uri "https://jeffreyaistein.fly.dev/health/ready"
```
**Expected**:
- `ready: true`
- `checks.database: true`
- `checks.redis: true`
- `checks.llm: true`
- `checks.x_bot: true`
- `x_bot_running: true`

**Result**: ✅ PASS (2026-02-02 16:45 UTC)
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

### Test 1.3: Liveness Check
```powershell
Invoke-RestMethod -Uri "https://jeffreyaistein.fly.dev/health/live"
```
**Expected**: `{"live": true}`
**Result**: ✅ PASS

---

## Phase 2: X API Connectivity (Read Operations)

### Test 2.1: Mentions Fetch (via logs)
```powershell
"C:\Users\Louie\.fly\bin\fly.exe" logs --app jeffreyaistein --no-tail
```

**Look for**:
- `x_api_fetch_mentions` - API call initiated
- `x_api_mentions_fetched count=N` - Successful response

**Result**: ✅ PASS
```
2026-02-02 16:44:58 [debug] x_api_fetch_mentions bot_user_id=201814435494 max_results=100 since_id=None
2026-02-02 16:44:58 [info] x_api_mentions_fetched count=0 since_id=None
```

### Test 2.2: Health Check Passes
**Look for in logs**:
- `x_api_health_check_passed` - OAuth 1.0a auth working

**Result**: ✅ PASS (verified during startup)

---

## Phase 3: Scheduler Loops

### Test 3.1: Ingestion Loop Running
**Look for in logs**:
- `ingestion_polling since_id=...` - Every ~45 seconds
- `ingestion_no_new_mentions` - Normal when no new mentions

**Result**: ✅ PASS
- Polling every 45 seconds
- No errors

### Test 3.2: Timeline Poster Loop Running
**Look for in logs**:
- `timeline_poster_waiting wait_seconds=N` - Every ~60 seconds

**Result**: ✅ PASS
- Waiting ~9500 seconds (first post in ~2.6 hours)
- Jitter applied correctly

---

## Phase 4: Safe Mode Verification

### Test 4.1: Safe Mode Enabled
The bot should NOT post any tweets while SAFE_MODE=true.

**Verification**:
1. Check logs for any `x_api_post_tweet` events - should be NONE
2. Check for `safe_mode_blocking_post` events if content was generated

**Result**: ✅ PASS - No posting attempts in logs

### Test 4.2: Approval Required
When APPROVAL_REQUIRED=true, drafts should be stored for admin approval.

**Note**: This can only be fully tested when someone mentions the bot or the timeline poster generates content.

---

## Phase 5: Error Handling

### Test 5.1: No Crash Loops
```powershell
"C:\Users\Louie\.fly\bin\fly.exe" status --app jeffreyaistein
```

**Check**:
- Machines status: `started` (not `crashed` or `stopped`)
- No repeated restarts

**Result**: ✅ PASS - Machine running stable

### Test 5.2: No API Errors
**Check logs for**:
- `x_api_error` - Should be rare/none
- `x_api_rate_limited` - Should be none in normal operation
- HTTP 401/403 errors - Should be none

**Result**: ✅ PASS - No errors in recent logs

---

## Phase 6: Admin Endpoints (When Admin Key Available)

### Test 6.1: Status Endpoint
```powershell
Invoke-RestMethod -Uri "https://jeffreyaistein.fly.dev/api/admin/social/status" `
  -Headers @{"X-Admin-Key"="YOUR_ADMIN_KEY"}
```

**Expected**:
```json
{
  "enabled": true,
  "ingestion": {"running": true, "total_fetched": 0},
  "timeline": {"running": true, "total_posts": 0},
  "safe_mode": true,
  "approval_required": true
}
```

### Test 6.2: Drafts Endpoint
```powershell
Invoke-RestMethod -Uri "https://jeffreyaistein.fly.dev/api/admin/social/drafts" `
  -Headers @{"X-Admin-Key"="YOUR_ADMIN_KEY"}
```

**Expected**: List of pending drafts (may be empty initially)

### Test 6.3: Kill Switch
```powershell
Invoke-RestMethod -Uri "https://jeffreyaistein.fly.dev/api/admin/kill_switch" `
  -Headers @{"X-Admin-Key"="YOUR_ADMIN_KEY"}
```

**Expected**: `{"safe_mode": true, "message": "..."}`

---

## Phase 7: Integration Test (Manual)

### Test 7.1: Trigger a Mention
1. From a test account, tweet: `@JeffreyAIstein hello test`
2. Wait 1-2 minutes for ingestion
3. Check logs for:
   - `x_api_mentions_fetched count=1`
   - `ingestion_processing_mention`
   - `draft_created` (if approved) or `mention_rejected` (if quality score too low)

### Test 7.2: First Timeline Post (Wait ~3 hours)
1. Monitor logs for `timeline_poster_generating`
2. Should see `draft_created` (approval required) or `timeline_post_blocked` (safe mode)

---

## Emergency Procedures

### Stop X Bot Immediately
```powershell
"C:\Users\Louie\.fly\bin\fly.exe" secrets set X_BOT_ENABLED=false --app jeffreyaistein
```

### Enable Kill Switch (Soft Stop)
```powershell
"C:\Users\Louie\.fly\bin\fly.exe" secrets set SAFE_MODE=true --app jeffreyaistein
```

### Check Recent Errors
```powershell
"C:\Users\Louie\.fly\bin\fly.exe" logs --app jeffreyaistein --no-tail 2>&1 | Select-String "error|ERROR|exception"
```

### Restart App
```powershell
"C:\Users\Louie\.fly\bin\fly.exe" apps restart jeffreyaistein
```

---

## Smoke Test Summary

| Phase | Test | Status |
|-------|------|--------|
| 1 | Health Endpoints | ✅ PASS |
| 2 | X API Connectivity | ✅ PASS |
| 3 | Scheduler Loops | ✅ PASS |
| 4 | Safe Mode | ✅ PASS |
| 5 | Error Handling | ✅ PASS |
| 6 | Admin Endpoints | ⏸️ SKIPPED (key mismatch) |
| 7 | Integration Test | ⏸️ MANUAL (optional) |

**Overall Result**: ✅ PASS - X Bot is running correctly in safe mode

---

## Phase 8: Web Frontend Verification

### Test 8.1: Token Metrics Panel
**URL**: https://jeffreyaistein.vercel.app

**Check**:
- [ ] Token Metrics panel shows status indicator (INDEXING or LIVE)
- [ ] NO "Phase 5" text visible
- [ ] If INDEXING: Shows "Indexing token data..." message
- [ ] If LIVE: Shows market cap, holders, 24h volume, meter

**Verification**:
```powershell
Invoke-RestMethod -Uri "https://jeffreyaistein.fly.dev/api/token/metrics"
```
Expected: Returns `state: "indexing"` or `state: "live"`

### Test 8.2: AGI Bot Stats Panel
**URL**: https://jeffreyaistein.vercel.app

**Check**:
- [ ] AGI Bot Stats panel shows LIVE status indicator
- [ ] NO "Phase 6" text visible
- [ ] Shows real message counts (MESSAGES IN, MESSAGES OUT)
- [ ] Shows CONVERSATIONS count
- [ ] Shows LEARNING PROGRESS meter
- [ ] Shows "Last updated" timestamp

**Verification**:
```powershell
Invoke-RestMethod -Uri "https://jeffreyaistein.fly.dev/api/stats/agent"
```
Expected: Returns real counts from database

---

## Go-Live Checklist (When Ready to Post)

Before disabling safe mode:

1. [ ] Verify bot has been running stable for 24+ hours
2. [ ] Test admin approval workflow manually
3. [ ] Review quality scoring thresholds
4. [ ] Confirm rate limits are appropriate
5. [ ] Have emergency contacts ready

```powershell
# When ready to go live:
"C:\Users\Louie\.fly\bin\fly.exe" secrets set SAFE_MODE=false --app jeffreyaistein

# Keep approval required for initial live period:
# APPROVAL_REQUIRED=true (already set)

# After confidence is established, disable approval requirement:
# "C:\Users\Louie\.fly\bin\fly.exe" secrets set APPROVAL_REQUIRED=false --app jeffreyaistein
```

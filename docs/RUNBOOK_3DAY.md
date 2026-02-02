# Jeffrey AIstein - 3-Day Monitoring Runbook

> **Purpose**: Monitor X bot stability over 72-hour initial deployment period
> **Start Date**: 2026-02-02 16:30 UTC
> **End Date**: 2026-02-05 16:30 UTC
> **Environment**: Fly.io (https://jeffreyaistein.fly.dev)

---

## Quick Reference

### Check Health (Quick)
```powershell
Invoke-RestMethod -Uri "https://jeffreyaistein.fly.dev/health/ready"
```

### View Recent Logs
```powershell
"C:\Users\Louie\.fly\bin\fly.exe" logs --app jeffreyaistein --no-tail
```

### Check App Status
```powershell
"C:\Users\Louie\.fly\bin\fly.exe" status --app jeffreyaistein
```

### Emergency Stop
```powershell
"C:\Users\Louie\.fly\bin\fly.exe" secrets set X_BOT_ENABLED=false --app jeffreyaistein
```

---

## Day 1 Checklist (Hours 0-24)

### Hour 0-1: Initial Deployment
- [x] X bot enabled in safe mode
- [x] Health endpoints returning healthy
- [x] Ingestion loop polling (~45s interval)
- [x] Timeline poster waiting (~3h until first attempt)
- [x] No errors in logs

### Hour 1-4: First Timeline Post Attempt
- [ ] Check for `timeline_poster_generating` in logs
- [ ] Verify draft created (not posted - safe mode)
- [ ] Check LLM content generation worked
- [ ] Note: First post attempt at ~19:00-19:30 UTC

### Hour 4-12: Steady State
- [ ] Verify no crash loops
- [ ] Check mentions are being fetched
- [ ] Verify rate limits not exceeded
- [ ] Check memory usage (in-memory storage)

### Hour 12-24: End of Day 1
- [ ] Review any errors in logs
- [ ] Verify machine still running
- [ ] Check database connectivity
- [ ] Note total mentions fetched

**Day 1 Status**: ⬜ Pending

---

## Day 2 Checklist (Hours 24-48)

### Morning Check (Hour 24-28)
- [ ] Health endpoints healthy
- [ ] App not crashed overnight
- [ ] Ingestion loop still running
- [ ] Timeline posts generated (as drafts)

### Midday Check (Hour 28-36)
- [ ] Verify no rate limiting events
- [ ] Check Redis connectivity
- [ ] Review any new errors
- [ ] Note patterns in mentions (if any)

### Evening Check (Hour 36-48)
- [ ] Count total drafts created
- [ ] Verify memory usage stable
- [ ] No repeated errors
- [ ] Timeline poster cycling correctly (~3h)

**Day 2 Status**: ⬜ Pending

---

## Day 3 Checklist (Hours 48-72)

### Morning Check (Hour 48-52)
- [ ] Health endpoints healthy
- [ ] App running continuously
- [ ] No memory leaks (check logs for OOM)
- [ ] Ingestion consistent

### Decision Point (Hour 52-60)
Based on 48-hour stability:

**If Stable**:
- Consider disabling SAFE_MODE
- Keep APPROVAL_REQUIRED=true initially
- Continue monitoring for 24h more

**If Issues**:
- Keep SAFE_MODE=true
- Investigate errors
- Fix and redeploy

### Final Check (Hour 60-72)
- [ ] All systems green
- [ ] No critical errors
- [ ] Ready for live posting (if applicable)

**Day 3 Status**: ⬜ Pending

---

## Monitoring Commands

### Check Machine Memory/CPU
```powershell
"C:\Users\Louie\.fly\bin\fly.exe" machine status <MACHINE_ID> --app jeffreyaistein
```

### Get Machine ID
```powershell
"C:\Users\Louie\.fly\bin\fly.exe" machine list --app jeffreyaistein
```

### SSH into Container (if needed)
```powershell
"C:\Users\Louie\.fly\bin\fly.exe" ssh console --app jeffreyaistein
```

### Check Postgres
```powershell
"C:\Users\Louie\.fly\bin\fly.exe" postgres connect --app jeffreyaistein-db
```

### Check Redis
```powershell
# Via health endpoint - shows redis: true/false
Invoke-RestMethod -Uri "https://jeffreyaistein.fly.dev/health/ready"
```

---

## Expected Log Patterns

### Normal Operation
```
[debug] ingestion_polling since_id=...
[debug] x_api_fetch_mentions bot_user_id=... max_results=100
[info]  x_api_mentions_fetched count=N
[debug] ingestion_no_new_mentions (or ingestion_processing_mention)
[debug] timeline_poster_waiting wait_seconds=...
```

### When Generating Content
```
[info]  timeline_poster_generating
[info]  content_generator_started topic=...
[info]  content_generator_completed length=...
[info]  draft_created id=... (if approval_required)
[info]  safe_mode_blocking_post (if safe_mode)
```

### Warning Signs (Investigate)
```
[warning] x_api_rate_limited
[warning] x_api_health_check_failed
[error]   x_api_error status_code=...
[error]   llm_generation_failed
```

### Critical (Action Required)
```
[error]   database_connection_failed
[error]   redis_connection_failed
[error]   x_api_auth_failed
Machine status: crashed
```

---

## Incident Tripwires

Automated thresholds that trigger immediate action. If any condition is met, execute the corresponding remediation.

### Tripwire 1: Ingestion Loop Stall
**Condition**: No `ingestion_polling` log entry for > 3 minutes

**Detection**:
```powershell
# Check last ingestion timestamp in logs
"C:\Users\Louie\.fly\bin\fly.exe" logs --app jeffreyaistein --no-tail 2>&1 | Select-String "ingestion_polling" | Select-Object -Last 1
```

**Remediation**:
```powershell
# Step 1: Restart the app
"C:\Users\Louie\.fly\bin\fly.exe" apps restart jeffreyaistein

# Step 2: If restart doesn't fix, disable X bot
"C:\Users\Louie\.fly\bin\fly.exe" secrets set X_BOT_ENABLED=false --app jeffreyaistein

# Step 3: Check logs for root cause
"C:\Users\Louie\.fly\bin\fly.exe" logs --app jeffreyaistein --no-tail 2>&1 | Select-String "error|exception"
```

---

### Tripwire 2: Repeated 429 Rate Limits
**Condition**: More than 3 `x_api_rate_limited` events in 1 hour

**Detection**:
```powershell
"C:\Users\Louie\.fly\bin\fly.exe" logs --app jeffreyaistein --no-tail 2>&1 | Select-String "rate_limited|429"
```

**Remediation**:
```powershell
# Step 1: Enable safe mode to stop all posting attempts
"C:\Users\Louie\.fly\bin\fly.exe" secrets set SAFE_MODE=true --app jeffreyaistein

# Step 2: Increase backoff time
"C:\Users\Louie\.fly\bin\fly.exe" secrets set X_API_BACKOFF_BASE_SECONDS=120 --app jeffreyaistein

# Step 3: Reduce poll frequency
"C:\Users\Louie\.fly\bin\fly.exe" secrets set X_POLL_INTERVAL_SECONDS=90 --app jeffreyaistein
```

---

### Tripwire 3: Repeated Exceptions
**Condition**: More than 5 `[error]` log entries in any 10-minute window

**Detection**:
```powershell
"C:\Users\Louie\.fly\bin\fly.exe" logs --app jeffreyaistein --no-tail 2>&1 | Select-String "\[error\]"
```

**Remediation**:
```powershell
# Step 1: Enable safe mode immediately
"C:\Users\Louie\.fly\bin\fly.exe" secrets set SAFE_MODE=true --app jeffreyaistein

# Step 2: If errors continue, disable X bot entirely
"C:\Users\Louie\.fly\bin\fly.exe" secrets set X_BOT_ENABLED=false --app jeffreyaistein

# Step 3: Investigate specific error
"C:\Users\Louie\.fly\bin\fly.exe" logs --app jeffreyaistein --no-tail 2>&1 | Select-String "\[error\]" | Select-Object -Last 10
```

---

### Tripwire 4: Restart Loops
**Condition**: Machine restarts more than 3 times in 1 hour

**Detection**:
```powershell
"C:\Users\Louie\.fly\bin\fly.exe" status --app jeffreyaistein
# Check for multiple machines in "stopped" or "starting" state
```

**Remediation**:
```powershell
# Step 1: Disable X bot (likely causing crashes)
"C:\Users\Louie\.fly\bin\fly.exe" secrets set X_BOT_ENABLED=false --app jeffreyaistein

# Step 2: Force restart with clean state
"C:\Users\Louie\.fly\bin\fly.exe" apps restart jeffreyaistein

# Step 3: Check for OOM or startup errors
"C:\Users\Louie\.fly\bin\fly.exe" logs --app jeffreyaistein --no-tail 2>&1 | Select-String "OOM|killed|crash|startup"
```

---

### Tripwire 5: Redis Connection Lost
**Condition**: `redis_connection_failed` in logs OR `/health/ready` shows `redis: false`

**Detection**:
```powershell
$health = Invoke-RestMethod -Uri "https://jeffreyaistein.fly.dev/health/ready"
if ($health.checks.redis -eq $false) { Write-Host "REDIS DOWN" -ForegroundColor Red }
```

**Remediation**:
```powershell
# Step 1: Disable X bot (leader lock depends on Redis)
"C:\Users\Louie\.fly\bin\fly.exe" secrets set X_BOT_ENABLED=false --app jeffreyaistein

# Step 2: Check Redis status
"C:\Users\Louie\.fly\bin\fly.exe" redis status jeffreyaistein-redis

# Step 3: Verify REDIS_URL secret is correct
"C:\Users\Louie\.fly\bin\fly.exe" secrets list --app jeffreyaistein | Select-String "REDIS_URL"
```

---

### Tripwire 6: Database Connection Lost
**Condition**: `/health/ready` shows `database: false`

**Detection**:
```powershell
$health = Invoke-RestMethod -Uri "https://jeffreyaistein.fly.dev/health/ready"
if ($health.checks.database -eq $false) { Write-Host "DATABASE DOWN" -ForegroundColor Red }
```

**Remediation**:
```powershell
# Step 1: Check Postgres status
"C:\Users\Louie\.fly\bin\fly.exe" status --app jeffreyaistein-db

# Step 2: Restart Postgres if needed
"C:\Users\Louie\.fly\bin\fly.exe" apps restart jeffreyaistein-db

# Step 3: Restart main app to reconnect
"C:\Users\Louie\.fly\bin\fly.exe" apps restart jeffreyaistein
```

---

### Tripwire 7: Auth Failures (401/403)
**Condition**: `x_api_auth_failed` or repeated 401/403 in logs

**Detection**:
```powershell
"C:\Users\Louie\.fly\bin\fly.exe" logs --app jeffreyaistein --no-tail 2>&1 | Select-String "401|403|auth_failed|Unauthorized"
```

**Remediation**:
```powershell
# Step 1: Disable X bot immediately
"C:\Users\Louie\.fly\bin\fly.exe" secrets set X_BOT_ENABLED=false --app jeffreyaistein

# Step 2: Verify X API credentials in Developer Portal
# - Check app is not suspended
# - Verify tokens are not revoked
# - Regenerate tokens if needed

# Step 3: Update secrets if credentials changed
"C:\Users\Louie\.fly\bin\fly.exe" secrets set X_API_KEY=... X_API_SECRET=... --app jeffreyaistein
```

---

### Tripwire Summary Table

| Tripwire | Condition | Severity | First Action |
|----------|-----------|----------|--------------|
| Ingestion Stall | No poll > 3 min | HIGH | Restart app |
| Rate Limits | > 3 429s/hour | MEDIUM | Enable SAFE_MODE |
| Exceptions | > 5 errors/10min | HIGH | Enable SAFE_MODE |
| Restart Loops | > 3/hour | CRITICAL | Disable X_BOT |
| Redis Lost | redis=false | HIGH | Disable X_BOT |
| Database Lost | database=false | CRITICAL | Restart Postgres |
| Auth Failures | 401/403 | CRITICAL | Disable X_BOT |

---

## Troubleshooting

### Bot Not Polling
1. Check X_BOT_ENABLED=true
2. Check health endpoint shows x_bot=true
3. Restart app: `fly apps restart jeffreyaistein`

### 403 Auth Errors
1. Check X API credentials are correct
2. Verify OAuth 1.0a tokens not expired
3. Check X Developer Portal for app status

### Rate Limited
1. Wait for backoff (automatic)
2. Check X_API_BACKOFF_BASE_SECONDS setting
3. Reduce X_POLL_INTERVAL_SECONDS if needed

### Memory Issues
1. Check logs for OOM
2. Consider restarting app
3. May need to switch to Postgres storage

### Database Errors
1. Check DATABASE_URL secret
2. Verify Postgres is running: `fly status --app jeffreyaistein-db`
3. Check connection limits

---

## Escalation

### Level 1: Self-Service
- Restart app
- Check secrets
- Review logs

### Level 2: Code Changes
- Fix bugs in code
- Redeploy
- Update environment variables

### Level 3: Infrastructure
- Fly.io support
- X API support
- Postgres/Redis issues

---

## Metrics to Track

| Metric | Target | Current |
|--------|--------|---------|
| Uptime | >99.9% | TBD |
| Mentions Processed | N/A | 0 |
| Timeline Posts Generated | ~8/day | 0 |
| API Errors | <1/hour | 0 |
| Rate Limit Events | 0/day | 0 |

---

## Sign-Off

### Day 1 Complete
- Date: ___________
- Status: ⬜ PASS / ⬜ ISSUES
- Notes:

### Day 2 Complete
- Date: ___________
- Status: ⬜ PASS / ⬜ ISSUES
- Notes:

### Day 3 Complete
- Date: ___________
- Status: ⬜ PASS / ⬜ ISSUES
- Notes:

### Go-Live Decision
- Date: ___________
- Decision: ⬜ Proceed / ⬜ Delay
- Approved By: ___________

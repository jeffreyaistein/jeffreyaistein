# Jeffrey AIstein - Production Checklist

> **Purpose**: End-to-end production verification for 3-day stable run
> **Date**: 2026-02-02
> **Environment**: Fly.io (https://jeffreyaistein.fly.dev)

---

## 1. Health Endpoints Verification

### Status: IN PROGRESS

### Endpoints to Verify

| Endpoint | Method | Expected Response | Status Code | Result |
|----------|--------|-------------------|-------------|--------|
| `/` | GET | `{"ok": true, "service": "Jeffrey AIstein API", "version": "0.1.0"}` | 200 | PENDING |
| `/health` | GET | `{"status": "ok"}` | 200 | PENDING |
| `/health/ready` | GET | `{"ready": true/false, "checks": {...}}` | 200 | PENDING |
| `/health/live` | GET | `{"live": true}` | 200 | PENDING |
| `/docs` | GET | Swagger UI (debug mode only) | 200/404 | PENDING |

### Verification Commands

**PowerShell:**
```powershell
# Root endpoint
Invoke-WebRequest -Uri "https://jeffreyaistein.fly.dev/" -Method GET

# Health check
Invoke-WebRequest -Uri "https://jeffreyaistein.fly.dev/health" -Method GET

# Readiness check
Invoke-WebRequest -Uri "https://jeffreyaistein.fly.dev/health/ready" -Method GET

# Liveness check
Invoke-WebRequest -Uri "https://jeffreyaistein.fly.dev/health/live" -Method GET

# Docs (may return 404 if debug=false)
Invoke-WebRequest -Uri "https://jeffreyaistein.fly.dev/docs" -Method GET
```

**curl (if available):**
```bash
curl -s https://jeffreyaistein.fly.dev/
curl -s https://jeffreyaistein.fly.dev/health
curl -s https://jeffreyaistein.fly.dev/health/ready
curl -s https://jeffreyaistein.fly.dev/health/live
curl -s https://jeffreyaistein.fly.dev/docs
```

### Changes Made
- [x] Added root `/` endpoint returning `{"ok": true}` with service info

### Notes
- `/docs` is only available when `DEBUG=true` in environment
- `/health/ready` includes database connectivity check

---

## 2. Fly Deployment / Runtime Status

### Status: PENDING

### Commands to Run

```powershell
# Check app status
fly status --app jeffreyaistein

# View recent logs (last 200 lines)
fly logs --app jeffreyaistein -n 200

# Check machine health
fly machine list --app jeffreyaistein
```

### Expected Output
- No crash loops (restart count < 10)
- Machines status: `started` or `running`
- No repeated error messages in logs

### Results
_(To be filled after running commands)_

---

## 3. Machines Uptime Settings (3-day stability)

### Status: PENDING

### Current Settings
```toml
# fly.toml (BEFORE)
min_machines_running = 0
auto_stop_machines = 'stop'
auto_start_machines = true
```

### Required Changes for 3-day Stability
```toml
# fly.toml (AFTER)
min_machines_running = 1
auto_stop_machines = 'off'  # Prevent machines from stopping
auto_start_machines = true
```

### Verification
After deployment, verify with:
```powershell
fly status --app jeffreyaistein
# Should show at least 1 machine running constantly
```

---

## 4. Secrets Presence Verification

### Status: PENDING

### Command
```powershell
fly secrets list --app jeffreyaistein
```

### Required Secrets Checklist

| Secret Name | Required | Present |
|-------------|----------|---------|
| ANTHROPIC_API_KEY | Yes | ? |
| X_API_KEY | Yes | ? |
| X_API_SECRET | Yes | ? |
| X_ACCESS_TOKEN | Yes | ? |
| X_ACCESS_TOKEN_SECRET | Yes | ? |
| X_BOT_USER_ID | Yes | ? |
| X_BEARER_TOKEN | Optional | ? |
| SECRET_KEY | Yes | ? |
| ADMIN_API_KEY | Yes | ? |
| DATABASE_URL | If DB attached | ? |
| REDIS_URL | Optional | ? |
| SENTRY_DSN | Optional | ? |
| HELIUS_API_KEY | Optional | ? |
| HELIUS_RPC_URL | Optional | ? |
| VOYAGE_API_KEY | Optional | ? |

---

## 5. Postgres Readiness + Migrations

### Status: PENDING

### Verify DATABASE_URL
```powershell
fly secrets list --app jeffreyaistein | Select-String "DATABASE_URL"
```

### Run Migrations
```powershell
fly ssh console -a jeffreyaistein -C "cd /app && alembic upgrade head"
```

### Verify DB Connectivity
The `/health/ready` endpoint includes a `SELECT 1` check:
```powershell
Invoke-WebRequest -Uri "https://jeffreyaistein.fly.dev/health/ready" | ConvertFrom-Json
# Should show: "database": true
```

---

## 6. Redis Readiness + Leader Lock

### Status: PENDING

### Check Redis URL
```powershell
fly secrets list --app jeffreyaistein | Select-String "REDIS_URL"
```

### Leader Lock Behavior
- If REDIS_URL exists: Implement leader lock for schedulers
- If REDIS_URL missing: Force X_BOT_ENABLED=false to prevent duplicate schedulers

### Verification
Check `/api/admin/social/status` for leader lock status.

---

## 7. X Bot Safe Launch

### Status: PENDING

### Required Configuration
```env
X_BOT_ENABLED=true
SAFE_MODE=true           # Prevents posting
APPROVAL_REQUIRED=true   # Requires admin approval
```

### Verification Steps
1. Confirm ingestion loop runs without posting
2. Confirm drafts are created (not posted)
3. Test admin endpoints:
   - `GET /api/admin/social/status`
   - `GET /api/admin/social/drafts`
   - `POST /api/admin/social/drafts/{id}/approve`
   - `POST /api/admin/social/drafts/{id}/reject`

### Disabling SAFE_MODE Later
```powershell
fly secrets set SAFE_MODE=false --app jeffreyaistein
```

---

## 8. Observability (Sentry)

### Status: PENDING

### Check SENTRY_DSN
```powershell
fly secrets list --app jeffreyaistein | Select-String "SENTRY_DSN"
```

### Verify Sentry Integration
If SENTRY_DSN is set, Sentry should initialize on app startup.
Check Sentry dashboard for:
- App connected
- Heartbeat events

---

## Summary

| Item | Status | Blockers |
|------|--------|----------|
| 1. Health Endpoints | IN PROGRESS | Need to deploy root endpoint |
| 2. Fly Status | PENDING | |
| 3. Uptime Settings | PENDING | |
| 4. Secrets | PENDING | |
| 5. Postgres | PENDING | |
| 6. Redis/Leader Lock | PENDING | |
| 7. X Bot Safe Launch | PENDING | |
| 8. Sentry | PENDING | |

---

## Deployment Commands

```powershell
# After making changes, deploy with:
cd C:\Users\Louie\apps
git add -A
git commit -m "Production checklist fixes"
git push
fly deploy --app jeffreyaistein
```

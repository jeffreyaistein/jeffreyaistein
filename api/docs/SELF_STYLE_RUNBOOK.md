# Self-Style Pipeline Runbook

Jeffrey AIstein - Self-Style Pipeline Operations Guide

## Overview

The Self-Style Pipeline automatically analyzes AIstein's posted tweets to generate style guide proposals. These proposals capture patterns in tone, vocabulary, structure, and engagement to help maintain consistent voice.

**IMPORTANT SAFETY CONSTRAINTS:**
- Proposals are **NEVER** auto-activated. Admin approval is always required.
- Emojis and hashtags are **ALWAYS** forbidden, regardless of what the analysis suggests.
- All proposals are versioned and auditable.

---

## Hard Constraints

These constraints are enforced at the code level and cannot be overridden by configuration:

1. **No Auto-Activation**: Every generated proposal is inserted with `is_active=false`. Activation requires explicit admin action via the API.

2. **No Emojis**: The `allow_emojis` field is always set to `false` in generated proposals, even if the tweet dataset contains emojis.

3. **No Hashtags**: The `allow_hashtags` field is always set to `false` in generated proposals, even if the tweet dataset contains hashtags.

4. **Redis Required**: The SelfStyleWorker refuses to start without a valid Redis connection. This ensures distributed locking works correctly.

---

## Feature Flags & Defaults

All self-style settings are configured via environment variables:

| Environment Variable | Type | Default | Description |
|---------------------|------|---------|-------------|
| `SELF_STYLE_ENABLED` | bool | `false` | Master switch to enable/disable the SelfStyleWorker |
| `SELF_STYLE_INTERVAL_HOURS` | int | `24` | Hours between proposal generation runs |
| `SELF_STYLE_MIN_TWEETS` | int | `25` | Minimum tweets required to generate a proposal |
| `SELF_STYLE_MAX_TWEETS` | int | `500` | Maximum tweets to analyze per proposal |
| `SELF_STYLE_DAYS` | int | `30` | Days to look back for tweets |
| `SELF_STYLE_INCLUDE_REPLIES` | bool | `true` | Whether to include reply tweets in analysis |
| `REDIS_URL` | str | required | Redis connection URL (required for leader locks) |

### Example Configuration

```bash
# Enable self-style with conservative settings
SELF_STYLE_ENABLED=true
SELF_STYLE_INTERVAL_HOURS=48
SELF_STYLE_MIN_TWEETS=50
SELF_STYLE_MAX_TWEETS=200
SELF_STYLE_DAYS=14
SELF_STYLE_INCLUDE_REPLIES=false

# Redis is required
REDIS_URL=redis://localhost:6379/0
```

### Recommended Settings by Phase

**Early Days (< 100 total tweets):**
```bash
SELF_STYLE_ENABLED=true
SELF_STYLE_MIN_TWEETS=10
SELF_STYLE_INTERVAL_HOURS=168  # Weekly
SELF_STYLE_DAYS=30
```

**Normal Operation (100-1000 tweets):**
```bash
SELF_STYLE_ENABLED=true
SELF_STYLE_MIN_TWEETS=25
SELF_STYLE_INTERVAL_HOURS=24  # Daily
SELF_STYLE_DAYS=30
```

**Conservative/Production:**
```bash
SELF_STYLE_ENABLED=true
SELF_STYLE_MIN_TWEETS=50
SELF_STYLE_INTERVAL_HOURS=72  # Every 3 days
SELF_STYLE_DAYS=60
```

---

## Gating Logic

The SelfStyleWorker has multiple gating checks that determine whether it runs:

### Disabled Reasons (`disabled_reason` field)

| Value | Meaning | Resolution |
|-------|---------|------------|
| `disabled` | `SELF_STYLE_ENABLED=false` | Set `SELF_STYLE_ENABLED=true` in environment |
| `redis_missing` | `REDIS_URL` not configured | Add `REDIS_URL` to environment variables |
| `redis_unavailable` | Redis connection failed | Check Redis server is running and accessible |

### Skip Reasons (`last_run_status` / `skip_reason`)

| Value | Meaning | Resolution |
|-------|---------|------------|
| `skipped_insufficient_data` | Not enough tweets found | Wait for more tweets or lower `SELF_STYLE_MIN_TWEETS` |
| `skipped_lock_contention` | Another instance holds the leader lock | Normal in multi-instance deployments; this instance waits |
| `success` | Proposal generated successfully | N/A - working as expected |
| `failed` | Error during proposal generation | Check logs for error details |

### Startup Checks

When the worker starts, it performs these checks in order:

1. **Feature Flag Check**: Is `SELF_STYLE_ENABLED=true`?
   - If false: Sets `disabled_reason="disabled"` and exits

2. **Redis Configuration Check**: Is `REDIS_URL` set?
   - If not: Sets `disabled_reason="redis_missing"` and exits

3. **Redis Availability Check**: Can we connect to Redis?
   - If not: Sets `disabled_reason="redis_unavailable"` and exits

4. **Leader Lock Check**: Can we acquire the leader lock?
   - If not: Sets `last_run_status="skipped_lock_contention"` and waits for next interval

5. **Tweet Count Check**: Do we have >= `SELF_STYLE_MIN_TWEETS` in the last `SELF_STYLE_DAYS`?
   - If not: Sets `last_run_status="skipped_insufficient_data"` and waits for next interval

---

## How to Enable Safely

Follow these steps to enable the self-style pipeline in production:

### Step 1: Configure Redis

Ensure Redis is running and configure the connection:

```bash
# In .env
REDIS_URL=redis://your-redis-host:6379/0
```

Verify connectivity:
```bash
redis-cli -u $REDIS_URL ping
# Should return: PONG
```

### Step 2: Set Conservative Initial Values

Start with conservative settings to avoid surprises:

```bash
SELF_STYLE_ENABLED=false  # Keep disabled initially
SELF_STYLE_INTERVAL_HOURS=72
SELF_STYLE_MIN_TWEETS=50
SELF_STYLE_MAX_TWEETS=200
SELF_STYLE_DAYS=30
SELF_STYLE_INCLUDE_REPLIES=true
```

### Step 3: Deploy and Verify

Deploy the application and check the status endpoint:

```bash
curl http://localhost:8000/api/admin/self-style/status
```

Verify:
- `enabled` is `false`
- `disabled_reason` is `"disabled"` (not Redis-related)
- No errors in logs

### Step 4: Enable the Worker

Update the environment and restart:

```bash
SELF_STYLE_ENABLED=true
```

### Step 5: Monitor First Run

Watch the logs and status endpoint:

```bash
# Check style status (includes self_style_worker info)
curl -H "X-Admin-Key: YOUR_KEY" \
  http://localhost:8000/api/admin/persona/style/status

# Check social status (includes self_style stats)
curl -H "X-Admin-Key: YOUR_KEY" \
  http://localhost:8000/api/admin/social/status

# List generated proposals
curl -H "X-Admin-Key: YOUR_KEY" \
  http://localhost:8000/api/admin/persona/style/versions
```

### Step 6: Review and Activate

When a proposal is generated:

1. Review the proposal via admin API
2. Compare against current active guide
3. If acceptable, activate via admin endpoint
4. Monitor tweet quality after activation

---

## Leader Lock Behavior

The SelfStyleWorker uses Redis distributed locks to ensure only one instance runs the proposal generation at a time.

### Lock Details

| Property | Value |
|----------|-------|
| Lock Key | `self_style:leader` |
| TTL | 300 seconds (5 minutes) |
| Renewal | Automatic during processing |

### Multi-Instance Behavior

When running multiple API instances:

1. All instances start the SelfStyleWorker
2. Only one acquires the leader lock
3. Others skip with `skipped_lock_contention`
4. If the leader crashes, another instance acquires the lock after TTL expires

### Monitoring Lock Status

The status endpoint shows lock information:

```json
{
  "leader_lock": {
    "lock_key": "self_style:leader",
    "lock_ttl_seconds": 300,
    "instance_id": "abc123-...",
    "currently_held": false,
    "total_acquisitions": 5,
    "total_failures": 2
  }
}
```

---

## Monitoring Endpoints

Use these admin endpoints to check SelfStyleWorker health:

### Primary: GET /api/admin/persona/style/status

The most comprehensive endpoint for self-style monitoring.

```bash
curl -H "X-Admin-Key: YOUR_KEY" \
  https://your-api.fly.dev/api/admin/persona/style/status
```

**Response includes:**
```json
{
  "style_rewriter": { ... },
  "active_version": { "version_id": "...", ... },
  "last_proposal": {
    "version_id": "20260202_120000",
    "generated_at": "2026-02-02T12:00:00Z",
    "source": "self_style",
    "tweet_count": 50,
    "is_active": false
  },
  "last_proposal_error": null,
  "self_style_worker": {
    "enabled": true,
    "disabled_reason": null,
    "last_run_status": "success",
    "last_run_started_at": "2026-02-02T12:00:00Z",
    "last_run_finished_at": "2026-02-02T12:05:00Z",
    "last_error": null,
    "last_proposal_version_id": "20260202_120000",
    "total_proposals_generated": 5,
    "total_proposals_skipped": 2,
    "leader_lock": {
      "lock_key": "self_style:leader",
      "lock_ttl_seconds": 300,
      "currently_acquired": false,
      "instance_id": "abc123-...",
      "total_acquisitions": 5,
      "total_failures": 0
    }
  },
  "hard_rules_enforced": {
    "emojis_allowed": 0,
    "hashtags_allowed": 0
  }
}
```

### Alternative: GET /api/admin/social/status

Includes `self_style` field with full worker stats.

```bash
curl -H "X-Admin-Key: YOUR_KEY" \
  https://your-api.fly.dev/api/admin/social/status
```

### Learning Integration: GET /api/admin/learning/status

Includes `last_self_style_job_at` and `last_self_style_status` for quick checks.

```bash
curl -H "X-Admin-Key: YOUR_KEY" \
  https://your-api.fly.dev/api/admin/learning/status
```

---

## Troubleshooting

### Worker Not Starting

**Symptom:** Worker logs show it's not running

**Check:**
1. Is `SELF_STYLE_ENABLED=true`?
2. Is `REDIS_URL` configured?
3. Can the application reach Redis?

**Resolution:**
```bash
# Verify Redis
redis-cli -u $REDIS_URL ping

# Check worker status
curl -H "X-Admin-Key: YOUR_KEY" \
  http://localhost:8000/api/admin/persona/style/status
# Look at self_style_worker.disabled_reason field
```

### No Proposals Generated

**Symptom:** Worker runs but no proposals appear

**Check:**
1. Are there enough tweets? (check `SELF_STYLE_MIN_TWEETS`)
2. Is the date range correct? (check `SELF_STYLE_DAYS`)
3. Are tweets being ingested correctly?

**Resolution:**
```bash
# Check tweet count
curl http://localhost:8000/api/admin/tweets/count?days=30

# Lower threshold if needed
SELF_STYLE_MIN_TWEETS=10
```

### Lock Contention Errors

**Symptom:** `skipped_lock_contention` on all instances

**Check:**
1. Is another instance holding the lock?
2. Did an instance crash while holding the lock?

**Resolution:**
- Wait for TTL (5 minutes) to expire
- Or manually clear the lock (emergency only):
```bash
redis-cli -u $REDIS_URL DEL self_style:leader
```

---

## Related Documentation

- [Style Guide Schema](./STYLE_GUIDE_SCHEMA.md) - Structure of style guide proposals
- [Admin API Reference](./ADMIN_API.md) - Endpoints for managing proposals
- [Deployment Guide](./DEPLOYMENT.md) - Production deployment instructions

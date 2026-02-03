# Self-Style Pipeline Runbook

> **Status**: READY FOR USE
> **Last Updated**: 2026-02-02

---

## Overview

The self-style pipeline analyzes AIstein's own posted tweets to derive style patterns. This creates a feedback loop where AIstein learns from its own successful posts.

**IMPORTANT**: Proposals do NOT affect production until explicitly activated by an admin.

---

## Hard Brand Rules (Non-Negotiable)

These rules are ALWAYS enforced, regardless of what the dataset shows:

| Rule | Value | Enforcement |
|------|-------|-------------|
| Emojis | **0% - NEVER** | Stripped at post-processing |
| Hashtags | **0% - NEVER** | Stripped at post-processing |

These rules CANNOT be overridden by any proposal.

---

## Pipeline Components

### 1. Corpus Builder (`scripts/build_self_style_corpus.py`)

Exports AIstein's posted tweets to JSONL for analysis.

**Command:**
```bash
cd apps/api
python scripts/build_self_style_corpus.py --days 30 --limit 500 --output data/self_style_tweets.jsonl
```

**Options:**
- `--days N` - Only include tweets from last N days (0 = no limit)
- `--limit N` - Maximum tweets to export (default: 500)
- `--output PATH` - Output file path
- `--no-replies` - Exclude reply tweets
- `--include-risk-flagged` - Include tweets that were risk-flagged

**Output:**
- `data/self_style_tweets.jsonl` - JSONL file with tweet records

### 2. Proposal Generator (`scripts/propose_style_guide.py`)

Generates versioned style guide proposals from the corpus.

**Command:**
```bash
cd apps/api
python scripts/propose_style_guide.py --days 30 --min-tweets 25
```

**Options:**
- `--days N` - Days to look back for tweets (0 = no limit)
- `--limit N` - Maximum tweets to analyze (default: 500)
- `--min-tweets N` - Minimum tweets required (default: 25, fails if below)

**Output Files:**

| File | Location | Purpose |
|------|----------|---------|
| Markdown | `apps/docs/style_proposals/STYLE_GUIDE_PROPOSED_<timestamp>.md` | Human-readable proposal |
| JSON | `apps/api/services/persona/style_guide_proposals/<timestamp>.json` | Machine-readable rules |
| Metadata | `apps/api/services/persona/style_guide_proposals/<timestamp>_meta.json` | Version tracking |

---

## Proposal Workflow

### Step 1: Generate Proposal

```bash
# Requires DATABASE_URL environment variable
cd apps/api
python scripts/propose_style_guide.py --days 30
```

This will:
1. Build corpus from AIstein's tweets
2. Analyze patterns (length, vocabulary, structure)
3. Generate versioned proposal files
4. Print summary with version_id

### Step 2: Review Proposal

Review the generated markdown file:
```
apps/docs/style_proposals/STYLE_GUIDE_PROPOSED_<version_id>.md
```

Key sections to review:
- Proposed tweet length patterns
- Dataset statistics (reference only)
- CT vocabulary frequency
- Derived style rules

### Step 3: Activate Proposal (Admin Only)

**PROPOSALS ARE NOT AUTO-ACTIVATED**

See the Admin API Reference section below for detailed commands.

### Step 4: Verify Activation

Check the status endpoint to confirm the new version is active.

### Step 5: Rollback (If Needed)

Use the rollback endpoint to revert to a previous version.

---

## Admin API Reference

All endpoints require `X-Admin-Key` header.

### List All Versions

```bash
curl -s -H "X-Admin-Key: $ADMIN_KEY" \
  https://jeffreyaistein.fly.dev/api/admin/persona/style/versions | python -m json.tool
```

**Response:**
```json
{
  "versions": [
    {
      "version_id": "20260203_153045",
      "generated_at": "2026-02-03T15:30:45+00:00",
      "source": "self_style",
      "tweet_count": 127,
      "is_active": true,
      "activated_at": "2026-02-03T16:00:00+00:00",
      "md_path": "...",
      "json_path": "..."
    }
  ],
  "total": 3
}
```

### Activate a Version

```bash
curl -X POST -H "X-Admin-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"version_id": "20260203_153045"}' \
  https://jeffreyaistein.fly.dev/api/admin/persona/style/activate
```

**Response:**
```json
{
  "activated": true,
  "version_id": "20260203_153045",
  "activated_at": "2026-02-03T16:00:00",
  "reload_success": true,
  "style_rewriter_status": {
    "available": true,
    "source": "database",
    "active_version_id": "20260203_153045",
    "target_length": 150,
    "max_length": 280
  }
}
```

**Errors:**
- `404`: Version not found
- `400`: Version already active, JSON file missing, or fails safety validation

### Rollback to Previous Version

**Option 1: Rollback to most recently deactivated:**
```bash
curl -X POST -H "X-Admin-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"previous": true}' \
  https://jeffreyaistein.fly.dev/api/admin/persona/style/rollback
```

**Option 2: Rollback to specific version:**
```bash
curl -X POST -H "X-Admin-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"version_id": "20260201_120000"}' \
  https://jeffreyaistein.fly.dev/api/admin/persona/style/rollback
```

**Response:**
```json
{
  "rolled_back": true,
  "version_id": "20260201_120000",
  "activated_at": "2026-02-03T16:05:00",
  "reload_success": true,
  "style_rewriter_status": {...}
}
```

### Check Current Status

```bash
curl -s -H "X-Admin-Key: $ADMIN_KEY" \
  https://jeffreyaistein.fly.dev/api/admin/persona/style/status | python -m json.tool
```

**Response:**
```json
{
  "style_rewriter": {
    "available": true,
    "source": "database",
    "active_version_id": "20260203_153045",
    "generated_at": "2026-02-03T15:30:45+00:00",
    "target_length": 150,
    "max_length": 280
  },
  "active_version": {
    "version_id": "20260203_153045",
    "generated_at": "2026-02-03T15:30:45+00:00",
    "source": "self_style",
    "tweet_count": 127,
    "activated_at": "2026-02-03T16:00:00+00:00"
  },
  "hard_rules_enforced": {
    "emojis_allowed": 0,
    "hashtags_allowed": 0
  }
}
```

**Source Values:**
- `"database"` - Active version loaded from DB
- `"baseline"` - Fallback to baseline style_guide.json
- `"none"` - No guide available

---

## Version Tracking

All proposals are versioned with timestamps:
- Version ID format: `YYYYMMDD_HHMMSS`
- Example: `20260202_153045`

Each proposal creates 3 files:
1. `<version_id>.json` - The actual rules
2. `<version_id>_meta.json` - Metadata including activation status
3. `STYLE_GUIDE_PROPOSED_<version_id>.md` - Human-readable summary

---

## Minimum Tweet Requirements

The proposal generator fails if fewer than 25 tweets are available (configurable via `--min-tweets`).

This ensures:
- Statistically meaningful patterns
- Avoidance of overfitting to small samples
- Quality style derivation

---

## Scheduling (Future: B6.4)

Automatic scheduling is planned but not yet implemented. Current process is manual:

1. Run proposal generator periodically (suggested: weekly)
2. Review generated proposals
3. Activate approved proposals via admin endpoint

---

## Troubleshooting

### "DATABASE_URL environment variable not set"

The scripts require a PostgreSQL connection:
```bash
export DATABASE_URL="postgresql://..."
```

### "Insufficient tweets: X < 25 minimum"

Not enough tweets to analyze. Options:
- Wait for more tweets to be posted
- Lower the minimum with `--min-tweets 10`
- Expand date range with `--days 0` (no limit)

### Proposal not taking effect

Remember: proposals must be explicitly activated via the admin endpoint. Check:
1. Was the activation endpoint called?
2. Is the correct version_id being used?
3. Check activation status via `/api/admin/persona/status`

---

## Safety Reminders

1. **Hard brand rules are ALWAYS enforced** - No emojis, no hashtags, ever
2. **Proposals require approval** - Nothing auto-activates
3. **Rollback is available** - Can revert to previous version
4. **All changes are auditable** - Version history preserved

---

*This runbook covers the self-style pipeline for Jeffrey AIstein.*
*Proposals do not affect production until activated.*

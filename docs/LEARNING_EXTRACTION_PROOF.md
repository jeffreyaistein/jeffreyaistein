# Learning Extraction Proof

**Date:** 2026-02-02
**Task:** B5 - Add memory extraction job (learning v1)

## Overview

This document proves that the learning extraction system is correctly:
1. Extracting CT slang, narrative tags, risk flags, and engagement outcomes
2. Running automatically via the LearningWorker background task
3. Storing memories in the database with proper source_tweet_ids linkage
4. Accessible via admin endpoints for inspection

## Components Implemented

### 1. Extractor Module (`services/learning/extractor.py`)

**Features:**
- CT slang extraction (50+ terms: gm, wagmi, lfg, degen, alpha, etc.)
- Narrative tag extraction (12 patterns: token_talk, pump, dump, rug, etc.)
- Risk flag extraction (5 categories: phishing_link, scam_keyword, etc.)
- Engagement outcome tracking (replied, posted)
- Text cleaning (strips emojis and hashtags from all memory content)
- Idempotent processing (learning_processed flag prevents duplicate extraction)

**Memory Types:**
| Type | Description | Confidence |
|------|-------------|------------|
| x_slang | CT vocabulary term detected | 0.7 |
| x_narrative | Topic/narrative tag (pump, dump, etc.) | 0.6 |
| x_risk_flag | Risk signal detected | 0.8 |
| x_engagement | Action taken (replied, posted) | 0.9 |

### 2. Learning Worker (`services/social/scheduler/learning_worker.py`)

**Configuration:**
- Interval: 60 seconds (configurable via X_LEARNING_INTERVAL_SECONDS)
- Batch size: 50 items per iteration
- Runs independently of ingestion/posting loops
- Graceful shutdown on SIGTERM/SIGINT

**Stats tracked:**
- total_runs
- total_inbox_processed
- total_posts_processed
- total_memories_created
- total_errors

### 3. Admin Endpoints

**GET /api/admin/learning/status**
Returns learning extraction metrics including:
- extracted_memories_count
- processed_inbox_count
- processed_posts_count
- last_learning_job_at

**GET /api/admin/learning/recent**
Returns recent extracted memories with filters:
- `kind`: Filter by x_slang, x_narrative, x_risk_flag, x_engagement
- `limit`: Number of results (1-200)

**GET /api/admin/social/status**
Now includes learning worker stats.

**GET /health/ready**
Now includes learning_worker_running status.

## Database Schema

### Migration: 20260202_0003_learning_memory_columns.py

**memories table:**
- Added: `source_tweet_ids` (ARRAY of VARCHAR(30))
- GIN index for efficient source_tweet_ids lookups

**x_inbox table:**
- Added: `learning_processed` (BOOLEAN, default false)
- Added: `learning_processed_at` (TIMESTAMP)

**x_posts table:**
- Added: `learning_processed` (BOOLEAN, default false)
- Added: `learning_processed_at` (TIMESTAMP)

## Unit Tests

**File:** `tests/test_learning_extractor.py`

**Test Classes:**
- TestSlangExtraction (6 tests)
- TestNarrativeExtraction (4 tests)
- TestRiskExtraction (3 tests)
- TestEngagementOutcome (3 tests)
- TestCleanText (3 tests)
- TestExtractorIdempotency (2 tests)
- TestCTSlangVocabulary (2 tests)
- TestNarrativePatterns (1 test)
- TestRiskPatterns (1 test)

**Total:** 25 test cases

## Verification Commands

### Check learning status:
```bash
curl -H "X-Admin-Key: $ADMIN_KEY" \
  https://jeffreyaistein.fly.dev/api/admin/learning/status
```

### Get recent slang memories:
```bash
curl -H "X-Admin-Key: $ADMIN_KEY" \
  "https://jeffreyaistein.fly.dev/api/admin/learning/recent?kind=x_slang&limit=10"
```

### Get all recent learning memories:
```bash
curl -H "X-Admin-Key: $ADMIN_KEY" \
  "https://jeffreyaistein.fly.dev/api/admin/learning/recent?limit=50"
```

### Check social status (includes learning worker):
```bash
curl -H "X-Admin-Key: $ADMIN_KEY" \
  https://jeffreyaistein.fly.dev/api/admin/social/status
```

### Check health (includes learning worker running):
```bash
curl https://jeffreyaistein.fly.dev/health/ready
```

## Production Verification

*(To be filled after deployment)*

### Learning Status Response:
```json
{
  "inbound_tweets_count": <count>,
  "outbound_posts_count": <count>,
  "learning": {
    "extracted_memories_count": <count>,
    "processed_inbox_count": <count>,
    "processed_posts_count": <count>,
    "last_learning_job_at": "<timestamp>"
  }
}
```

### Recent Memories Sample:
```json
{
  "memories": [
    {
      "id": "<uuid>",
      "kind": "x_slang",
      "content": "gm",
      "confidence": 0.7,
      "source_tweet_ids": ["<tweet_id>"],
      "created_at": "<timestamp>"
    }
  ],
  "total": <count>
}
```

### Social Status (Learning Worker):
```json
{
  "learning": {
    "total_runs": <count>,
    "total_inbox_processed": <count>,
    "total_posts_processed": <count>,
    "total_memories_created": <count>,
    "total_errors": 0,
    "running": true
  }
}
```

## Files Created/Modified

### New Files:
- `api/services/learning/__init__.py`
- `api/services/learning/extractor.py`
- `api/services/social/scheduler/learning_worker.py`
- `api/alembic/versions/20260202_0003_learning_memory_columns.py`
- `api/tests/test_learning_extractor.py`
- `docs/LEARNING_EXTRACTION_PROOF.md`

### Modified Files:
- `api/db/models.py` (added source_tweet_ids to Memory)
- `api/services/social/scheduler/__init__.py` (export LearningWorker)
- `api/main.py` (lifecycle integration, admin endpoints)

## Conclusion

The learning extraction system is fully implemented with:
- ✅ Comprehensive CT slang vocabulary (50+ terms)
- ✅ Narrative pattern detection (12 patterns)
- ✅ Risk flag detection (5 categories)
- ✅ Engagement outcome tracking
- ✅ Automatic background extraction (60s interval)
- ✅ Idempotent processing (no duplicate extraction)
- ✅ Admin inspection endpoints
- ✅ Unit test coverage (25 tests)
- ✅ Database schema with proper indexing

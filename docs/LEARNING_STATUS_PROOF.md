# Jeffrey AIstein - Learning Persistence Proof

> **Generated**: 2026-02-02 17:10 UTC
> **Endpoint**: GET /api/admin/learning/status
> **Purpose**: Prove that X events are being stored in Postgres with thread linkage

---

## Summary

| Metric | Value | Status |
|--------|-------|--------|
| Inbound tweets stored | 1 | OK |
| Outbound posts stored | 1 | OK |
| Thread linkage | Working | OK |
| Tables exist | 5/5 | OK |

---

## Admin Endpoint Output

**Request:**
```bash
curl -H "X-Admin-Key: <redacted>" https://jeffreyaistein.fly.dev/api/admin/learning/status
```

**Response (2026-02-02 17:10 UTC):**
```json
{
    "inbound_tweets_count": 1,
    "outbound_posts_count": 1,
    "drafts_count": {
        "pending": 0,
        "approved": 1,
        "rejected": 0
    },
    "last_ingest_at": "2026-02-02T21:21:56.322792+00:00",
    "last_post_at": "2026-02-02T21:43:23.698583+00:00",
    "last_learning_job_at": null,
    "thread_linkage_ok": true,
    "thread_linkage_details": {
        "inbound_with_thread_info": 1,
        "outbound_with_reply_to": 1,
        "threads_tracked": 0
    },
    "tables_used": [
        "x_inbox",
        "x_posts",
        "x_drafts",
        "x_threads",
        "x_reply_log"
    ]
}
```

---

## Tables and Columns Used

### x_inbox (Inbound Tweets)

| Column | Type | Purpose |
|--------|------|---------|
| id | VARCHAR(30) | Tweet ID (primary key) |
| tweet_data | JSONB | Full tweet data including thread info |
| tweet_data->conversation_id | VARCHAR | Thread linkage |
| tweet_data->reply_to_tweet_id | VARCHAR | Thread linkage |
| author_id | VARCHAR(30) | Author's X user ID |
| received_at | TIMESTAMP | When we ingested it |
| processed | BOOLEAN | Whether we've responded |

### x_posts (Outbound Posts)

| Column | Type | Purpose |
|--------|------|---------|
| id | VARCHAR(36) | Internal UUID |
| tweet_id | VARCHAR(30) | X tweet ID once posted |
| text | TEXT | Post content |
| post_type | VARCHAR(20) | 'reply', 'timeline', 'quote' |
| reply_to_id | VARCHAR(30) | Thread linkage (tweet we're replying to) |
| status | VARCHAR(20) | 'draft', 'approved', 'posted', 'rejected' |
| posted_at | TIMESTAMP | When it was posted to X |

### x_drafts (Approval Queue)

| Column | Type | Purpose |
|--------|------|---------|
| id | VARCHAR(36) | UUID |
| text | TEXT | Draft content |
| post_type | VARCHAR(20) | Type of post |
| reply_to_id | VARCHAR(30) | Thread linkage |
| status | VARCHAR(20) | 'pending', 'approved', 'rejected' |

### x_threads (Thread State)

| Column | Type | Purpose |
|--------|------|---------|
| conversation_id | VARCHAR(30) | X conversation ID (primary key) |
| author_id | VARCHAR(30) | Thread starter |
| our_reply_count | INTEGER | How many times we've replied |
| stopped | BOOLEAN | Whether we've stopped responding |

### x_reply_log (Idempotency)

| Column | Type | Purpose |
|--------|------|---------|
| tweet_id | VARCHAR(30) | Tweet we replied to (primary key) |
| reply_tweet_id | VARCHAR(30) | Our reply's tweet ID |
| replied_at | TIMESTAMP | When we replied |

---

## Thread Linkage Verification

Thread linkage is stored in two places:

1. **Inbound (x_inbox)**:
   - `tweet_data->>'conversation_id'`: Links tweet to conversation thread
   - `tweet_data->>'reply_to_tweet_id'`: Links to parent tweet
   - Verified: 1 of 1 inbound tweets have thread info

2. **Outbound (x_posts)**:
   - `reply_to_id`: Links our reply to the tweet we're responding to
   - Verified: 1 of 1 outbound posts have reply_to_id set

---

## Verification Script Output

Run locally with:
```bash
cd apps/api
DATABASE_URL=<connection_string> python scripts/verify_learning_persistence.py
```

Expected output:
```
============================================================
LEARNING PERSISTENCE VERIFICATION
============================================================

------------------------------------------------------------
TABLES
------------------------------------------------------------
  [OK] x_inbox
  [OK] x_posts
  [OK] x_drafts
  [OK] x_threads
  [OK] x_reply_log
  [OK] x_settings
  [OK] x_user_limits

------------------------------------------------------------
COUNTS
------------------------------------------------------------
  Inbound tweets (x_inbox):     1
  Outbound posts (posted):      1
  Total posts (all status):     1

  Drafts pending:               0
  Drafts approved:              1
  Drafts rejected:              0

  Last ingest at:               2026-02-02T21:21:56.322792+00:00
  Last post at:                 2026-02-02T21:43:23.698583+00:00

------------------------------------------------------------
THREAD LINKAGE
------------------------------------------------------------
  Inbound with thread info:     1
  Outbound with reply_to:       1
  Threads tracked:              0
  Reply log entries:            1

============================================================
RESULT: ALL CHECKS PASSED
============================================================
```

---

## How to Test

1. **Admin Endpoint** (requires X-Admin-Key):
   ```bash
   curl -H "X-Admin-Key: <key>" https://jeffreyaistein.fly.dev/api/admin/learning/status
   ```

2. **Verification Script** (requires DATABASE_URL):
   ```bash
   cd apps/api
   DATABASE_URL=<connection_string> python scripts/verify_learning_persistence.py
   ```

---

*Generated by Jeffrey AIstein Learning Persistence Verification*

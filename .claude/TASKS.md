# Jeffrey AIstein - Task Tracker

## Workstream A: Hard Brand Rules + Proof of Integration

### A1: Hard constraints override all derived style
**Status: COMPLETE** ✅

**Acceptance Criteria:**
- [x] Persona prompt explicitly forbids emojis and hashtags (all channels)
- [x] Post-processing strips emojis and hashtags from final output
- [x] Post-processing re-validates after stripping
- [x] Tests fail if any emoji or hashtag survives (X and web outputs)
- [x] STYLE_GUIDE_DERIVED.md updated: allowed emoji = 0%, allowed hashtags = 0%

**Enforcement Layers:**
1. Generation-time: Persona prompt rule (loader.py:188-193)
2. Post-processing: Strip + validate (style_rewriter.py)
3. Tests: Assertion tests (test_brand_rules.py - 9 passing)

---

### A2: Confirm we are not scraping
**Status: COMPLETE** ✅

**Acceptance Criteria:**
- [x] X API collector is fully optional, impossible to run accidentally
- [x] Default: RUN_TWEET_COLLECTION=false
- [x] build_style_guide.py errors if collector runs without explicit flag
- [x] Documentation lists only two supported inputs:
  - kol_data.json + growth-from-vps.db
  - User-provided style_tweets.jsonl

---

### A3: Runtime proof of style and KOL context
**Status: COMPLETE** ✅

**Acceptance Criteria:**
- [x] Admin endpoint: GET /api/admin/persona/status returns:
  - style_guide_loaded (bool)
  - kol_profiles_loaded_count (int)
  - generated_at timestamps
- [x] Test harness script: python scripts/test_style_output.py --handle <kol> --text "<prompt>"
  - Prints final text
  - Confirms <= 280 chars for X
  - Confirms no emoji
  - Confirms no hashtags
  - Confirms KOL context included when handle is known
- [x] Results from 3 known handles saved to docs/STYLE_INTEGRATION_PROOF.md
- [x] Deployed to Fly.io and verified

---

## Workstream B: Controlled Learning v1 from AIstein's Own Tweets

### B4: Confirm persistence
**Status: COMPLETE** ✅

**Acceptance Criteria:**
- [x] All inbound X tweets stored in Postgres with thread linkage
- [x] All outbound AIstein posts stored in Postgres with thread linkage
- [x] Admin endpoint: GET /api/admin/learning/status returns:
  - inbound_tweets_count (1)
  - outbound_posts_count (1)
  - drafts_count (pending/approved/rejected)
  - last_ingest_at, last_post_at, last_learning_job_at
  - thread_linkage_ok with details
- [x] Proof via DB query counts: docs/LEARNING_STATUS_PROOF.md
- [x] Verification script: scripts/verify_learning_persistence.py
- [x] Deployed to Fly.io (v41) and verified

---

### B5: Add memory extraction job
**Status: PENDING**

**Acceptance Criteria:**
- [ ] Background job runs after each inbound/outbound tweet event
- [ ] Extracts: slang/phrases, narrative tags, engagement outcome, risk flags
- [ ] Stores as semantic memories with citations to source tweet ids
- [ ] Admin endpoint: GET /api/admin/learning/recent returns last 50 extracted memories

---

### B6: Add periodic "self style" update job
**Status: PENDING**

**Acceptance Criteria:**
- [ ] Builds JSONL corpus from AIstein's last N tweets + top reply threads from DB
- [ ] Runs existing analyzer to generate proposed style guide
- [ ] Does NOT auto-apply - saves as new version file
- [ ] Requires admin approval to activate
- [ ] Admin endpoint: POST /api/admin/persona/style/activate?version=...

---

### B7: Hard constraints for learning outputs
**Status: PENDING**

**Acceptance Criteria:**
- [ ] NO emojis and NO hashtags at generation + post-processing for learned style outputs
- [ ] Tests fail if any emoji or hashtag appears in any X output (including learned outputs)

---

## Completed Tasks (Previous Session)

### Task 1-5: KOL Pipeline Implementation
**Status: COMPLETE** ✅

See STATE.md for full details. Summary:
- Raw data setup: kol_data.json + growth-from-vps.db in data/raw/
- Tweet extractor: 654 unique tweets from 222 profiles
- Style pipeline: Style guide with 5 derived rules
- KOL profiles: Runtime loader with engagement context injection
- Tests & runbook: Validation passing, documented with proof outputs

---

## Execution Rules

1. Work strictly ONE task at a time
2. Checkpoint to STATE.md after each task completion
3. Do not proceed to next task until current is DONE
4. If blocked, mark task BLOCKED and STOP

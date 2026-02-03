# Jeffrey AIstein - KOL Pipeline Runbook

> **Last verified**: 2026-02-02
> **Status**: All checks passing

---

## Overview

This runbook documents the KOL (Key Opinion Leader) dataset pipeline that:
1. Extracts tweets from raw data files
2. Generates style analysis for X platform content
3. Creates KOL profile artifacts for persona-aware engagement

---

## Prerequisites

- Python 3.10+ with venv
- Raw data files in `apps/data/raw/`:
  - `kol_data.json` (~284KB, 222 profiles)
  - `growth-from-vps.db` (~20MB, SQLite database)

See `docs/RAW_DATA_SETUP.md` for instructions on obtaining these files.

---

## Quick Start

Run the complete pipeline:

```bash
cd apps/api
python scripts/extract_kol_tweets.py      # Extract tweets
python scripts/build_style_guide.py        # Build style guide
python scripts/extract_kol_profiles.py     # Extract KOL profiles
```

---

## Pipeline Steps

### Step 1: Extract Tweets

**Command:**
```bash
cd apps/api && python scripts/extract_kol_tweets.py
```

**Expected output:**
- File: `apps/data/style_tweets.jsonl`
- Line count: ~654 tweets
- Format: `{"text": "...", "handle": "...", "tweet_id": null, "created_at": "...", "source": "kol_data.json"}`

### Step 2: Build Style Guide

**Command:**
```bash
cd apps/api && python scripts/build_style_guide.py
```

**Expected outputs:**
- `apps/docs/STYLE_GUIDE_DERIVED.md` - Human-readable style patterns
- `apps/api/services/persona/style_guide.json` - Machine-readable rules

### Step 3: Extract KOL Profiles

**Command:**
```bash
cd apps/api && python scripts/extract_kol_profiles.py
```

**Expected outputs:**
- `apps/docs/knowledge/KOL_PROFILES_SUMMARY.md` - Profile summary by credibility tier
- `apps/api/services/persona/kol_profiles.json` - Runtime lookup data (50KB)

---

## Proof Outputs

### Current Pipeline Results (2026-02-02)

| Artifact | Path | Lines | Size |
|----------|------|-------|------|
| Tweet Dataset | `data/style_tweets.jsonl` | 654 | 141,036 bytes |
| Style Guide (MD) | `docs/STYLE_GUIDE_DERIVED.md` | 84 | 1,882 bytes |
| Style Guide (JSON) | `api/services/persona/style_guide.json` | 72 | 1,631 bytes |
| KOL Profiles (MD) | `docs/knowledge/KOL_PROFILES_SUMMARY.md` | 89 | 2,842 bytes |
| KOL Profiles (JSON) | `api/services/persona/kol_profiles.json` | 2,686 | 50,409 bytes |

### Pipeline Metrics

| Metric | Value |
|--------|-------|
| Profiles in dataset | 222 |
| Tweets extracted | 666 |
| Duplicates removed | 12 |
| Unique tweets written | 654 |
| CUBE references sanitized | 0 |

### Style Analysis Results

| Pattern | Value |
|---------|-------|
| Average tweet length | 112.1 chars |
| Median tweet length | 77 chars |
| Short tweets (<50 chars) | 33.0% |
| Emoji usage | 0.5% |
| Link usage | 6.4% |
| Hashtag usage | 2.3% |
| Question tweets | 9.9% |

### KOL Profile Distribution

| Credibility Tier | Count |
|------------------|-------|
| High (8-10) | 2 |
| Medium (5-7) | 220 |
| Low (1-4) | 0 |

---

## Tests

Run pipeline tests:

```bash
cd apps/api
python -m pytest tests/test_kol_pipeline.py -v
```

Alternatively, run validation without pytest:

```bash
cd apps/api
python -c "
from services.persona import get_kol_loader
loader = get_kol_loader()
print(f'Profiles: {loader.profile_count}')
print(f'Available: {loader.is_available()}')
"
```

**Test Classes:**

| Test Class | Description |
|------------|-------------|
| TestTweetExtractor | hash_text, sanitize, dedupe functions |
| TestStyleAnalyzer | JSONL parsing, rule generation |
| TestKOLProfileExtractor | trait extraction, risk flags |
| TestKOLProfileLoader | profile lookup, engagement context |

---

## File Locations

### Input Files (not in git)
- `apps/data/raw/kol_data.json` - Raw KOL profiles
- `apps/data/raw/growth-from-vps.db` - Growth database

### Generated Artifacts
- `apps/data/style_tweets.jsonl` - Extracted tweets
- `apps/docs/STYLE_GUIDE_DERIVED.md` - Style guide (markdown)
- `apps/api/services/persona/style_guide.json` - Style rules (JSON)
- `apps/docs/knowledge/KOL_PROFILES_SUMMARY.md` - KOL profiles (markdown)
- `apps/api/services/persona/kol_profiles.json` - KOL profiles (JSON)

### Scripts
- `apps/api/scripts/extract_kol_tweets.py` - Tweet extraction
- `apps/api/scripts/build_style_guide.py` - Complete style pipeline
- `apps/api/scripts/extract_kol_profiles.py` - KOL profile extraction

### Runtime Services
- `apps/api/services/persona/style_rewriter.py` - Style rewriting
- `apps/api/services/persona/kol_profiles.py` - KOL profile loader

---

## Runtime Integration

### Style Rewriter

The `StyleRewriter` loads `style_guide.json` at runtime:

```python
from services.persona import get_style_rewriter

rewriter = get_style_rewriter()
if rewriter.is_available():
    text = rewriter.rewrite_for_x(text)
```

### KOL Profile Lookup

The `KOLProfileLoader` provides handle-based lookups:

```python
from services.persona import get_kol_context

# Returns engagement context string or None
context = get_kol_context("rajgokal")
# "This is a respected voice in the space (credibility: 9/10)..."

# Or use the full loader
from services.persona import get_kol_loader
loader = get_kol_loader()
profile = loader.get_profile("frankdegods")
if profile:
    print(f"Credibility: {profile.credibility}")
    print(f"High cred: {profile.is_high_credibility}")
```

### Content Generator Integration

Reply generation automatically injects KOL context when replying to known handles:

```python
# In ContentGenerator._build_reply_user_prompt()
kol_context = get_kol_context(author_username)
if kol_context:
    parts.append(f"\n[KOL Context: {kol_context}]")
```

---

## Troubleshooting

### "kol_data.json not found"
Raw data files are not in git. See `docs/RAW_DATA_SETUP.md` for download instructions.

### "No module named 'structlog'"
Install dependencies:
```bash
pip install structlog
```

### "kol_profiles.json not found" at runtime
Run the profile extractor:
```bash
cd apps/api && python scripts/extract_kol_profiles.py
```

### Tests failing
Ensure you're running from the `apps/api` directory with dependencies installed.

---

## Data Flow

```
kol_data.json ──┬──▶ extract_kol_tweets.py ──▶ style_tweets.jsonl
                │                                     │
                │                                     ▼
                │                           build_style_guide.py
                │                                     │
                │                    ┌────────────────┴────────────────┐
                │                    ▼                                 ▼
                │          STYLE_GUIDE_DERIVED.md            style_guide.json
                │                                                      │
                │                                                      ▼
                │                                              StyleRewriter
                │
                └──▶ extract_kol_profiles.py ──┬──▶ KOL_PROFILES_SUMMARY.md
                                               │
                                               └──▶ kol_profiles.json
                                                           │
                                                           ▼
                                                   KOLProfileLoader
                                                           │
                                                           ▼
                                                   ContentGenerator
                                                   (X reply context)
```

---

*Generated for Jeffrey AIstein persona system*

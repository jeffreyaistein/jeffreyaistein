# Epstein Corpus Data Import Guide

> **Status**: Ready for Use
> **Last Updated**: 2026-02-03

This guide explains how to import Epstein corpus data for the AIstein persona's "casefile tone" feature.

---

## Overview

The Epstein corpus ingestion uses **offline-friendly** imports. You download dataset files manually and place them in the local `data/raw/epstein/` directory. The ingestion script reads from this local folder.

**No API keys required. No scraping. No network calls during ingestion.**

---

## Safety Constraints

All imported content passes through the `ContentSanitizer` which:

| Check | Action |
|-------|--------|
| Explicit sexual content | **BLOCKED** - document rejected |
| Minor-related explicit detail | **BLOCKED** - document rejected |
| Victim identifiers (Victim #1, Jane Doe, etc.) | **REDACTED** → `[VICTIM]` |
| Minor age references in sensitive context | **REDACTED** → `[AGE REDACTED]` |
| PII (phone, SSN, email) | **ANONYMIZED** |

Only documents that pass sanitization are stored. Raw text is stored only if fully safe.

---

## Directory Structure

```
apps/data/raw/epstein/
├── .gitkeep
├── kaggle/                 # Kaggle epstein-ranker dataset
│   └── .gitkeep
├── huggingface/            # Hugging Face FULL_EPSTEIN_INDEX
│   └── .gitkeep
└── epstein_docs/           # epstein-docs.github.io exports (optional)
    └── .gitkeep
```

All files in `data/raw/` are gitignored except `.gitkeep` files.

---

## Data Sources

### 1. Kaggle: epstein-ranker Dataset

**Source**: https://www.kaggle.com/datasets/[dataset-path]

**How to Download**:
1. Go to Kaggle and find the epstein-ranker dataset
2. Click "Download" (requires Kaggle account)
3. Extract the ZIP file
4. Copy contents to `apps/data/raw/epstein/kaggle/`

**Expected Files**:
```
kaggle/
├── documents.csv       # Main document metadata
├── rankings.csv        # Document relevance scores
└── content/            # Text content files (if present)
    └── *.txt
```

**Supported Formats**: CSV, JSON, JSONL, TXT

---

### 2. Hugging Face: FULL_EPSTEIN_INDEX

**Source**: https://huggingface.co/datasets/[dataset-path]

**How to Download**:

**Option A: Manual Download**
1. Go to the dataset page on Hugging Face
2. Click "Files and versions" tab
3. Download the data files (parquet, jsonl, or csv)
4. Copy to `apps/data/raw/epstein/huggingface/`

**Option B: Using huggingface-cli**
```bash
# Install if needed
pip install huggingface_hub

# Download dataset files
huggingface-cli download [dataset-name] --local-dir apps/data/raw/epstein/huggingface/
```

**Expected Files**:
```
huggingface/
├── train.parquet       # or train.jsonl
├── metadata.json       # Dataset info (optional)
└── README.md           # Dataset documentation
```

**Supported Formats**: Parquet, JSONL, CSV

---

### 3. epstein-docs.github.io (Optional)

**Source**: https://epstein-docs.github.io

This is a community analysis site with structured metadata. If you have OCR dumps or text exports:

1. Export or copy text content
2. Save as `.txt` or `.json` files
3. Copy to `apps/data/raw/epstein/epstein_docs/`

**Expected Files**:
```
epstein_docs/
├── flight_logs.txt
├── depositions.json
└── metadata.json
```

---

## Running the Ingestion

Once files are in place:

```bash
cd apps/api

# Ingest with default limit (200 docs)
python scripts/ingest_epstein_corpus.py --input-dir ../data/raw/epstein

# Ingest more documents
python scripts/ingest_epstein_corpus.py --input-dir ../data/raw/epstein --limit 500

# Dry run (no database writes)
python scripts/ingest_epstein_corpus.py --input-dir ../data/raw/epstein --dry-run

# Verbose output
python scripts/ingest_epstein_corpus.py --input-dir ../data/raw/epstein --verbose
```

---

## Ingestion Output

The script will output:
```
Epstein Corpus Ingestion
========================
Input directory: ../data/raw/epstein
Limit: 200 documents

Scanning sources...
  - kaggle: 150 files found
  - huggingface: 1 parquet file (2500 rows)
  - epstein_docs: 0 files found

Processing documents...
  [========================================] 200/200

Results:
  - Ingested: 180
  - Blocked (explicit): 15
  - Blocked (minor-related): 3
  - Skipped (duplicate): 2
  - Errors: 0

Ingestion complete. Run admin review before enabling.
```

---

## Admin Review & Activation

After ingestion, an admin must review and activate:

```bash
# Check ingestion status
curl -H "X-Admin-Key: $ADMIN_KEY" \
  https://jeffreyaistein.fly.dev/api/admin/corpus/epstein/status

# View sample sanitized summaries
curl -H "X-Admin-Key: $ADMIN_KEY" \
  "https://jeffreyaistein.fly.dev/api/admin/corpus/epstein/samples?limit=10"

# Enable EPSTEIN_MODE (after review)
curl -X POST -H "X-Admin-Key: $ADMIN_KEY" \
  https://jeffreyaistein.fly.dev/api/admin/corpus/epstein/enable

# Disable EPSTEIN_MODE
curl -X POST -H "X-Admin-Key: $ADMIN_KEY" \
  https://jeffreyaistein.fly.dev/api/admin/corpus/epstein/disable
```

---

## What Gets Stored

| Field | Description | Stored? |
|-------|-------------|---------|
| `source` | kaggle, huggingface, epstein_docs | Yes |
| `doc_id` | Stable content hash | Yes |
| `title` | Document title/filename | Yes |
| `doc_type` | deposition, flight_log, etc. | Yes |
| `sanitized_summary` | High-level summary (max 500 chars) | Yes |
| `raw_text` | Original text | Only if fully clean |
| `content_hash` | SHA256 for deduplication | Yes |
| `sanitization_status` | clean, redacted, blocked | Yes |

---

## How It's Used

When `EPSTEIN_MODE=true`:
1. Agent can search knowledge via `search_knowledge(source="epstein", query)`
2. Only `sanitized_summary` is returned (never raw text with redactions)
3. `casefile_tone.json` affects writing style (formal, investigative)
4. No specific allegations are generated - tone/framing only

When `EPSTEIN_MODE=false` (default):
- Corpus is not searchable
- Tone layer is not applied
- No impact on agent behavior

---

## Troubleshooting

### "No files found in input directory"

Ensure files are in the correct subdirectories:
```bash
ls -la apps/data/raw/epstein/kaggle/
ls -la apps/data/raw/epstein/huggingface/
```

### "All documents blocked"

The sanitizer may be rejecting all content. Check:
1. Is the dataset actually the Epstein corpus?
2. Are files in expected format (CSV, JSON, JSONL)?
3. Run with `--verbose` to see block reasons

### "Database connection error"

Ensure DATABASE_URL is set:
```bash
export DATABASE_URL="postgresql://..."
python scripts/ingest_epstein_corpus.py --input-dir ../data/raw/epstein
```

---

## Re-ingestion

The ingestion is **idempotent**. Re-running with the same files:
- Skips documents already in the database (matched by content_hash)
- Only processes new documents
- Updates metadata if source file changed

To force full re-ingestion:
```bash
python scripts/ingest_epstein_corpus.py --input-dir ../data/raw/epstein --force
```

---

## Security Reminders

1. **Never commit raw data files** - they're gitignored for a reason
2. **Review samples before enabling** - use admin endpoints
3. **Disable immediately if issues found** - POST to /disable endpoint
4. **No explicit content is ever stored** - sanitizer blocks it
5. **No victim identifiers stored** - redacted to `[VICTIM]`

---

*See also: `apps/api/docs/EPSTEIN_CORPUS_SAFETY.md` for full safety specification.*

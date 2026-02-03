# Epstein Corpus Ingestion - Safety Specification

> **Status**: ACTIVE
> **Last Updated**: 2026-02-03
> **Phase**: 11 (Corpus Ingestion)

---

## Purpose

This document defines the safety requirements and constraints for ingesting Epstein-related documents from public datasets. The goal is to extract **investigative tone patterns** and **entity relationship structures** for persona enhancement, while strictly excluding explicit or harmful content.

---

## Data Sources (Approved)

Only these public, pre-curated datasets are approved for ingestion:

| Source | Type | URL | Notes |
|--------|------|-----|-------|
| Hugging Face FULL_EPSTEIN_INDEX | Dataset | huggingface.co | Pre-indexed document metadata |
| epstein-docs.github.io | Analysis | epstein-docs.github.io | Structured metadata and analyses |
| Kaggle epstein-ranker | Dataset | kaggle.com | Scored/ranked document subset |

**PROHIBITED Sources:**
- Direct DOJ website scraping
- Court document direct downloads
- Any source requiring authentication
- Any source with unclear provenance

---

## Content Categories

### ALLOWED (May be stored and processed)

| Category | Examples | Storage |
|----------|----------|---------|
| Entity names | Person names, organization names, locations | Full text |
| Dates and timelines | Event dates, document dates | Full text |
| Document metadata | File names, page counts, classifications | Full text |
| Legal terminology | Deposition, testimony, subpoena, indictment | Full text |
| Investigative patterns | Interview structures, questioning styles | Summary only |
| Relationship types | "associated with", "employed by", "traveled to" | Anonymized |
| Tone markers | Formal legal language, investigative prose | Pattern only |

### BLOCKED (Must be sanitized/removed)

| Category | Detection Method | Action |
|----------|------------------|--------|
| Explicit sexual content | Keyword + pattern matching | REMOVE entirely |
| Minor-related explicit detail | Age references + context | REMOVE entirely |
| Victim names (minors) | Named entity + age check | REDACT to [MINOR] |
| Graphic abuse descriptions | Phrase pattern matching | REMOVE entirely |
| Personal identifiers (non-public) | PII patterns | REDACT |
| Medical/psychological details | Medical terminology + context | REMOVE |

---

## Sanitizer Requirements

### Hard Blocks (Non-Negotiable)

The sanitizer MUST block content containing:

```python
EXPLICIT_BLOCK_PATTERNS = [
    # Sexual content indicators
    r"\b(sexual|intercourse|penetrat|molest|abus[ei]|rape|assault)\b.*\b(minor|child|underage|teen|girl|boy)\b",
    r"\b(minor|child|underage|teen)\b.*\b(sexual|intercourse|penetrat|molest|abus[ei]|rape|assault)\b",

    # Explicit act descriptions
    r"\b(oral|anal|genital|breast|naked|nude|uncloth)\b",
    r"\b(masturbat|ejaculat|orgasm|erection)\b",

    # Victim identification patterns
    r"\b(victim\s+\d+|jane\s+doe\s+\d+|minor\s+\d+)\b",
    r"\bage[d]?\s+\d{1,2}\b.*\b(girl|boy|child|minor)\b",
]

EXPLICIT_BLOCK_KEYWORDS = [
    "sexually abused", "sexual abuse", "sexual assault",
    "sex trafficking", "sex slave", "sexual exploitation",
    "nude photograph", "naked photograph", "explicit image",
    "child pornography", "underage", "prepubescent",
]
```

### Sanitization Actions

| Match Type | Action | Log |
|------------|--------|-----|
| Hard block pattern | Reject entire document | `BLOCKED: [doc_id] hard_block_pattern` |
| Block keyword | Reject entire document | `BLOCKED: [doc_id] keyword:[word]` |
| Soft block pattern | Redact sentence | `REDACTED: [doc_id] line:[n]` |
| PII pattern | Replace with placeholder | `ANONYMIZED: [doc_id] type:[type]` |

### Output Constraints

All stored content MUST:
1. Contain NO explicit sexual content
2. Contain NO minor-identifying information in explicit context
3. Be limited to investigative/legal language patterns
4. Be stored as high-level summaries only (not raw transcripts)

---

## Storage Schema

### Table: `knowledge_documents`

```sql
CREATE TABLE knowledge_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(100) NOT NULL,           -- 'huggingface', 'kaggle', 'epstein_docs'
    doc_id VARCHAR(255) NOT NULL,           -- External document identifier
    title VARCHAR(500),                     -- Document title
    doc_type VARCHAR(50),                   -- 'deposition', 'flight_log', 'testimony', etc.
    raw_text TEXT,                          -- Original text (may be null if blocked)
    sanitized_summary TEXT,                 -- Sanitized high-level summary
    entity_count INTEGER,                   -- Count of extracted entities
    tone_markers JSONB,                     -- Extracted tone patterns
    sanitization_status VARCHAR(20),        -- 'clean', 'redacted', 'blocked'
    sanitization_log JSONB,                 -- Log of sanitization actions
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(source, doc_id)
);

CREATE INDEX idx_knowledge_docs_source ON knowledge_documents(source);
CREATE INDEX idx_knowledge_docs_status ON knowledge_documents(sanitization_status);
```

### Table: `corpus_ingestion_log`

```sql
CREATE TABLE corpus_ingestion_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL,
    source VARCHAR(100) NOT NULL,
    total_docs INTEGER,
    docs_clean INTEGER,
    docs_redacted INTEGER,
    docs_blocked INTEGER,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    error_message TEXT
);
```

---

## Admin Controls

### Activation Gating

The corpus integration is controlled by:

```env
EPSTEIN_MODE=false              # Master switch (default: disabled)
EPSTEIN_CORPUS_LOADED=false     # Set true after admin approval
```

### Required Approval Flow

1. Ingest documents with sanitizer (offline)
2. Admin reviews sample via `/api/admin/corpus/sample`
3. Admin explicitly activates via `/api/admin/corpus/activate`
4. `EPSTEIN_MODE` can then be enabled for specific contexts

### Admin Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/admin/corpus/status` | GET | Ingestion stats and status |
| `/api/admin/corpus/sample` | GET | View 10 random sanitized summaries |
| `/api/admin/corpus/activate` | POST | Approve corpus for use |
| `/api/admin/corpus/deactivate` | POST | Disable corpus usage |

---

## Tone Integration

### casefile_tone.json Structure

```json
{
    "meta": {
        "source": "sanitized_epstein_corpus",
        "generated_at": "2026-02-03T00:00:00Z",
        "doc_count": 100,
        "version": "1.0"
    },
    "lexicon": {
        "formal_terms": ["pursuant to", "aforementioned", "deposition"],
        "investigative_verbs": ["testified", "stated", "alleged", "confirmed"],
        "hedging_phrases": ["it appears that", "evidence suggests", "allegedly"],
        "transition_markers": ["furthermore", "moreover", "in addition"]
    },
    "sentence_patterns": {
        "declarative_ratio": 0.75,
        "avg_sentence_length": 22,
        "subordinate_clause_frequency": 0.35
    },
    "entity_types": ["person", "organization", "location", "date", "document"],
    "tone_profile": {
        "formality": "high",
        "objectivity": "high",
        "certainty": "hedged",
        "emotional_valence": "neutral"
    }
}
```

### Integration Rules

1. Tone is an **optional overlay**, NOT a replacement for CT voice
2. Only activated when `EPSTEIN_MODE=true`
3. Blends with existing style guide (does not override)
4. Never mentions source material directly
5. Uses investigative patterns for analytical responses only

---

## Testing Requirements

### Required Tests

```python
# test_corpus_sanitizer.py

def test_blocks_explicit_sexual_content():
    """Content with explicit sexual terms must be blocked."""

def test_blocks_minor_explicit_context():
    """Content describing minors in explicit context must be blocked."""

def test_allows_legal_terminology():
    """Legal/investigative terms alone should pass."""

def test_allows_entity_names():
    """Entity names without explicit context should pass."""

def test_redacts_victim_identifiers():
    """Victim identifiers should be redacted to [MINOR] or [VICTIM]."""

def test_logs_all_sanitization_actions():
    """All sanitization actions must be logged."""

def test_full_block_on_hard_pattern():
    """Hard block patterns reject entire document."""

def test_preserves_investigative_tone():
    """Investigative language patterns should be preserved."""
```

### Test Data

Test fixtures must use **synthetic content only** - never real case excerpts.

---

## Audit Trail

All corpus operations are logged:

| Event | Log Level | Fields |
|-------|-----------|--------|
| Document ingested | INFO | doc_id, source, status |
| Document blocked | WARN | doc_id, reason, pattern |
| Document redacted | INFO | doc_id, redaction_count |
| Corpus activated | WARN | admin_id, timestamp |
| Corpus deactivated | WARN | admin_id, timestamp |
| Tone file generated | INFO | version, doc_count |

---

## Emergency Procedures

### Immediate Disable

```bash
# Disable via env (requires restart)
fly secrets set EPSTEIN_MODE=false -a jeffreyaistein

# Or via admin endpoint (no restart)
curl -X POST -H "X-Admin-Key: [KEY]" \
  https://jeffreyaistein.fly.dev/api/admin/corpus/deactivate
```

### Content Removal

If problematic content is discovered:
1. Immediately disable corpus (`EPSTEIN_MODE=false`)
2. Identify affected documents via `sanitization_log`
3. Delete from `knowledge_documents` table
4. Re-run sanitizer with updated patterns
5. Require fresh admin approval before re-activation

---

## Compliance Notes

- All source datasets are publicly available
- No direct court record scraping
- No victim re-identification attempts
- Content used solely for linguistic pattern extraction
- No explicit content stored or transmitted
- Admin approval required before any production use

---

*This safety specification must be followed for all Phase 11 implementation.*

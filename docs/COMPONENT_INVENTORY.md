# Jeffrey AIstein - Component Inventory

**Last Updated:** 2026-02-03

A complete inventory of all major components, modules, and their relationships.

---

## Web (UI/Components/Hooks)

### Pages

| File | Purpose | Inputs | Outputs | Dependencies |
|------|---------|--------|---------|--------------|
| `web/src/app/page.tsx` | Main landing page | None | UI | All components |
| `web/src/app/layout.tsx` | Root layout, fonts, metadata | Children | HTML wrapper | tailwind.config |

**How to test:** `cd apps/web && npm run dev` → Open http://localhost:3000

---

### Components

| File | Purpose | Props | Used By | Env Vars |
|------|---------|-------|---------|----------|
| `ChatInterface.tsx` | Combined chat + hologram UI | None | `page.tsx` | `NEXT_PUBLIC_API_BASE_URL` |
| `ChatBox.tsx` | Standalone chat component | None | (legacy) | `NEXT_PUBLIC_API_BASE_URL` |
| `HologramAvatar.tsx` | Avatar mode switcher | `state`, `amplitude` | `ChatInterface` | `NEXT_PUBLIC_AVATAR_MODE` |
| `HologramAvatar3D.tsx` | GLB mesh hologram | `state`, `amplitude` | `HologramAvatar` | None |
| `HologramCardAvatar.tsx` | 2.5D card hologram | `state`, `amplitude` | `HologramAvatar` | None |
| `HologramProjectedFace.tsx` | Face PNG projection | `state`, `amplitude` | `HologramAvatar` | `NEXT_PUBLIC_AVATAR_DEBUG` |
| `HologramPlaceholder.tsx` | Static placeholder | None | (fallback) | None |
| `DigitalRain.tsx` | Matrix rain background | None | `page.tsx` | None |
| `TokenPanel.tsx` | Token metrics display | None | `page.tsx` | `NEXT_PUBLIC_API_BASE_URL` |
| `StatsPanel.tsx` | Agent stats display | None | `page.tsx` | `NEXT_PUBLIC_API_BASE_URL` |
| `ContractSection.tsx` | Contract address display | None | `page.tsx` | None |
| `SocialLinks.tsx` | X/Telegram links | `showLabels` | `page.tsx` | None |
| `DebugPanel.tsx` | Debug info overlay | `connectionStatus`, `ttsDebugInfo` | `ChatInterface` | `NEXT_PUBLIC_DEBUG` |

**How to test:** `npm run build` in `apps/web/` should pass without errors.

---

### Hooks

| File | Purpose | Returns | Used By | Env Vars |
|------|---------|---------|---------|----------|
| `useChat.ts` | WebSocket chat + session management | `{messages, sendMessage, connectionStatus}` | `ChatInterface` | `NEXT_PUBLIC_API_BASE_URL` |
| `useTTS.ts` | TTS playback + AudioContext | `{voiceEnabled, speak, amplitude, debugInfo}` | `ChatInterface` | `NEXT_PUBLIC_API_BASE_URL` |
| `useAvatarDriver.ts` | Avatar state machine | `{state, amplitude}` | `HologramSection` | None |

**How to test:** Hooks are tested via component usage. Check browser console for `[useChat]` and `[useTTS]` logs.

---

### Config

| File | Purpose | Exports |
|------|---------|---------|
| `web/src/config/brand.ts` | Brand constants (name, version, tagline, links) | `brand` object |
| `web/tailwind.config.ts` | Tailwind theme (matrix colors) | Config |
| `web/tsconfig.json` | TypeScript config | N/A |
| `web/package.json` | Dependencies, scripts | N/A |

---

## API Routes (FastAPI Endpoints)

All endpoints defined in `api/main.py`.

### Public Endpoints

| Endpoint | Method | Handler | Purpose | Test Command |
|----------|--------|---------|---------|--------------|
| `/` | GET | `root()` | Health ping | `curl https://jeffreyaistein.fly.dev/` |
| `/health` | GET | `health()` | Basic health | `curl .../health` |
| `/health/ready` | GET | `ready()` | Full dependency check | `curl .../health/ready` |
| `/health/live` | GET | `live()` | Liveness probe | `curl .../health/live` |
| `/api/session` | POST | `init_session()` | Create session | `curl -X POST .../api/session` |
| `/api/info` | GET | `info()` | API info | `curl .../api/info` |
| `/api/conversations` | GET | `list_conversations()` | List conversations | (requires session cookie) |
| `/api/conversations` | POST | `create_conversation()` | Create conversation | (requires session cookie) |
| `/api/conversations/{id}` | GET | `get_conversation()` | Get with messages | (requires session cookie) |
| `/api/chat` | POST | `chat_sse()` | SSE chat stream | (requires session cookie) |
| `/api/tts` | POST | `text_to_speech()` | TTS synthesis | `curl -X POST .../api/tts -d '{"text":"hello"}'` |
| `/api/tts/status` | GET | `tts_status()` | TTS config status | `curl .../api/tts/status` |
| `/api/token/metrics` | GET | `get_token_metrics()` | Token data (placeholder) | `curl .../api/token/metrics` |
| `/api/stats/agent` | GET | `get_agent_stats()` | Agent stats (placeholder) | `curl .../api/stats/agent` |

### WebSocket Endpoints

| Endpoint | Handler | Purpose |
|----------|---------|---------|
| `/ws/chat` | `websocket_chat()` | Streaming chat |
| `/ws/token` | `websocket_token()` | Token updates (placeholder) |
| `/ws/metrics` | `websocket_metrics()` | Metrics updates (placeholder) |

### Admin Endpoints (require `X-Admin-Key` header)

| Endpoint | Method | Purpose | Test Command |
|----------|--------|---------|--------------|
| `/api/admin/social/status` | GET | X bot status | `curl -H "X-Admin-Key: $KEY" .../api/admin/social/status` |
| `/api/admin/social/drafts` | GET | List drafts | `curl -H "X-Admin-Key: $KEY" .../api/admin/social/drafts` |
| `/api/admin/social/drafts/{id}/approve` | POST | Approve draft | (see OPS guide) |
| `/api/admin/social/drafts/{id}/reject` | POST | Reject draft | (see OPS guide) |
| `/api/admin/social/settings` | GET | Get settings | `curl -H "X-Admin-Key: $KEY" .../api/admin/social/settings` |
| `/api/admin/social/settings` | PATCH | Update settings | (see OPS guide) |
| `/api/admin/kill_switch` | GET/POST | Safe mode status | (see OPS guide) |
| `/api/admin/persona/status` | GET | Persona status | `curl -H "X-Admin-Key: $KEY" .../api/admin/persona/status` |
| `/api/admin/persona/rebuild` | POST | Rebuild persona | (see OPS guide) |
| `/api/admin/persona/settings` | PATCH | Update blend settings | (see OPS guide) |
| `/api/admin/persona/style/versions` | GET | List style versions | `curl -H "X-Admin-Key: $KEY" .../api/admin/persona/style/versions` |
| `/api/admin/persona/style/activate` | POST | Activate version | (see OPS guide) |
| `/api/admin/persona/style/rollback` | POST | Rollback version | (see OPS guide) |
| `/api/admin/persona/style/status` | GET | Style rewriter status | `curl -H "X-Admin-Key: $KEY" .../api/admin/persona/style/status` |
| `/api/admin/persona/style/generate` | POST | Manual proposal | (see OPS guide) |
| `/api/admin/learning/status` | GET | Learning stats | `curl -H "X-Admin-Key: $KEY" .../api/admin/learning/status` |
| `/api/admin/learning/recent` | GET | Recent memories | `curl -H "X-Admin-Key: $KEY" .../api/admin/learning/recent` |
| `/api/admin/corpus/epstein/status` | GET | Corpus status | `curl -H "X-Admin-Key: $KEY" .../api/admin/corpus/epstein/status` |
| `/api/admin/corpus/epstein/samples` | GET | Corpus samples | (see OPS guide) |
| `/api/admin/corpus/epstein/enable` | POST | Enable EPSTEIN_MODE | (see OPS guide) |
| `/api/admin/corpus/epstein/disable` | POST | Disable EPSTEIN_MODE | (see OPS guide) |

---

## Services

### Chat Service

| File | Class/Function | Purpose | Dependencies |
|------|----------------|---------|--------------|
| `services/chat/handler.py` | `ChatService` | Orchestrates LLM + persona + moderation | LLM, Persona, Moderation |
| `services/chat/handler.py` | `ChatContext` | Request context dataclass | None |

**Env Vars:** `ANTHROPIC_API_KEY`, `LLM_MODEL`

---

### LLM Service

| File | Class | Purpose | Env Vars |
|------|-------|---------|----------|
| `services/llm/base.py` | `LLMProvider` (ABC) | Base interface | None |
| `services/llm/anthropic_provider.py` | `AnthropicProvider` | Claude API client | `ANTHROPIC_API_KEY`, `LLM_MODEL` |
| `services/llm/mock_provider.py` | `MockProvider` | Testing mock | None |
| `services/llm/factory.py` | `get_llm_provider()` | Factory function | `LLM_PROVIDER` |

**How to test:** `pytest api/tests/test_health.py -v`

---

### Persona Service

| File | Class/Function | Purpose | Dependencies |
|------|----------------|---------|--------------|
| `services/persona/loader.py` | `load_persona()` | Load persona from JSON | `persona.json` files |
| `services/persona/loader.py` | `get_system_prompt()` | Build system prompt | Style, KOL profiles |
| `services/persona/style_rewriter.py` | `StyleRewriter` | Post-process for brand rules | `style_guide.json` |
| `services/persona/kol_profiles.py` | `KOLLoader` | Load KOL context | `kol_profiles.json` |
| `services/persona/blender.py` | `build_and_save_persona()` | Compile persona from components | Tone, style, base |

**Key Files:**
- `services/persona/style_guide.json` - Derived style rules
- `services/persona/kol_profiles.json` - KOL engagement context
- `services/persona/epstein_tone.json` - Casefile parody tone (optional)

**How to test:** `python scripts/test_style_output.py --handle elonmusk --text "test"`

---

### Moderation Service

| File | Function | Purpose |
|------|----------|---------|
| `services/moderation/checker.py` | `check_input()` | Filter harmful input |
| `services/moderation/checker.py` | `check_output()` | Detect persona breaks |
| `services/moderation/checker.py` | `get_safe_response()` | Return safe fallback |

**How to test:** `pytest api/tests/test_brand_rules.py -v`

---

### TTS Service

| File | Class | Purpose | Env Vars |
|------|-------|---------|----------|
| `services/tts.py` | `ElevenLabsTTS` | ElevenLabs API client | `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` |
| `services/tts.py` | `sanitize_text_for_tts()` | Strip emojis/hashtags | None |
| `services/tts.py` | `is_tts_configured()` | Check config status | `ENABLE_TTS` |

**How to test:** `curl -X POST .../api/tts -d '{"text":"Hello"}' -o test.mp3`

---

### Social/X Bot Service

| File | Class/Function | Purpose | Env Vars |
|------|----------------|---------|----------|
| `services/social/providers/real.py` | `RealXProvider` | tweepy X API client | `X_*` credentials |
| `services/social/providers/mock.py` | `MockXProvider` | Testing mock | None |
| `services/social/scorer.py` | `TweetScorer` | Score tweet quality | `X_QUALITY_THRESHOLD` |
| `services/social/content.py` | `ContentGenerator` | Generate replies/posts | LLM, Persona |
| `services/social/context.py` | `ContextBuilder` | Build reply context | KOL profiles |
| `services/social/storage/postgres.py` | `Postgres*Repository` | DB persistence | `DATABASE_URL` |

**How to test:** `python scripts/verify_x_credentials.py`

---

### Learning Service

| File | Class | Purpose | Env Vars |
|------|-------|---------|----------|
| `services/learning/extractor.py` | `LearningExtractor` | Extract memories from tweets | `ANTHROPIC_API_KEY` |

**How to test:** `curl -H "X-Admin-Key: $KEY" .../api/admin/learning/recent`

---

### Corpus Service

| File | Class/Function | Purpose |
|------|----------------|---------|
| `services/corpus/sanitizer.py` | `ContentSanitizer` | Block names, PII, explicit |
| `services/corpus/epstein/ingest.py` | `ingest_document()` | Store sanitized docs |
| `services/corpus/epstein/readers.py` | `read_*()` | Parse PDF/JSON sources |
| `services/corpus/epstein/tone_builder.py` | `build_and_save_tone()` | Extract tone patterns |

**How to test:** `python scripts/ingest_epstein_corpus.py --dry-run`

---

### Locking Service

| File | Class | Purpose | Env Vars |
|------|-------|---------|----------|
| `services/locking/redis_lock.py` | `RedisLock` | Distributed lock for workers | `REDIS_URL` |

**How to test:** `curl .../health/ready` (checks Redis connectivity)

---

## Workers/Schedulers

All defined in `api/services/social/scheduler/`.

| File | Class | Trigger | Interval | Purpose | Env Vars |
|------|-------|---------|----------|---------|----------|
| `ingestion.py` | `IngestionLoop` | `X_BOT_ENABLED=true` | 45s | Poll X mentions | `X_POLL_INTERVAL_SECONDS` |
| `timeline_poster.py` | `TimelinePosterLoop` | `X_BOT_ENABLED=true` | 3h | Organic posts | `X_TIMELINE_POST_INTERVAL_SECONDS` |
| `learning_worker.py` | `LearningWorker` | `X_BOT_ENABLED=true` | 5m | Extract memories | None |
| `self_style_worker.py` | `SelfStyleWorker` | `SELF_STYLE_ENABLED=true` | 24h | Style proposals | `SELF_STYLE_*`, `REDIS_URL` |
| `clock.py` | `Clock` | N/A | N/A | Time abstraction for testing | None |

**How to test:** `curl -H "X-Admin-Key: $KEY" .../api/admin/social/status`

---

## DB Models/Migrations

### Models (`api/db/models.py`)

| Table | Model Class | Purpose |
|-------|-------------|---------|
| `users` | `User` | Anonymous/authenticated users |
| `conversations` | `Conversation` | Chat threads |
| `messages` | `Message` | Chat messages |
| `events` | `Event` | Episodic event log |
| `memories` | `Memory` | Semantic memories (with pgvector) |
| `summaries` | `Summary` | Compressed context |
| `retrieval_traces` | `RetrievalTrace` | Memory retrieval audit |
| `token_metrics` | `TokenMetrics` | Current token data |
| `token_ath` | `TokenATH` | ATH tracking |
| `token_snapshots` | `TokenSnapshot` | Historical snapshots |
| `agent_stats` | `AgentStats` | Agent statistics |
| `social_inbox` | `SocialInbox` | X mentions (legacy) |
| `social_posts` | `SocialPost` | X posts (legacy) |
| `social_drafts` | `SocialDraft` | Approval queue (legacy) |
| `knowledge_documents` | `KnowledgeDocument` | Ingested corpus |
| `tool_calls` | `ToolCall` | Tool call audit |

### Migrations (`api/alembic/versions/`)

| File | Purpose |
|------|---------|
| `20260201_0001_initial_schema.py` | Core tables |
| `20260202_0002_x_bot_storage_tables.py` | X bot tables (`x_inbox`, `x_posts`, etc.) |
| `20260202_0003_learning_memory_columns.py` | Learning columns on X tables |
| `20260203_0004_style_guide_versions.py` | Style versioning |
| `20260203_0005_knowledge_documents.py` | Knowledge corpus |

**How to apply:** `cd api && alembic upgrade head`

---

## Scripts/CLIs

| Script | Purpose | Key Args | Example |
|--------|---------|----------|---------|
| `scripts/ingest_epstein_corpus.py` | Ingest DOJ documents | `--sources`, `--dry-run` | `python scripts/ingest_epstein_corpus.py --sources doj_releases` |
| `scripts/build_style_guide.py` | Build style from KOL tweets | `--input`, `--output` | `python scripts/build_style_guide.py` |
| `scripts/propose_style_guide.py` | Generate self-style proposal | `--days`, `--limit` | `python scripts/propose_style_guide.py --days 30` |
| `scripts/test_style_output.py` | Test persona output | `--handle`, `--text` | `python scripts/test_style_output.py --text "test"` |
| `scripts/verify_learning_persistence.py` | Verify DB persistence | None | `python scripts/verify_learning_persistence.py` |
| `scripts/verify_x_credentials.py` | Test X API credentials | None | `python scripts/verify_x_credentials.py` |
| `scripts/build_self_style_corpus.py` | Build corpus from x_posts | `--days`, `--limit` | `python scripts/build_self_style_corpus.py` |
| `scripts/extract_kol_tweets.py` | Extract tweets from kol_data | None | `python scripts/extract_kol_tweets.py` |
| `scripts/generate_kol_profiles.py` | Generate KOL profiles | None | `python scripts/generate_kol_profiles.py` |

---

## Tests

| File | Coverage Area |
|------|---------------|
| `tests/test_health.py` | Health endpoints |
| `tests/test_brand_rules.py` | Emoji/hashtag enforcement |
| `tests/test_style_rewriter_loader.py` | Style loading |
| `tests/test_style_version_endpoints.py` | Version management |
| `tests/test_social_storage.py` | X bot storage |
| `tests/test_social_scorer.py` | Tweet scoring |
| `tests/test_x_provider.py` | X API provider |
| `tests/test_learning_extractor.py` | Memory extraction |
| `tests/test_corpus_sanitizer.py` | Content sanitization |
| `tests/test_tone_builder.py` | Tone extraction |
| `tests/test_redis_lock.py` | Leader locking |
| `tests/test_scheduler.py` | Scheduler loops |
| `tests/test_self_style_*.py` | Self-style pipeline |
| `tests/test_context_builder.py` | Reply context |
| `tests/test_kol_pipeline.py` | KOL profiles |
| `tests/test_tools.py` | Tool registry |

**Run all:** `cd api && pytest -v`

---

## Docs/Runbooks/Proofs

### Setup Guides
| File | Purpose |
|------|---------|
| `docs/RAW_DATA_SETUP.md` | Setup data/raw/ directory |
| `docs/DOMAIN_SETUP.md` | Domain configuration |
| `docs/KOL_PIPELINE_RUNBOOK.md` | KOL profile generation |
| `docs/SELF_STYLE_RUNBOOK.md` | Self-style pipeline |
| `docs/EPSTEIN_DATA_IMPORT.md` | Corpus ingestion |
| `web/docs/TTS_SETUP.md` | TTS configuration |
| `web/docs/AVATAR_MODE.md` | Avatar mode selection |
| `web/docs/WEB_DEPLOY.md` | Vercel deployment |

### Proof Documents
| File | Purpose |
|------|---------|
| `docs/STYLE_INTEGRATION_PROOF.md` | Style system verified |
| `docs/LEARNING_STATUS_PROOF.md` | Learning persistence verified |
| `docs/LEARNING_EXTRACTION_PROOF.md` | Memory extraction verified |
| `docs/LEARNING_PROD_PROOF.md` | Production learning verified |
| `docs/SELF_STYLE_SCHEDULER_PROOF.md` | Self-style worker verified |
| `docs/PERSONA_BLEND_PROOF.md` | Persona blending verified |
| `docs/EPSTEIN_INGEST_PROOF.md` | Corpus ingestion verified |
| `docs/TTS_PROOF.md` | TTS playback verified |
| `docs/X_LIVE_SMOKE_TEST.md` | X bot smoke test |
| `docs/X_LIVE_RUN_RESULTS.md` | X bot live results |

### Reference
| File | Purpose |
|------|---------|
| `docs/BRAND.md` | Brand guidelines |
| `docs/STYLE_GUIDE_DERIVED.md` | Derived style rules |
| `docs/PROD_CHECKLIST.md` | Production checklist |
| `docs/OPS_DASHBOARD.md` | Operations dashboard |
| `docs/RUNBOOK_3DAY.md` | 3-day launch runbook |
| `api/docs/EPSTEIN_CORPUS_SAFETY.md` | Corpus safety rules |
| `web/docs/WEB_CHAT_PROD_DEBUG.md` | Chat debugging |

### Knowledge Base
| File | Purpose |
|------|---------|
| `docs/knowledge/CT_VOCABULARY.md` | CT vocabulary reference |
| `docs/knowledge/TRENCHES_CULTURE.md` | Trenches culture reference |
| `docs/knowledge/KOL_INTELLIGENCE.md` | KOL engagement intel |
| `docs/knowledge/KOL_PROFILES_SUMMARY.md` | KOL profiles summary |

---

## Dead Code / Placeholders

| File/Component | Status | Notes |
|----------------|--------|-------|
| `ChatBox.tsx` | Legacy | Replaced by `ChatInterface.tsx` |
| `SocialInbox`, `SocialPost`, `SocialDraft` models | Legacy | Replaced by `x_*` tables |
| `/api/token/metrics` | Placeholder | Returns zeroes |
| `/api/stats/agent` | Placeholder | Returns zeroes |
| `/ws/token`, `/ws/metrics` | Placeholder | Stubbed endpoints |
| `services/tools/*` | Partial | Tool registry exists but not fully wired |

---

## File Count Summary

| Category | Count |
|----------|-------|
| Web Components | 15 |
| Web Hooks | 3 |
| API Services | 25+ modules |
| Workers | 4 |
| Scripts | 9 |
| DB Migrations | 5 |
| Tests | 20+ |
| Docs | 30+ |

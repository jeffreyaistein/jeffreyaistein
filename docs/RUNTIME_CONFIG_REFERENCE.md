# Jeffrey AIstein - Runtime Configuration Reference

**Last Updated:** 2026-02-03

This document lists every environment variable and runtime setting in the system.

---

## Configuration Layers

| Layer | Platform | Timing | Persistence |
|-------|----------|--------|-------------|
| **Backend Env Vars** | Fly.io Secrets | Runtime | Until next deploy |
| **Frontend Env Vars** | Vercel Env | Build-time | Baked into JS bundle |
| **Runtime Settings** | Postgres `x_settings` | Immediate | Persisted across restarts |

---

## Backend Environment Variables (Fly.io)

Set via `fly secrets set KEY=value` or Fly.io dashboard.

### Core Settings

| Variable | Default | Description | Production Value |
|----------|---------|-------------|------------------|
| `DEBUG` | `false` | Enable debug logging | `false` |
| `LOG_LEVEL` | `info` | Log level (debug/info/warning/error) | `info` |

### Database

| Variable | Default | Description | Production Value |
|----------|---------|-------------|------------------|
| `DATABASE_URL` | `postgresql://aistein:...@localhost/aistein` | Postgres connection string | Fly Postgres internal URL |

### Redis

| Variable | Default | Description | Production Value |
|----------|---------|-------------|------------------|
| `REDIS_URL` | `redis://localhost:6379/0` | Upstash Redis URL | Upstash connection string |

### LLM Providers

| Variable | Default | Description | Production Value |
|----------|---------|-------------|------------------|
| `ANTHROPIC_API_KEY` | `""` | Anthropic API key | `sk-ant-...` (required) |
| `OPENAI_API_KEY` | `""` | OpenAI API key (for embeddings) | `sk-...` (optional) |
| `LLM_PROVIDER` | `anthropic` | LLM provider (anthropic/openai) | `anthropic` |
| `LLM_MODEL` | `claude-3-5-sonnet-20241022` | Model ID for chat | Keep default or upgrade |
| `EMBEDDING_PROVIDER` | `openai` | Embedding provider | `openai` |
| `EMBEDDING_MODEL` | `text-embedding-ada-002` | Embedding model | Keep default |

### TTS (ElevenLabs)

| Variable | Default | Description | Production Value |
|----------|---------|-------------|------------------|
| `TTS_PROVIDER` | `elevenlabs` | TTS provider | `elevenlabs` |
| `ELEVENLABS_API_KEY` | `""` | ElevenLabs API key | Required for TTS |
| `ELEVENLABS_VOICE_ID` | `""` | Voice ID for synthesis | Jeffrey voice ID |
| `ELEVENLABS_MODEL_ID` | `eleven_monolingual_v1` | TTS model | Keep default |
| `ELEVENLABS_OUTPUT_FORMAT` | `mp3_44100_128` | Audio format | Keep default |
| `TTS_MAX_TEXT_LENGTH` | `1000` | Max chars per request | `1000` |
| `TTS_RATE_LIMIT_PER_MINUTE` | `10` | Rate limit per IP | `10` |

### X (Twitter) Bot

| Variable | Default | Description | Production Value |
|----------|---------|-------------|------------------|
| `X_API_KEY` | `""` | X API key | From X Developer Portal |
| `X_API_SECRET` | `""` | X API secret | From X Developer Portal |
| `X_ACCESS_TOKEN` | `""` | OAuth access token | From X Developer Portal |
| `X_ACCESS_TOKEN_SECRET` | `""` | OAuth access secret | From X Developer Portal |
| `X_BEARER_TOKEN` | `""` | Bearer token for API v2 | From X Developer Portal |
| `X_BOT_USER_ID` | `""` | Bot's X user ID | @JeffreyAIstein user ID |
| `X_BOT_ENABLED` | `false` | Enable X bot workers | `false` until ready |
| `SAFE_MODE` | `false` | Block all posting | `false` (use runtime toggle) |
| `APPROVAL_REQUIRED` | `true` | Require admin approval | `true` (always) |
| `X_HOURLY_POST_LIMIT` | `5` | Max posts per hour | `5` |
| `X_DAILY_POST_LIMIT` | `20` | Max posts per day | `20` |

### Self-Style Pipeline

| Variable | Default | Description | Production Value |
|----------|---------|-------------|------------------|
| `SELF_STYLE_ENABLED` | `false` | Enable auto style proposals | `false` until X bot active |
| `SELF_STYLE_INTERVAL_HOURS` | `24` | Hours between runs | `24` |
| `SELF_STYLE_MIN_TWEETS` | `25` | Min tweets required | `25` |
| `SELF_STYLE_MAX_TWEETS` | `500` | Max tweets to analyze | `500` |
| `SELF_STYLE_DAYS` | `30` | Look-back window | `30` |
| `SELF_STYLE_INCLUDE_REPLIES` | `true` | Include replies | `true` |

### Token Data

| Variable | Default | Description | Production Value |
|----------|---------|-------------|------------------|
| `TOKEN_DATA_PROVIDER` | `dexscreener` | Price data source | `dexscreener` |
| `TOKEN_CONTRACT_ADDRESS` | `""` | Solana contract address | Token contract |
| `TOKEN_CHAIN` | `solana` | Blockchain | `solana` |
| `COINGECKO_API_KEY` | `""` | CoinGecko API key | Optional |
| `HELIUS_API_KEY` | `""` | Helius RPC key | Optional |
| `HELIUS_RPC_URL` | `""` | Helius RPC URL | Optional |

### Security

| Variable | Default | Description | Production Value |
|----------|---------|-------------|------------------|
| `SECRET_KEY` | `CHANGE_THIS` | App secret key | Random 64+ char string |
| `SESSION_SECRET` | `CHANGE_THIS` | Session signing key | Random 64+ char string |
| `ADMIN_API_KEY` | `CHANGE_THIS` | Admin endpoint auth | Random 64+ char string |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed CORS origins | `https://jeffreyaistein.vercel.app` |

### Rate Limiting

| Variable | Default | Description | Production Value |
|----------|---------|-------------|------------------|
| `CHAT_RATE_LIMIT_PER_MINUTE` | `20` | Chat messages/min | `20` |
| `API_RATE_LIMIT_PER_MINUTE` | `100` | API requests/min | `100` |

### Feature Flags

| Variable | Default | Description | Production Value |
|----------|---------|-------------|------------------|
| `ENABLE_TTS` | `true` | Enable TTS endpoint | `true` |
| `ENABLE_X_BOT` | `false` | Enable X bot feature | `false` until ready |
| `ENABLE_IMAGE_GEN` | `true` | Enable image generation | `true` |
| `ENABLE_TOKEN_DATA` | `true` | Enable token data | `true` |

### Monitoring

| Variable | Default | Description | Production Value |
|----------|---------|-------------|------------------|
| `SENTRY_DSN` | `""` | Sentry error tracking | Sentry project DSN |

### Celery (Not Currently Used)

| Variable | Default | Description | Production Value |
|----------|---------|-------------|------------------|
| `CELERY_BROKER_URL` | `redis://localhost:6379/1` | Celery broker | Not used |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/2` | Celery results | Not used |

---

## Frontend Environment Variables (Vercel)

Set in Vercel dashboard > Project > Settings > Environment Variables.

**Important:** These are **build-time** variables. Changes require a new deployment.

### Required

| Variable | Default | Description | Production Value |
|----------|---------|-------------|------------------|
| `NEXT_PUBLIC_API_BASE_URL` | None | Backend API base URL | `https://jeffreyaistein.fly.dev` |

### Token Display

| Variable | Default | Description | Production Value |
|----------|---------|-------------|------------------|
| `NEXT_PUBLIC_CONTRACT_ADDRESS` | `""` | Token contract address | `69WBpgbrydCLSn3zyqAxzgrj2emGHLQJy9VdB1Xpump` |
| `NEXT_PUBLIC_SOLANA_EXPLORER_BASE_URL` | `https://solscan.io/token` | Explorer URL | Keep default |

### Avatar

| Variable | Default | Description | Production Value |
|----------|---------|-------------|------------------|
| `NEXT_PUBLIC_AVATAR_MODE` | `glb` | Avatar rendering mode | `glb` or `card` |

### Debug (Development Only)

| Variable | Default | Description | Production Value |
|----------|---------|-------------|------------------|
| `NEXT_PUBLIC_DEBUG` | `false` | Show chat debug panel | `false` |
| `NEXT_PUBLIC_AVATAR_DEBUG` | `false` | Show avatar debug overlay | `false` |

### Legacy (Deprecated)

| Variable | Default | Description | Production Value |
|----------|---------|-------------|------------------|
| `NEXT_PUBLIC_API_URL` | None | Legacy REST URL | Don't use, use `NEXT_PUBLIC_API_BASE_URL` |
| `NEXT_PUBLIC_WS_URL` | None | Legacy WebSocket URL | Don't use, use `NEXT_PUBLIC_API_BASE_URL` |

---

## Runtime Settings (Database)

These settings are stored in the `x_settings` table and can be changed via admin API without restart.

**Priority:** Database values override environment variables.

### Social Bot Settings

| Key | Default | Description | Admin Endpoint |
|-----|---------|-------------|----------------|
| `SAFE_MODE` | `false` | Block all X posting | `PATCH /api/admin/social/settings` |
| `APPROVAL_REQUIRED` | `true` | Require approval for drafts | `PATCH /api/admin/social/settings` |

### Persona Settings

| Key | Default | Description | Admin Endpoint |
|-----|---------|-------------|----------------|
| `EPSTEIN_MODE` | `false` | Enable corpus retrieval | `POST /api/admin/corpus/epstein/enable` |
| `EPSTEIN_PERSONA_BLEND` | `false` | Enable parody cadence | `PATCH /api/admin/persona/settings` |

---

## Admin API Endpoints for Runtime Settings

### Social Bot Settings

```bash
# Get current settings
curl -H "X-Admin-Key: $ADMIN_KEY" \
  https://jeffreyaistein.fly.dev/api/admin/social/settings

# Update settings (any combination)
curl -X PATCH \
  -H "X-Admin-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"safe_mode": true, "approval_required": true}' \
  https://jeffreyaistein.fly.dev/api/admin/social/settings
```

**Parameters:**
- `safe_mode` (bool): `true` = block all posting, `false` = allow posting
- `approval_required` (bool): `true` = drafts need approval, `false` = auto-post

### Persona Settings

```bash
# Update persona blend settings
curl -X PATCH \
  -H "X-Admin-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"epstein_persona_blend": false, "snark_level": 2}' \
  https://jeffreyaistein.fly.dev/api/admin/persona/settings
```

**Parameters:**
- `epstein_persona_blend` (bool): Toggle parody cadence
- `snark_level` (int 0-5): Sarcasm intensity (default 2)

### Corpus Control

```bash
# Enable EPSTEIN_MODE (corpus retrieval)
curl -X POST \
  -H "X-Admin-Key: $ADMIN_KEY" \
  https://jeffreyaistein.fly.dev/api/admin/corpus/epstein/enable

# Disable EPSTEIN_MODE
curl -X POST \
  -H "X-Admin-Key: $ADMIN_KEY" \
  https://jeffreyaistein.fly.dev/api/admin/corpus/epstein/disable
```

### Kill Switch (Emergency)

```bash
# Enable kill switch (stops all posting immediately)
curl -X PATCH \
  -H "X-Admin-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"safe_mode": true}' \
  https://jeffreyaistein.fly.dev/api/admin/social/settings
```

---

## Style Version Management

Style proposals are stored in `style_guide_versions` table. Activation is manual.

```bash
# List all style versions
curl -H "X-Admin-Key: $ADMIN_KEY" \
  https://jeffreyaistein.fly.dev/api/admin/persona/style/versions

# Activate a specific version
curl -X POST \
  -H "X-Admin-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"version": 3}' \
  https://jeffreyaistein.fly.dev/api/admin/persona/style/activate

# Rollback to previous version
curl -X POST \
  -H "X-Admin-Key: $ADMIN_KEY" \
  https://jeffreyaistein.fly.dev/api/admin/persona/style/rollback

# Manually trigger proposal generation
curl -X POST \
  -H "X-Admin-Key: $ADMIN_KEY" \
  https://jeffreyaistein.fly.dev/api/admin/persona/style/generate
```

---

## Safe Production Configuration

### Fly.io Secrets (Minimum Required)

```bash
fly secrets set \
  DATABASE_URL="postgres://..." \
  REDIS_URL="redis://..." \
  ANTHROPIC_API_KEY="sk-ant-..." \
  ELEVENLABS_API_KEY="..." \
  ELEVENLABS_VOICE_ID="..." \
  SECRET_KEY="$(openssl rand -hex 32)" \
  SESSION_SECRET="$(openssl rand -hex 32)" \
  ADMIN_API_KEY="$(openssl rand -hex 32)" \
  CORS_ORIGINS="https://jeffreyaistein.vercel.app"
```

### Fly.io Secrets (X Bot - When Ready)

```bash
fly secrets set \
  X_API_KEY="..." \
  X_API_SECRET="..." \
  X_ACCESS_TOKEN="..." \
  X_ACCESS_TOKEN_SECRET="..." \
  X_BEARER_TOKEN="..." \
  X_BOT_USER_ID="..." \
  X_BOT_ENABLED="true"
```

### Vercel Environment Variables

```
NEXT_PUBLIC_API_BASE_URL=https://jeffreyaistein.fly.dev
NEXT_PUBLIC_CONTRACT_ADDRESS=69WBpgbrydCLSn3zyqAxzgrj2emGHLQJy9VdB1Xpump
NEXT_PUBLIC_AVATAR_MODE=glb
```

---

## Hardcoded Safety Constraints

These values are **not configurable** and are enforced in code:

| Constraint | Value | Location |
|------------|-------|----------|
| Max emoji percent | `0%` | `StyleRewriter`, validation before activation |
| Max hashtag percent | `0%` | `StyleRewriter`, validation before activation |
| EPSTEIN_MODE default | `false` | Always off unless explicitly enabled |
| Style auto-activation | Never | Proposals require manual admin activation |

---

## Environment Priority

When a setting exists in multiple places, the priority is:

1. **Runtime DB setting** (highest priority) - `x_settings` table
2. **Environment variable** - Fly secrets
3. **Default value** (lowest priority) - Hardcoded in `config.py`

This allows emergency changes via admin API without redeploying.

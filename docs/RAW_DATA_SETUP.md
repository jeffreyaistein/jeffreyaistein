# Raw KOL Dataset Setup

## Overview

The style training pipeline requires raw KOL (Key Opinion Leader) data. This data is **not committed to the repository** for size and privacy reasons.

## Supported Input Methods

There are only **two supported ways** to provide input data:

| Method | Description | Recommended |
|--------|-------------|-------------|
| **Local files** | kol_data.json + growth-from-vps.db in data/raw/ | **Yes** |
| **Pre-existing JSONL** | User-provided style_tweets.jsonl (use --skip-extraction) | Yes |

**The X API collector is DISABLED by default.** We do not scrape Twitter/X in normal operation. All data comes from local files that were previously collected.

## Local Development

### Required Files

Place these files in `apps/data/raw/`:

| File | Size | Description |
|------|------|-------------|
| `kol_data.json` | ~277 KB | 222 KOL profiles with sample tweets, personality analysis, engagement playbooks |
| `growth-from-vps.db` | ~19 MB | SQLite database with additional growth/intel data |

### How to Obtain

**Option 1: From DigitalOcean VPS backup**
```bash
scp root@178.128.78.35:/root/kol_data.json apps/data/raw/
scp root@178.128.78.35:/root/cube-launch/website/growth.db apps/data/raw/growth-from-vps.db
```

**Option 2: From local CUBE backup**
```bash
cp ~/cube-launch/kol_data.json apps/data/raw/
cp ~/cube-launch/growth-from-vps.db apps/data/raw/
```

### Verification

After placing the files, verify with:
```bash
ls -la apps/data/raw/
# Should show:
# - kol_data.json (~277 KB)
# - growth-from-vps.db (~19 MB)
```

## Production Setup

### Fly.io

1. Create a persistent volume:
   ```bash
   fly volumes create kol_data --size 1 --region iad
   ```

2. Mount in `fly.toml`:
   ```toml
   [mounts]
     source = "kol_data"
     destination = "/data/raw"
   ```

3. Upload files via SSH:
   ```bash
   fly ssh console
   # Then scp or curl the files into /data/raw/
   ```

4. Set environment variable:
   ```bash
   fly secrets set KOL_DATA_PATH=/data/raw
   ```

### Railway / Render

Use object storage (S3, R2, etc.) and download at startup:

```python
import os
import boto3

def download_kol_data():
    if os.path.exists('data/raw/kol_data.json'):
        return

    s3 = boto3.client('s3')
    s3.download_file('your-bucket', 'kol_data.json', 'data/raw/kol_data.json')
    s3.download_file('your-bucket', 'growth-from-vps.db', 'data/raw/growth-from-vps.db')
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RAW_DATA_DIR` | `data/raw` | Path to directory containing raw KOL files |
| `RUN_TWEET_COLLECTION` | `false` | **DANGEROUS**: Enables X API scraping (requires X_BEARER_TOKEN) |

**WARNING**: `RUN_TWEET_COLLECTION=true` is NOT recommended. It:
- Requires a valid X API bearer token
- Will scrape tweets from Twitter/X
- May violate Twitter's ToS if misused
- Is explicitly opt-in and will error without proper setup

Use local data files instead.

## Data Schema

### kol_data.json

```json
[
  {
    "handle": "frankdegods",
    "category": "alpha_caller|degen_trader|...",
    "notes": {
      "personality_summary": "...",
      "tone": "aggressive|chill|...",
      "market_insights": {...},
      "engagement_playbook": {...},
      "credibility_score": 7,
      "influence_reach": "medium",
      "sample_tweets": ["tweet1", "tweet2", "tweet3"],
      "analyzed_at": "2026-01-30T09:12:04.304Z"
    }
  }
]
```

### growth-from-vps.db (SQLite)

Key tables with row counts:

| Table | Rows | Description |
|-------|------|-------------|
| `kol_watchlist` | 222 | KOL profiles (mirrors kol_data.json structure) |
| `kol_intelligence` | 11 | Additional intelligence records |
| `memory_items` | 10,208 | Context/learning memory items |
| `scheduled_posts` | 921 | Historical post scheduling data |
| `action_log` | 5,910 | Historical action records |
| `stream_posts` | 95 | Stream-related posts |

Note: `x_tweets` table exists but has 0 rows - tweets are in `kol_data.json` sample_tweets field.

## Security Notes

- **Never commit** raw data files to git
- The `data/raw/` directory is in `.gitignore`
- Sample tweets may contain profanity/controversial content (CT culture)
- Personality analyses are AI-generated and may contain biases

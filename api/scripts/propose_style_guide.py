#!/usr/bin/env python3
"""
Jeffrey AIstein - Self Style Guide Proposal Generator

Generates versioned style guide proposals from AIstein's own tweets.
Proposals are NOT auto-activated - they require admin approval.

IMPORTANT: Hard brand rules are ALWAYS enforced:
- hashtags_allowed = 0 (NEVER)
- emojis_allowed = 0 (NEVER)

Usage:
    python scripts/propose_style_guide.py [--days 30] [--min-tweets 25]

Output:
    - apps/docs/style_proposals/STYLE_GUIDE_PROPOSED_<timestamp>.md
    - apps/api/services/persona/style_guide_proposals/<timestamp>.json
    - Metadata stored in style_guide_proposals/<timestamp>_meta.json
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Minimum tweets required to generate a proposal
DEFAULT_MIN_TWEETS = 25


def generate_version_id() -> str:
    """Generate a timestamp-based version ID."""
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


async def build_corpus(days: int, limit: int, output_path: Path) -> dict:
    """
    Build corpus from AIstein's tweets.

    Reuses logic from build_self_style_corpus.py.
    """
    from scripts.build_self_style_corpus import build_corpus as _build_corpus

    return await _build_corpus(
        days=days,
        limit=limit,
        output_path=str(output_path),
        include_replies=True,
        exclude_risk_flagged=True,
    )


def run_analyzer(input_file: Path) -> dict:
    """
    Run the style analyzer on the corpus.

    Returns profile and stats.
    """
    from services.social.style_dataset.analyzer import StyleAnalyzer

    analyzer = StyleAnalyzer()
    profile = analyzer.analyze_dataset(input_file)

    return {
        "profile": profile,
        "avg_length": profile.avg_length,
        "median_length": profile.median_length,
        "emoji_usage_pct": profile.emoji_usage_pct,
        "hashtag_usage_pct": profile.hashtag_usage_pct,
        "rules_derived": len(profile.rules),
        "ct_vocab_count": len(profile.ct_vocab_frequency),
    }


def generate_proposal_markdown(
    profile,
    version_id: str,
    tweet_count: int,
    output_path: Path,
) -> Path:
    """
    Generate versioned markdown proposal.

    ALWAYS enforces hard brand rules regardless of dataset stats.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now(timezone.utc).isoformat()

    content = f"""# Jeffrey AIstein - Style Guide Proposal

> **Version**: {version_id}
> **Generated**: {generated_at}
> **Source**: Self-Style Analysis (AIstein's own tweets)
> **Tweet Count**: {tweet_count}
> **Status**: PENDING APPROVAL

---

## IMPORTANT: This is a PROPOSAL

This style guide has NOT been activated. It requires admin approval via:
```
POST /api/admin/persona/style/activate
{{"version_id": "{version_id}"}}
```

Until activated, the current production style guide remains in effect.

---

## HARD BRAND RULES (Non-Negotiable)

These rules are ALWAYS enforced, regardless of dataset statistics:

| Rule | Allowed | Enforcement |
|------|---------|-------------|
| **Emojis** | **0% - NEVER** | Stripped at post-processing, validated |
| **Hashtags** | **0% - NEVER** | Stripped at post-processing, validated |

**These rules CANNOT be overridden by any proposal.**

---

## Proposed Tweet Length Patterns

| Metric | Value |
|--------|-------|
| Average length | {profile.avg_length} chars |
| Median length | {profile.median_length} chars |
| Short tweets (<50 chars) | {profile.short_tweet_pct}% |

---

## Dataset Statistics (Reference Only)

These are the raw statistics from AIstein's tweets. Hard brand rules override these:

| Pattern | Dataset Frequency | Enforced Rule |
|---------|-------------------|---------------|
| Uses emoji | {profile.emoji_usage_pct}% | **0% (FORCED)** |
| Avg emoji per tweet | {profile.avg_emoji_per_tweet} | **0 (FORCED)** |
| Contains link | {profile.link_usage_pct}% | Allowed |
| Ends with link | {profile.ends_with_link_pct}% | Allowed |
| Uses hashtag | {profile.hashtag_usage_pct}% | **0% (FORCED)** |
| Uses mention | {profile.mention_usage_pct}% | Allowed |
| Is question | {profile.question_pct}% | Allowed |

---

## CT Vocabulary Frequency

| Term | Count |
|------|-------|
"""
    for term, count in profile.ct_vocab_frequency.items():
        content += f"| {term} | {count} |\n"

    content += f"""
---

## Derived Style Rules

"""
    for i, rule in enumerate(profile.rules, 1):
        # Override any emoji/hashtag rules
        if "emoji" in rule.lower():
            rule = "NEVER use emojis - not a single one, ever"
        if "hashtag" in rule.lower() and "rare" not in rule.lower():
            rule = "NEVER use hashtags - not a single one, ever"
        content += f"{i}. {rule}\n"

    content += f"""
---

## Activation Instructions

To activate this proposal:

1. Review the proposed rules above
2. Call the activation endpoint:
   ```bash
   curl -X POST -H "X-Admin-Key: $ADMIN_KEY" \\
     -H "Content-Type: application/json" \\
     -d '{{"version_id": "{version_id}"}}' \\
     https://jeffreyaistein.fly.dev/api/admin/persona/style/activate
   ```
3. Verify activation via:
   ```bash
   curl -H "X-Admin-Key: $ADMIN_KEY" \\
     https://jeffreyaistein.fly.dev/api/admin/persona/status
   ```

To rollback to the previous version:
```bash
curl -X POST -H "X-Admin-Key: $ADMIN_KEY" \\
  https://jeffreyaistein.fly.dev/api/admin/persona/style/rollback
```

---

*Generated by Jeffrey AIstein Self-Style Pipeline*
*Proposals do not affect production until activated*
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    return output_path


def generate_proposal_json(
    profile,
    version_id: str,
    tweet_count: int,
    output_path: Path,
) -> Path:
    """
    Generate versioned JSON proposal.

    ALWAYS enforces hard brand rules:
    - emojis_allowed = 0
    - hashtags_allowed = 0
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now(timezone.utc).isoformat()

    # Build the guide with FORCED brand rules
    guide = {
        "version_id": version_id,
        "generated_at": generated_at,
        "source": "self_style",
        "tweet_count": tweet_count,
        "active": False,  # NEVER auto-activate
        "patterns": {
            "length": {
                "average": profile.avg_length,
                "median": profile.median_length,
                "target_max": 200,
                "short_pct": profile.short_tweet_pct,
            },
            "structure": {
                # FORCED: Dataset stats stored for reference but...
                "emoji_pct_dataset": profile.emoji_usage_pct,
                "avg_emoji_dataset": profile.avg_emoji_per_tweet,
                "hashtag_pct_dataset": profile.hashtag_usage_pct,
                # ...FORCED rules always apply
                "emojis_allowed": 0,  # FORCED - NEVER
                "hashtags_allowed": 0,  # FORCED - NEVER
                # Other patterns from dataset
                "link_pct": profile.link_usage_pct,
                "ends_with_link_pct": profile.ends_with_link_pct,
                "question_pct": profile.question_pct,
                "mention_pct": profile.mention_usage_pct,
            },
            "vocabulary": {
                "ct_terms": profile.ct_vocab_frequency,
            },
        },
        "rules": profile.rules,
        "hard_constraints": {
            "emojis_allowed": 0,
            "hashtags_allowed": 0,
            "max_length": 280,
            "note": "These constraints CANNOT be overridden by any proposal",
        },
        "rewriting": {
            "max_length": 280,
            "target_length": min(int(profile.avg_length * 1.2), 250),
            "avoid": [
                "emojis (NEVER)",
                "hashtags (NEVER)",
                "corporate language",
                "guaranteed returns",
                "excessive exclamation marks",
            ],
            "prefer": [
                "short sentences",
                "observations over promises",
                "self-aware humor",
                "tribal vocabulary when natural",
            ],
        },
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(guide, f, indent=2)

    return output_path


def generate_metadata(
    version_id: str,
    tweet_count: int,
    md_path: Path,
    json_path: Path,
    output_path: Path,
) -> Path:
    """Generate metadata file for the proposal."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    metadata = {
        "version_id": version_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "self_style",
        "tweet_count": tweet_count,
        "active": False,
        "activated_at": None,
        "files": {
            "markdown": str(md_path),
            "json": str(json_path),
            "metadata": str(output_path),
        },
        "hard_constraints_enforced": {
            "emojis_allowed": 0,
            "hashtags_allowed": 0,
        },
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return output_path


async def propose_style_guide(
    days: int = 30,
    limit: int = 500,
    min_tweets: int = DEFAULT_MIN_TWEETS,
) -> dict:
    """
    Generate a complete style guide proposal.

    Args:
        days: Days to look back for tweets
        limit: Max tweets to analyze
        min_tweets: Minimum tweets required (fails if below)

    Returns:
        Result dict with paths and stats
    """
    # Generate version ID
    version_id = generate_version_id()

    # Set up paths
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir.parent / "data"
    docs_dir = base_dir.parent / "docs" / "style_proposals"
    proposals_dir = base_dir / "services" / "persona" / "style_guide_proposals"

    corpus_path = data_dir / "self_style_tweets.jsonl"
    md_path = docs_dir / f"STYLE_GUIDE_PROPOSED_{version_id}.md"
    json_path = proposals_dir / f"{version_id}.json"
    meta_path = proposals_dir / f"{version_id}_meta.json"

    print(f"Generating style guide proposal: {version_id}")
    print(f"  Days: {days if days > 0 else 'all'}")
    print(f"  Limit: {limit}")
    print(f"  Min tweets required: {min_tweets}")
    print()

    # Step 1: Build corpus
    print("Step 1: Building self-style corpus...")
    corpus_stats = await build_corpus(days, limit, corpus_path)

    tweet_count = corpus_stats["exported"]
    print(f"  Tweets exported: {tweet_count}")

    # Validate minimum tweets
    if tweet_count < min_tweets:
        raise ValueError(
            f"Insufficient tweets: {tweet_count} < {min_tweets} minimum. "
            f"Cannot generate reliable style guide."
        )

    # Step 2: Run analyzer
    print("\nStep 2: Analyzing corpus...")
    analysis = run_analyzer(corpus_path)
    profile = analysis["profile"]

    print(f"  Avg length: {analysis['avg_length']} chars")
    print(f"  Emoji usage (dataset): {analysis['emoji_usage_pct']}%")
    print(f"  Hashtag usage (dataset): {analysis['hashtag_usage_pct']}%")
    print(f"  Rules derived: {analysis['rules_derived']}")

    # Step 3: Generate proposal files
    print("\nStep 3: Generating proposal files...")

    # Markdown
    md_result = generate_proposal_markdown(profile, version_id, tweet_count, md_path)
    print(f"  Markdown: {md_result}")

    # JSON
    json_result = generate_proposal_json(profile, version_id, tweet_count, json_path)
    print(f"  JSON: {json_result}")

    # Metadata
    meta_result = generate_metadata(version_id, tweet_count, md_path, json_path, meta_path)
    print(f"  Metadata: {meta_result}")

    # Validate outputs
    for path in [md_result, json_result, meta_result]:
        if not path.exists():
            raise RuntimeError(f"Failed to write output file: {path}")

    result = {
        "version_id": version_id,
        "tweet_count": tweet_count,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": {
            "corpus": str(corpus_path),
            "markdown": str(md_path),
            "json": str(json_path),
            "metadata": str(meta_path),
        },
        "analysis": {
            "avg_length": analysis["avg_length"],
            "emoji_usage_pct": analysis["emoji_usage_pct"],
            "hashtag_usage_pct": analysis["hashtag_usage_pct"],
            "rules_derived": analysis["rules_derived"],
        },
        "hard_constraints": {
            "emojis_allowed": 0,
            "hashtags_allowed": 0,
        },
        "active": False,
    }

    return result


def print_summary(result: dict) -> None:
    """Print proposal summary."""
    print()
    print("=" * 60)
    print("STYLE GUIDE PROPOSAL GENERATED")
    print("=" * 60)
    print()
    print(f"  Version ID:        {result['version_id']}")
    print(f"  Tweet count:       {result['tweet_count']}")
    print(f"  Generated at:      {result['generated_at']}")
    print()
    print("  Files:")
    print(f"    Corpus:          {result['files']['corpus']}")
    print(f"    Markdown:        {result['files']['markdown']}")
    print(f"    JSON:            {result['files']['json']}")
    print(f"    Metadata:        {result['files']['metadata']}")
    print()
    print("  Analysis:")
    print(f"    Avg length:      {result['analysis']['avg_length']} chars")
    print(f"    Emoji (dataset): {result['analysis']['emoji_usage_pct']}%")
    print(f"    Hashtag (data):  {result['analysis']['hashtag_usage_pct']}%")
    print(f"    Rules derived:   {result['analysis']['rules_derived']}")
    print()
    print("  Hard Constraints (ALWAYS ENFORCED):")
    print(f"    Emojis allowed:  {result['hard_constraints']['emojis_allowed']} (NEVER)")
    print(f"    Hashtags allowed: {result['hard_constraints']['hashtags_allowed']} (NEVER)")
    print()
    print("  Status:            PENDING APPROVAL")
    print()
    print("=" * 60)
    print("PROPOSALS DO NOT AFFECT PRODUCTION UNTIL ACTIVATED")
    print("=" * 60)
    print()
    print(f"To activate, use: POST /api/admin/persona/style/activate")
    print(f'  Body: {{"version_id": "{result["version_id"]}"}}')


async def main():
    parser = argparse.ArgumentParser(
        description="Generate a versioned style guide proposal from AIstein's tweets"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Days to look back for tweets (0 = no limit)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Maximum tweets to analyze",
    )
    parser.add_argument(
        "--min-tweets",
        type=int,
        default=DEFAULT_MIN_TWEETS,
        help=f"Minimum tweets required (default: {DEFAULT_MIN_TWEETS})",
    )

    args = parser.parse_args()

    # Check for DATABASE_URL
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL environment variable not set")
        print("This script requires a PostgreSQL database connection.")
        sys.exit(1)

    try:
        result = await propose_style_guide(
            days=args.days,
            limit=args.limit,
            min_tweets=args.min_tweets,
        )
        print_summary(result)

    except ValueError as e:
        print(f"\nERROR: {e}")
        sys.exit(1)
    except RuntimeError as e:
        print(f"\nERROR: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nUNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

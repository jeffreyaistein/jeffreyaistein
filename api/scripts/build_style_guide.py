#!/usr/bin/env python3
"""
Jeffrey AIstein - Style Guide Builder

Unified command to build the complete style guide pipeline:
1. Extract tweets from kol_data.json + growth-from-vps.db
2. Run analyzer to generate STYLE_GUIDE_DERIVED.md and style_guide.json
3. Print summary statistics

SUPPORTED INPUTS (only two options):
1. Local data files: kol_data.json + growth-from-vps.db in data/raw/
2. Pre-existing JSONL: User-provided style_tweets.jsonl (use --skip-extraction)

The X API collector is DISABLED by default and requires explicit opt-in.
We do NOT scrape Twitter/X. All data comes from local files.

Usage:
    cd apps/api && python scripts/build_style_guide.py

Environment Variables:
    RAW_DATA_DIR              - Override raw data directory path
    RUN_TWEET_COLLECTION=true - DANGEROUS: Use X API (requires explicit flag + token)
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.extract_kol_tweets import (
    extract_from_json,
    extract_from_db,
    deduplicate_tweets,
    sanitize_cube_references,
)
from services.social.style_dataset.analyzer import StyleAnalyzer
import json


def build_style_guide(
    input_dir: Path = None,
    output_jsonl: Path = None,
    skip_extraction: bool = False,
    use_x_api: bool = False,
):
    """
    Build the complete style guide from raw KOL data.

    Args:
        input_dir: Directory containing kol_data.json and growth-from-vps.db
        output_jsonl: Output path for style_tweets.jsonl
        skip_extraction: If True, skip extraction and use existing JSONL
        use_x_api: If True, use X API collector (requires X_BEARER_TOKEN)

    Returns:
        Dict with summary statistics
    """
    # X API mode is DISABLED by default
    # Requires BOTH: RUN_TWEET_COLLECTION=true AND X_BEARER_TOKEN
    run_tweet_collection_env = os.getenv("RUN_TWEET_COLLECTION", "").lower()
    if run_tweet_collection_env == "true":
        # Check for required token BEFORE enabling
        if not os.getenv("X_BEARER_TOKEN"):
            print("=" * 60)
            print("ERROR: X API mode requested but X_BEARER_TOKEN not set")
            print("=" * 60)
            print()
            print("To use X API collection, you must set BOTH:")
            print("  RUN_TWEET_COLLECTION=true")
            print("  X_BEARER_TOKEN=<your_bearer_token>")
            print()
            print("Alternatively, use local data files (recommended):")
            print("  - Place kol_data.json in data/raw/")
            print("  - Place growth-from-vps.db in data/raw/")
            print("  - Run without RUN_TWEET_COLLECTION")
            print()
            sys.exit(1)
        use_x_api = True
        print("WARNING: X API mode enabled - will scrape Twitter/X")
        print("         This is NOT the default behavior.")
        print()

    # Resolve default paths
    # Script is at apps/api/scripts/, raw data is at apps/data/raw/
    script_dir = Path(__file__).parent.parent  # apps/api
    apps_dir = script_dir.parent  # apps/

    # Allow RAW_DATA_DIR env var override
    raw_data_dir_env = os.getenv("RAW_DATA_DIR")
    if raw_data_dir_env:
        input_dir = Path(raw_data_dir_env)
    else:
        input_dir = input_dir or apps_dir / "data" / "raw"

    output_jsonl = output_jsonl or apps_dir / "data" / "style_tweets.jsonl"

    print("=" * 60)
    print("JEFFREY AISTEIN - STYLE GUIDE BUILDER")
    print("=" * 60)
    print()

    # Handle X API collection mode (DISABLED BY DEFAULT)
    # This mode requires explicit opt-in via RUN_TWEET_COLLECTION=true + X_BEARER_TOKEN
    if use_x_api and not skip_extraction:
        print("=" * 60)
        print("[MODE] X API COLLECTION (NON-DEFAULT)")
        print("=" * 60)
        print()
        print("WARNING: You have explicitly enabled X API collection.")
        print("         This will scrape tweets from Twitter/X.")
        print()

        try:
            from services.social.style_dataset.collector import StyleDatasetCollector
            from services.social.style_dataset.config import KOL_HANDLES, TWEETS_PER_USER
            import asyncio

            async def run_collector():
                collector = StyleDatasetCollector(
                    output_dir=output_jsonl.parent,
                    tweets_per_user=TWEETS_PER_USER,
                )
                return await collector.collect_from_handles(
                    KOL_HANDLES,
                    output_file=output_jsonl.name,
                )

            print("[STEP 1/3] Collecting tweets from X API...")
            stats = asyncio.run(run_collector())
            print(f"  Handles processed: {stats['handles_processed']}")
            print(f"  Handles failed: {stats['handles_failed']}")
            print(f"  Tweets collected: {stats['tweets_collected']}")
            print()

            extraction_stats = {
                "profiles_read": stats["handles_processed"],
                "tweets_extracted": stats["tweets_collected"],
                "tweets_deduped": 0,
                "tweets_written": stats["tweets_collected"],
                "cube_refs_sanitized": 0,
            }

            # Skip the local extraction since we used X API
            skip_extraction = True

        except ImportError as e:
            # Do NOT fall back - if X API was explicitly requested, fail
            print("=" * 60)
            print("ERROR: X API collector import failed")
            print("=" * 60)
            print(f"  {e}")
            print()
            print("X API collection was explicitly requested but failed.")
            print("Either fix the import or use local data files instead:")
            print("  - Remove RUN_TWEET_COLLECTION=true from environment")
            print("  - Place kol_data.json and growth-from-vps.db in data/raw/")
            print()
            sys.exit(1)

        except ValueError as e:
            print("=" * 60)
            print("ERROR: X API collection failed")
            print("=" * 60)
            print(f"  {e}")
            print()
            sys.exit(1)

    # Step 1: Extract tweets from raw data (if not using X API)
    if not skip_extraction:
        print("[STEP 1/3] Extracting tweets from raw data...")
        print(f"  Input directory: {input_dir}")
        print()

        json_path = input_dir / "kol_data.json"
        db_path = input_dir / "growth-from-vps.db"

        all_tweets = []
        total_profiles = 0

        if json_path.exists():
            print(f"  Reading {json_path.name}...")
            json_tweets, json_profiles = extract_from_json(json_path)
            all_tweets.extend(json_tweets)
            total_profiles += json_profiles
            print(f"    - Profiles: {json_profiles}")
            print(f"    - Tweets: {len(json_tweets)}")
        else:
            print(f"  WARNING: {json_path} not found")

        if db_path.exists():
            print(f"  Reading {db_path.name}...")
            db_tweets, db_profiles = extract_from_db(db_path)
            # Only add x_tweets (avoid duplicates from kol_watchlist)
            x_tweets_only = [t for t in db_tweets if "x_tweets" in t.get("source", "")]
            all_tweets.extend(x_tweets_only)
            print(f"    - Additional x_tweets: {len(x_tweets_only)}")
        else:
            print(f"  WARNING: {db_path} not found")

        print()
        print(f"  Total tweets before dedup: {len(all_tweets)}")

        # Deduplicate
        unique_tweets, duplicates = deduplicate_tweets(all_tweets)
        print(f"  Duplicates removed: {duplicates}")
        print(f"  Unique tweets: {len(unique_tweets)}")

        # Sanitize CUBE references
        cube_refs_found = 0
        for tweet in unique_tweets:
            if "CUBE" in tweet.get("text", ""):
                cube_refs_found += 1
            tweet["text"] = sanitize_cube_references(tweet["text"], "text")
        print(f"  CUBE references sanitized: {cube_refs_found}")

        # Write JSONL
        output_jsonl.parent.mkdir(parents=True, exist_ok=True)
        with open(output_jsonl, "w", encoding="utf-8") as f:
            for tweet in unique_tweets:
                f.write(json.dumps(tweet, ensure_ascii=False) + "\n")

        extraction_stats = {
            "profiles_read": total_profiles,
            "tweets_extracted": len(all_tweets),
            "tweets_deduped": duplicates,
            "tweets_written": len(unique_tweets),
            "cube_refs_sanitized": cube_refs_found,
        }

        print()
        print(f"  Output: {output_jsonl}")
        print(f"  Size: {output_jsonl.stat().st_size:,} bytes")
        print()
    else:
        print("[STEP 1/3] Skipping extraction (using existing JSONL)")
        print()
        if not output_jsonl.exists():
            raise FileNotFoundError(f"JSONL not found: {output_jsonl}")

    # Step 2: Run analyzer
    print("[STEP 2/3] Analyzing tweet patterns...")
    print()

    analyzer = StyleAnalyzer()
    result = analyzer.run(output_jsonl)

    profile = result["profile"]
    print(f"  Tweets analyzed: {len(profile.ct_vocab_frequency) > 0 and 'OK' or 'WARNING: No data'}")
    print(f"  Average length: {profile.avg_length} chars")
    print(f"  Emoji usage: {profile.emoji_usage_pct}%")
    print(f"  Link usage: {profile.link_usage_pct}%")
    print(f"  Hashtag usage: {profile.hashtag_usage_pct}%")
    print(f"  Question tweets: {profile.question_pct}%")
    print()

    # Step 3: Print summary
    print("[STEP 3/3] Generated files:")
    print()
    print(f"  STYLE_GUIDE_DERIVED.md: {result['markdown_path']}")
    print(f"  style_guide.json: {result['json_path']}")
    print()

    # Final summary
    print("=" * 60)
    print("BUILD COMPLETE")
    print("=" * 60)
    print()

    if extraction_stats:
        print("Extraction Summary:")
        print(f"  - Profiles read: {extraction_stats['profiles_read']}")
        print(f"  - Tweets extracted: {extraction_stats['tweets_extracted']}")
        print(f"  - Duplicates removed: {extraction_stats['tweets_deduped']}")
        print(f"  - Tweets written: {extraction_stats['tweets_written']}")
        print()

    print("Analysis Summary:")
    print(f"  - Average tweet length: {profile.avg_length} chars")
    print(f"  - Short tweets (<50 chars): {profile.short_tweet_pct}%")
    print(f"  - Rules derived: {len(profile.rules)}")
    print()

    print("Derived Style Rules:")
    for i, rule in enumerate(profile.rules, 1):
        print(f"  {i}. {rule}")
    print()

    print("=" * 60)

    return {
        "extraction": extraction_stats,
        "analysis": {
            "avg_length": profile.avg_length,
            "emoji_pct": profile.emoji_usage_pct,
            "rules_count": len(profile.rules),
        },
        "outputs": {
            "jsonl": str(output_jsonl),
            "markdown": result["markdown_path"],
            "json": result["json_path"],
        },
    }


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Build Jeffrey AIstein style guide from KOL data"
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        help="Directory containing kol_data.json and growth-from-vps.db (default: data/raw)",
    )
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        help="Output path for style_tweets.jsonl (default: data/style_tweets.jsonl)",
    )
    parser.add_argument(
        "--skip-extraction",
        action="store_true",
        help="Skip extraction and use existing JSONL file",
    )

    args = parser.parse_args()

    try:
        build_style_guide(
            input_dir=args.input_dir,
            output_jsonl=args.output_jsonl,
            skip_extraction=args.skip_extraction,
        )
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        print()
        print("Make sure raw data files exist in data/raw/")
        print("See docs/RAW_DATA_SETUP.md for instructions.")
        sys.exit(1)


if __name__ == "__main__":
    main()

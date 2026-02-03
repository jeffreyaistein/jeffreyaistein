#!/usr/bin/env python3
"""
KOL Tweet Extractor

Reads kol_data.json and growth-from-vps.db and outputs style_tweets.jsonl
for the style training pipeline.

Usage:
    python scripts/extract_kol_tweets.py [--input-dir PATH] [--output PATH]
"""

import argparse
import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


def hash_text(text: str) -> str:
    """Generate a hash for deduplication when tweet_id is not available."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def sanitize_cube_references(obj: Any, field_path: str = "") -> Any:
    """
    Recursively sanitize CUBE references in metadata fields.

    Rules:
    - In metadata/analysis fields: Replace "CUBE" with "AIstein"
    - In tweet text: Only replace if literally contains "CUBE" (case-sensitive)
    - Preserve original structure
    """
    if isinstance(obj, str):
        # For tweet text fields, only replace literal "CUBE"
        if field_path.endswith(".text") or field_path.endswith("sample_tweets"):
            if "CUBE" in obj:
                return obj.replace("CUBE", "AIstein")
            return obj
        # For metadata fields, replace all CUBE references
        return re.sub(r"\bCUBE\b", "AIstein", obj, flags=re.IGNORECASE)
    elif isinstance(obj, dict):
        return {k: sanitize_cube_references(v, f"{field_path}.{k}") for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_cube_references(item, field_path) for item in obj]
    return obj


def extract_from_json(json_path: Path) -> list[dict]:
    """Extract tweets from kol_data.json."""
    tweets = []

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    profiles_read = 0

    for record in data:
        handle = record.get("handle", "unknown")
        notes_raw = record.get("notes", {})

        # Parse notes if it's a string
        if isinstance(notes_raw, str):
            try:
                notes = json.loads(notes_raw)
            except json.JSONDecodeError:
                notes = {}
        else:
            notes = notes_raw

        profiles_read += 1

        # Extract sample tweets
        sample_tweets = notes.get("sample_tweets", notes.get("tweets", []))
        analyzed_at = notes.get("analyzed_at", None)

        for tweet_text in sample_tweets:
            if not tweet_text or not isinstance(tweet_text, str):
                continue

            # Clean up the tweet text (remove extra whitespace)
            tweet_text = " ".join(tweet_text.split())

            if len(tweet_text) < 5:
                continue

            tweets.append({
                "text": tweet_text,
                "handle": handle,
                "tweet_id": None,  # Not available in this dataset
                "created_at": analyzed_at,  # Use analysis timestamp as proxy
                "source": "kol_data.json",
            })

    return tweets, profiles_read


def extract_from_db(db_path: Path) -> list[dict]:
    """Extract tweets from growth-from-vps.db."""
    tweets = []
    profiles_read = 0

    if not db_path.exists():
        return tweets, profiles_read

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    # Check if kol_watchlist exists and has data not in JSON
    try:
        cur.execute("SELECT handle, notes FROM kol_watchlist")
        rows = cur.fetchall()

        for handle, notes_raw in rows:
            if not notes_raw:
                continue

            try:
                notes = json.loads(notes_raw)
            except json.JSONDecodeError:
                continue

            profiles_read += 1

            # Extract sample tweets
            sample_tweets = notes.get("sample_tweets", notes.get("tweets", []))
            analyzed_at = notes.get("analyzed_at", None)

            for tweet_text in sample_tweets:
                if not tweet_text or not isinstance(tweet_text, str):
                    continue

                tweet_text = " ".join(tweet_text.split())

                if len(tweet_text) < 5:
                    continue

                tweets.append({
                    "text": tweet_text,
                    "handle": handle,
                    "tweet_id": None,
                    "created_at": analyzed_at,
                    "source": "growth-from-vps.db",
                })
    except sqlite3.OperationalError:
        pass

    # Also check x_tweets table if it has data
    try:
        cur.execute("SELECT tweet_id, handle, text, ts FROM x_tweets WHERE text IS NOT NULL")
        rows = cur.fetchall()

        for tweet_id, handle, text, ts in rows:
            if not text:
                continue

            tweets.append({
                "text": " ".join(text.split()),
                "handle": handle or "unknown",
                "tweet_id": tweet_id,
                "created_at": ts,
                "source": "growth-from-vps.db:x_tweets",
            })
    except sqlite3.OperationalError:
        pass

    conn.close()
    return tweets, profiles_read


def deduplicate_tweets(tweets: list[dict]) -> list[dict]:
    """Deduplicate tweets by tweet_id (if available) or text hash."""
    seen_ids = set()
    seen_hashes = set()
    unique_tweets = []
    duplicates = 0

    for tweet in tweets:
        # Prefer tweet_id for dedup
        if tweet.get("tweet_id"):
            if tweet["tweet_id"] in seen_ids:
                duplicates += 1
                continue
            seen_ids.add(tweet["tweet_id"])
        else:
            # Fall back to text hash
            text_hash = hash_text(tweet["text"])
            if text_hash in seen_hashes:
                duplicates += 1
                continue
            seen_hashes.add(text_hash)

        unique_tweets.append(tweet)

    return unique_tweets, duplicates


def main():
    parser = argparse.ArgumentParser(description="Extract KOL tweets to JSONL")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/raw"),
        help="Directory containing kol_data.json and growth-from-vps.db",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/style_tweets.jsonl"),
        help="Output JSONL file path",
    )
    parser.add_argument(
        "--sanitize-cube",
        action="store_true",
        default=True,
        help="Replace CUBE references with AIstein",
    )
    args = parser.parse_args()

    # Resolve paths
    input_dir = args.input_dir
    if not input_dir.is_absolute():
        # Try relative to script location first, then CWD
        script_dir = Path(__file__).parent.parent
        if (script_dir / input_dir).exists():
            input_dir = script_dir / input_dir

    json_path = input_dir / "kol_data.json"
    db_path = input_dir / "growth-from-vps.db"
    output_path = args.output

    if not output_path.is_absolute():
        script_dir = Path(__file__).parent.parent
        output_path = script_dir / output_path

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("KOL Tweet Extractor")
    print("=" * 60)
    print(f"Input directory: {input_dir}")
    print(f"Output file: {output_path}")
    print()

    # Extract from both sources
    all_tweets = []
    total_profiles = 0

    if json_path.exists():
        print(f"Reading {json_path}...")
        json_tweets, json_profiles = extract_from_json(json_path)
        all_tweets.extend(json_tweets)
        total_profiles += json_profiles
        print(f"  - Profiles: {json_profiles}")
        print(f"  - Tweets: {len(json_tweets)}")
    else:
        print(f"WARNING: {json_path} not found")

    if db_path.exists():
        print(f"Reading {db_path}...")
        db_tweets, db_profiles = extract_from_db(db_path)
        # Only add DB tweets that aren't from the same source
        # (DB and JSON have same data, so we skip DB kol_watchlist)
        x_tweets_only = [t for t in db_tweets if "x_tweets" in t.get("source", "")]
        all_tweets.extend(x_tweets_only)
        print(f"  - Additional x_tweets: {len(x_tweets_only)}")
    else:
        print(f"WARNING: {db_path} not found")

    print()
    print(f"Total tweets before dedup: {len(all_tweets)}")

    # Deduplicate
    unique_tweets, duplicates = deduplicate_tweets(all_tweets)
    print(f"Duplicates removed: {duplicates}")
    print(f"Unique tweets: {len(unique_tweets)}")

    # Sanitize CUBE references if requested
    if args.sanitize_cube:
        print("Sanitizing CUBE references...")
        cube_refs_found = 0
        for tweet in unique_tweets:
            if "CUBE" in tweet.get("text", ""):
                cube_refs_found += 1
            tweet["text"] = sanitize_cube_references(tweet["text"], "text")
        print(f"  - Tweets with CUBE references: {cube_refs_found}")

    # Write output
    print()
    print(f"Writing to {output_path}...")
    with open(output_path, "w", encoding="utf-8") as f:
        for tweet in unique_tweets:
            f.write(json.dumps(tweet, ensure_ascii=False) + "\n")

    # Print summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Profiles read: {total_profiles}")
    print(f"Tweets extracted: {len(all_tweets)}")
    print(f"Tweets deduped: {duplicates}")
    print(f"Tweets written: {len(unique_tweets)}")
    print(f"Output file: {output_path}")
    print(f"Output size: {output_path.stat().st_size:,} bytes")
    print("=" * 60)

    return {
        "profiles_read": total_profiles,
        "tweets_extracted": len(all_tweets),
        "tweets_deduped": duplicates,
        "tweets_written": len(unique_tweets),
        "output_path": str(output_path),
    }


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Jeffrey AIstein - Self Style Corpus Builder

Exports AIstein's own outbound tweets to a JSONL corpus for self-style analysis.
This enables learning from our own successful posts without external API scraping.

Usage:
    python scripts/build_self_style_corpus.py [--days 30] [--limit 500] [--output data/self_style_tweets.jsonl]

Output format (JSONL):
    {"text": "...", "tweet_id": "...", "post_type": "reply|timeline", "posted_at": "...", "source": "aistein"}
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def build_corpus(
    days: int = 30,
    limit: int = 500,
    output_path: str = "data/self_style_tweets.jsonl",
    include_replies: bool = True,
    exclude_risk_flagged: bool = True,
) -> dict:
    """
    Build a JSONL corpus from AIstein's own outbound tweets.

    Args:
        days: Only include tweets from the last N days (0 = no limit)
        limit: Maximum number of tweets to export
        output_path: Path to output JSONL file
        include_replies: Whether to include reply tweets
        exclude_risk_flagged: Whether to exclude tweets with risk flags

    Returns:
        Stats dict with counts
    """
    from sqlalchemy import text
    from db.base import async_session_maker

    stats = {
        "total_posts": 0,
        "filtered_drafts": 0,
        "filtered_risk": 0,
        "filtered_type": 0,
        "exported": 0,
        "deduped": 0,
        "output_file": output_path,
    }

    # Ensure output directory exists
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    async with async_session_maker() as db:
        # Build the query
        query_parts = [
            "SELECT id, tweet_id, text, post_type, reply_to_id, posted_at",
            "FROM x_posts",
            "WHERE status = 'posted'",  # Only posted tweets
            "AND tweet_id IS NOT NULL",  # Must have been posted to X
        ]
        params = {}

        # Filter by date if specified
        if days > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            query_parts.append("AND posted_at >= :cutoff")
            params["cutoff"] = cutoff

        # Filter by post type if not including replies
        if not include_replies:
            query_parts.append("AND post_type = 'timeline'")

        # Order by most recent first
        query_parts.append("ORDER BY posted_at DESC")

        # Limit results
        query_parts.append("LIMIT :limit")
        params["limit"] = limit

        query = text("\n".join(query_parts))
        result = await db.execute(query, params)
        posts = result.mappings().fetchall()

        stats["total_posts"] = len(posts)

        # Get risk-flagged tweet IDs if excluding
        risk_flagged_ids = set()
        if exclude_risk_flagged:
            risk_query = text("""
                SELECT DISTINCT unnest(source_tweet_ids) as tweet_id
                FROM memories
                WHERE type = 'x_risk_flag'
            """)
            risk_result = await db.execute(risk_query)
            risk_flagged_ids = {row[0] for row in risk_result.fetchall()}
            print(f"Found {len(risk_flagged_ids)} risk-flagged tweets to exclude")

    # Process and export
    seen_texts = set()  # For deduplication
    exported_tweets = []

    for post in posts:
        tweet_id = post["tweet_id"]
        text_content = post["text"]

        # Skip risk-flagged tweets
        if tweet_id in risk_flagged_ids:
            stats["filtered_risk"] += 1
            continue

        # Skip duplicates (same text)
        text_hash = hash(text_content.strip().lower())
        if text_hash in seen_texts:
            stats["deduped"] += 1
            continue
        seen_texts.add(text_hash)

        # Build export record
        record = {
            "text": text_content,
            "tweet_id": tweet_id,
            "post_type": post["post_type"],
            "posted_at": post["posted_at"].isoformat() if post["posted_at"] else None,
            "source": "aistein",
        }

        # Include reply context if available
        if post["reply_to_id"]:
            record["reply_to_id"] = post["reply_to_id"]

        exported_tweets.append(record)

    stats["exported"] = len(exported_tweets)

    # Write JSONL output
    with open(output_path, "w", encoding="utf-8") as f:
        for record in exported_tweets:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # Calculate file size
    stats["output_size_bytes"] = os.path.getsize(output_path)

    return stats


def print_stats(stats: dict) -> None:
    """Print export statistics."""
    print("=" * 60)
    print("SELF STYLE CORPUS BUILD")
    print("=" * 60)
    print()
    print(f"  Total posts queried:     {stats['total_posts']}")
    print(f"  Filtered (risk flags):   {stats['filtered_risk']}")
    print(f"  Duplicates removed:      {stats['deduped']}")
    print(f"  Exported:                {stats['exported']}")
    print()
    print(f"  Output file:             {stats['output_file']}")
    print(f"  Output size:             {stats['output_size_bytes']:,} bytes")
    print("=" * 60)


async def main():
    parser = argparse.ArgumentParser(
        description="Build self-style corpus from AIstein's outbound tweets"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Only include tweets from the last N days (0 = no limit)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Maximum number of tweets to export",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/self_style_tweets.jsonl",
        help="Output JSONL file path",
    )
    parser.add_argument(
        "--no-replies",
        action="store_true",
        help="Exclude reply tweets (only timeline posts)",
    )
    parser.add_argument(
        "--include-risk-flagged",
        action="store_true",
        help="Include tweets that have been risk-flagged",
    )

    args = parser.parse_args()

    # Check for DATABASE_URL
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL environment variable not set")
        print("This script requires a PostgreSQL database connection.")
        sys.exit(1)

    print(f"Building self-style corpus...")
    print(f"  Days: {args.days if args.days > 0 else 'all'}")
    print(f"  Limit: {args.limit}")
    print(f"  Include replies: {not args.no_replies}")
    print(f"  Exclude risk-flagged: {not args.include_risk_flagged}")
    print()

    stats = await build_corpus(
        days=args.days,
        limit=args.limit,
        output_path=args.output,
        include_replies=not args.no_replies,
        exclude_risk_flagged=not args.include_risk_flagged,
    )

    print_stats(stats)

    if stats["exported"] == 0:
        print("\nWARNING: No tweets exported. This may be expected if:")
        print("  - No posts have been made yet")
        print("  - All posts are outside the date range")
        print("  - All posts have been filtered out")
        sys.exit(0)

    print(f"\nCorpus ready: {stats['output_file']}")


if __name__ == "__main__":
    asyncio.run(main())

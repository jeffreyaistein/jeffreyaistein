#!/usr/bin/env python3
"""
Jeffrey AIstein - Learning Persistence Verification

Verifies that all required tables exist and learning data is being persisted.
Prints counts matching the /api/admin/learning/status endpoint.

Usage:
    python scripts/verify_learning_persistence.py

Exit codes:
    0: All tables exist and counts can be computed
    1: Missing tables or query errors
"""

import asyncio
import os
import sys
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def verify_persistence():
    """Verify learning persistence tables and return counts."""
    from sqlalchemy import text
    from db.base import async_session_maker

    results = {
        "tables_verified": [],
        "tables_missing": [],
        "counts": {},
        "errors": [],
    }

    async with async_session_maker() as db:
        # Tables to verify
        tables = [
            "x_inbox",
            "x_posts",
            "x_drafts",
            "x_threads",
            "x_reply_log",
            "x_settings",
            "x_user_limits",
        ]

        # Check each table exists
        for table in tables:
            try:
                await db.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
                results["tables_verified"].append(table)
            except Exception as e:
                if "does not exist" in str(e) or "relation" in str(e).lower():
                    results["tables_missing"].append(table)
                    results["errors"].append(f"Table {table} does not exist")
                else:
                    results["errors"].append(f"Error checking {table}: {e}")

        # If critical tables missing, return early
        critical_tables = ["x_inbox", "x_posts", "x_drafts"]
        missing_critical = [t for t in critical_tables if t in results["tables_missing"]]
        if missing_critical:
            return results

        # Get counts
        try:
            # Inbound tweets
            inbound_result = await db.execute(text("SELECT COUNT(*) FROM x_inbox"))
            results["counts"]["inbound_tweets_count"] = inbound_result.scalar() or 0

            # Outbound posts (posted only)
            outbound_result = await db.execute(
                text("SELECT COUNT(*) FROM x_posts WHERE status = 'posted'")
            )
            results["counts"]["outbound_posts_count"] = outbound_result.scalar() or 0

            # All posts (any status)
            all_posts_result = await db.execute(text("SELECT COUNT(*) FROM x_posts"))
            results["counts"]["total_posts_count"] = all_posts_result.scalar() or 0

            # Drafts by status
            drafts_result = await db.execute(
                text("SELECT status, COUNT(*) as count FROM x_drafts GROUP BY status")
            )
            drafts_rows = drafts_result.fetchall()
            results["counts"]["drafts"] = {
                "pending": 0,
                "approved": 0,
                "rejected": 0,
            }
            for row in drafts_rows:
                if row[0] in results["counts"]["drafts"]:
                    results["counts"]["drafts"][row[0]] = row[1]

            # Last ingest
            last_ingest_result = await db.execute(
                text("SELECT MAX(received_at) FROM x_inbox")
            )
            results["counts"]["last_ingest_at"] = last_ingest_result.scalar()

            # Last post
            last_post_result = await db.execute(
                text("SELECT MAX(posted_at) FROM x_posts WHERE status = 'posted'")
            )
            results["counts"]["last_post_at"] = last_post_result.scalar()

            # Thread linkage
            inbox_thread_result = await db.execute(
                text("""
                    SELECT COUNT(*) FROM x_inbox
                    WHERE tweet_data->>'conversation_id' IS NOT NULL
                       OR tweet_data->>'reply_to_tweet_id' IS NOT NULL
                """)
            )
            results["counts"]["inbound_with_thread_info"] = inbox_thread_result.scalar() or 0

            posts_reply_result = await db.execute(
                text("SELECT COUNT(*) FROM x_posts WHERE reply_to_id IS NOT NULL")
            )
            results["counts"]["outbound_with_reply_to"] = posts_reply_result.scalar() or 0

            threads_result = await db.execute(text("SELECT COUNT(*) FROM x_threads"))
            results["counts"]["threads_tracked"] = threads_result.scalar() or 0

            # Reply log
            reply_log_result = await db.execute(text("SELECT COUNT(*) FROM x_reply_log"))
            results["counts"]["reply_log_entries"] = reply_log_result.scalar() or 0

        except Exception as e:
            results["errors"].append(f"Error computing counts: {e}")

    return results


def print_results(results: dict) -> bool:
    """Print verification results. Returns True if all OK."""
    print("=" * 60)
    print("LEARNING PERSISTENCE VERIFICATION")
    print("=" * 60)
    print()

    # Tables status
    print("-" * 60)
    print("TABLES")
    print("-" * 60)
    for table in results["tables_verified"]:
        print(f"  [OK] {table}")
    for table in results["tables_missing"]:
        print(f"  [MISSING] {table}")
    print()

    # Counts
    if results["counts"]:
        print("-" * 60)
        print("COUNTS")
        print("-" * 60)
        counts = results["counts"]

        print(f"  Inbound tweets (x_inbox):     {counts.get('inbound_tweets_count', 'N/A')}")
        print(f"  Outbound posts (posted):      {counts.get('outbound_posts_count', 'N/A')}")
        print(f"  Total posts (all status):     {counts.get('total_posts_count', 'N/A')}")
        print()

        drafts = counts.get("drafts", {})
        print(f"  Drafts pending:               {drafts.get('pending', 'N/A')}")
        print(f"  Drafts approved:              {drafts.get('approved', 'N/A')}")
        print(f"  Drafts rejected:              {drafts.get('rejected', 'N/A')}")
        print()

        last_ingest = counts.get("last_ingest_at")
        last_post = counts.get("last_post_at")
        print(f"  Last ingest at:               {last_ingest.isoformat() if last_ingest else 'Never'}")
        print(f"  Last post at:                 {last_post.isoformat() if last_post else 'Never'}")
        print()

        print("-" * 60)
        print("THREAD LINKAGE")
        print("-" * 60)
        print(f"  Inbound with thread info:     {counts.get('inbound_with_thread_info', 'N/A')}")
        print(f"  Outbound with reply_to:       {counts.get('outbound_with_reply_to', 'N/A')}")
        print(f"  Threads tracked:              {counts.get('threads_tracked', 'N/A')}")
        print(f"  Reply log entries:            {counts.get('reply_log_entries', 'N/A')}")
        print()

    # Errors
    if results["errors"]:
        print("-" * 60)
        print("ERRORS")
        print("-" * 60)
        for error in results["errors"]:
            print(f"  [ERROR] {error}")
        print()

    # Summary
    print("=" * 60)
    all_ok = len(results["tables_missing"]) == 0 and len(results["errors"]) == 0
    status = "ALL CHECKS PASSED" if all_ok else "VERIFICATION FAILED"
    print(f"RESULT: {status}")
    print("=" * 60)

    return all_ok


async def main():
    # Check for DATABASE_URL
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL environment variable not set")
        print("This script requires a PostgreSQL database connection.")
        sys.exit(1)

    results = await verify_persistence()
    all_ok = print_results(results)
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    asyncio.run(main())

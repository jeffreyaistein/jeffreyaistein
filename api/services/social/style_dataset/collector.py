"""
Jeffrey AIstein - KOL Style Dataset Collector

Fetches tweets from KOL handles using X API v2 for style analysis.
Respects rate limits and stores in JSONL format.
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
import structlog

logger = structlog.get_logger()

# X API v2 base URL
X_API_BASE = "https://api.x.com/2"

# Default output paths
DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent.parent.parent / "data"
DEFAULT_OUTPUT_FILE = "style_tweets.jsonl"

# Rate limit settings
RATE_LIMIT_DELAY = 1.0  # seconds between requests
MAX_RETRIES = 3
BACKOFF_BASE = 2.0


class StyleDatasetCollector:
    """
    Collects tweets from KOL handles for style analysis.

    Uses X API v2 Bearer token authentication (read-only).
    Stores tweets in JSONL format for downstream analysis.
    """

    def __init__(
        self,
        bearer_token: Optional[str] = None,
        output_dir: Optional[Path] = None,
        tweets_per_user: int = 20,
    ):
        """
        Initialize the collector.

        Args:
            bearer_token: X API Bearer token (defaults to env var)
            output_dir: Directory for output files
            tweets_per_user: Max tweets to fetch per user (default 20)
        """
        self.bearer_token = bearer_token or os.getenv("X_BEARER_TOKEN")
        if not self.bearer_token:
            raise ValueError("X_BEARER_TOKEN required for style dataset collection")

        self.output_dir = output_dir or DEFAULT_OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.tweets_per_user = tweets_per_user

        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={
                    "Authorization": f"Bearer {self.bearer_token}",
                    "User-Agent": "JeffreyAIstein/1.0",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _request_with_backoff(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> Optional[dict]:
        """Make request with exponential backoff on rate limits."""
        client = await self._get_client()

        for attempt in range(MAX_RETRIES):
            try:
                response = await client.request(method, url, **kwargs)

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    # Rate limited
                    retry_after = int(response.headers.get("retry-after", 60))
                    logger.warning(
                        "rate_limited",
                        url=url,
                        retry_after=retry_after,
                        attempt=attempt,
                    )
                    await asyncio.sleep(retry_after)
                elif response.status_code == 401:
                    logger.error("auth_failed", url=url)
                    return None
                elif response.status_code == 404:
                    logger.warning("not_found", url=url)
                    return None
                else:
                    logger.warning(
                        "request_failed",
                        url=url,
                        status=response.status_code,
                        body=response.text[:200],
                    )
                    # Backoff on errors
                    delay = BACKOFF_BASE ** attempt
                    await asyncio.sleep(delay)

            except Exception as e:
                logger.error("request_exception", url=url, error=str(e))
                delay = BACKOFF_BASE ** attempt
                await asyncio.sleep(delay)

        return None

    async def get_user_id(self, username: str) -> Optional[str]:
        """
        Get user ID from username.

        Args:
            username: X username (without @)

        Returns:
            User ID string or None if not found
        """
        url = f"{X_API_BASE}/users/by/username/{username}"
        params = {"user.fields": "id,username,name,public_metrics"}

        data = await self._request_with_backoff("GET", url, params=params)
        if data and "data" in data:
            return data["data"]["id"]
        return None

    async def get_user_tweets(
        self,
        user_id: str,
        max_results: int = 20,
    ) -> list[dict]:
        """
        Fetch recent tweets from a user.

        Args:
            user_id: X user ID
            max_results: Maximum tweets to fetch (5-100)

        Returns:
            List of tweet data dicts
        """
        url = f"{X_API_BASE}/users/{user_id}/tweets"
        params = {
            "max_results": min(max(max_results, 5), 100),
            "tweet.fields": "created_at,public_metrics,entities,text",
            "exclude": "retweets,replies",  # Original tweets only
        }

        data = await self._request_with_backoff("GET", url, params=params)
        if data and "data" in data:
            return data["data"]
        return []

    async def collect_from_handles(
        self,
        handles: list[str],
        output_file: Optional[str] = None,
    ) -> dict:
        """
        Collect tweets from a list of handles.

        Args:
            handles: List of X usernames (without @)
            output_file: Output filename (default: style_tweets.jsonl)

        Returns:
            Stats dict with counts
        """
        output_path = self.output_dir / (output_file or DEFAULT_OUTPUT_FILE)

        stats = {
            "handles_processed": 0,
            "handles_failed": 0,
            "tweets_collected": 0,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(
            "collection_started",
            handles_count=len(handles),
            tweets_per_user=self.tweets_per_user,
            output=str(output_path),
        )

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                for i, handle in enumerate(handles):
                    handle = handle.lstrip("@")
                    logger.info(
                        "processing_handle",
                        handle=handle,
                        progress=f"{i+1}/{len(handles)}",
                    )

                    # Get user ID
                    user_id = await self.get_user_id(handle)
                    if not user_id:
                        logger.warning("handle_not_found", handle=handle)
                        stats["handles_failed"] += 1
                        continue

                    # Respect rate limits
                    await asyncio.sleep(RATE_LIMIT_DELAY)

                    # Get tweets
                    tweets = await self.get_user_tweets(
                        user_id,
                        max_results=self.tweets_per_user,
                    )

                    if not tweets:
                        logger.warning("no_tweets", handle=handle)
                        stats["handles_failed"] += 1
                        continue

                    # Write tweets to JSONL
                    for tweet in tweets:
                        record = {
                            "handle": handle,
                            "user_id": user_id,
                            "tweet_id": tweet.get("id"),
                            "text": tweet.get("text"),
                            "created_at": tweet.get("created_at"),
                            "metrics": tweet.get("public_metrics", {}),
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                        }
                        f.write(json.dumps(record) + "\n")
                        stats["tweets_collected"] += 1

                    stats["handles_processed"] += 1

                    # Rate limit between users
                    await asyncio.sleep(RATE_LIMIT_DELAY)

        finally:
            await self.close()

        stats["completed_at"] = datetime.now(timezone.utc).isoformat()

        logger.info("collection_completed", **stats)

        return stats

    async def collect_from_file(
        self,
        handles_file: Path,
        output_file: Optional[str] = None,
    ) -> dict:
        """
        Collect tweets from handles listed in a file.

        Args:
            handles_file: Path to file with one handle per line
            output_file: Output filename

        Returns:
            Stats dict
        """
        with open(handles_file, "r", encoding="utf-8") as f:
            handles = [line.strip() for line in f if line.strip() and not line.startswith("#")]

        return await self.collect_from_handles(handles, output_file)


# CLI entry point
async def main():
    """Run collector from command line."""
    import argparse

    parser = argparse.ArgumentParser(description="Collect KOL tweets for style analysis")
    parser.add_argument(
        "--handles-file",
        type=Path,
        help="File with handles (one per line)",
    )
    parser.add_argument(
        "--handles",
        nargs="+",
        help="List of handles to collect",
    )
    parser.add_argument(
        "--tweets-per-user",
        type=int,
        default=20,
        help="Max tweets per user (default: 20)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="style_tweets.jsonl",
        help="Output filename",
    )

    args = parser.parse_args()

    if not args.handles_file and not args.handles:
        parser.error("Must provide --handles-file or --handles")

    collector = StyleDatasetCollector(tweets_per_user=args.tweets_per_user)

    if args.handles_file:
        stats = await collector.collect_from_file(args.handles_file, args.output)
    else:
        stats = await collector.collect_from_handles(args.handles, args.output)

    print(f"\nCollection complete:")
    print(f"  Handles processed: {stats['handles_processed']}")
    print(f"  Handles failed: {stats['handles_failed']}")
    print(f"  Tweets collected: {stats['tweets_collected']}")


if __name__ == "__main__":
    asyncio.run(main())

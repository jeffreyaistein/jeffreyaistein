"""
Jeffrey AIstein - Real X Provider

Production X API v2 implementation with pay-per-use pricing.
Uses api.x.com endpoints for read/write operations.
"""

import asyncio
import base64
import hashlib
import hmac
import os
import random
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
import structlog

from services.social.providers.base import (
    XAuthError,
    XNotFoundError,
    XProvider,
    XProviderError,
    XRateLimitError,
)
from services.social.types import XTweet, XUser

logger = structlog.get_logger()


# X API v2 base URL (api.x.com is the current URL, api.twitter.com also works)
X_API_BASE = "https://api.x.com/2"


def get_backoff_base() -> float:
    """Get exponential backoff base seconds from environment."""
    return float(os.getenv("X_API_BACKOFF_BASE_SECONDS", "1"))


def get_backoff_max() -> float:
    """Get max backoff seconds from environment."""
    return float(os.getenv("X_API_BACKOFF_MAX_SECONDS", "900"))


class OAuth1Signer:
    """
    OAuth 1.0a request signer for X API write operations.

    Implements HMAC-SHA1 signing as required by X API.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        access_token: str,
        access_token_secret: str,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_token = access_token
        self.access_token_secret = access_token_secret

    def _percent_encode(self, s: str) -> str:
        """RFC 3986 percent-encode a string."""
        return urllib.parse.quote(str(s), safe="")

    def _generate_nonce(self) -> str:
        """Generate a random nonce."""
        return base64.b64encode(
            hashlib.sha1(str(random.random()).encode()).digest()
        ).decode()[:32]

    def _generate_timestamp(self) -> str:
        """Generate Unix timestamp."""
        return str(int(time.time()))

    def sign_request(
        self,
        method: str,
        url: str,
        body_params: Optional[dict] = None,
    ) -> dict:
        """
        Generate OAuth 1.0a Authorization header.

        Args:
            method: HTTP method (GET, POST, DELETE)
            url: Full request URL (without query string for signing)
            body_params: Request body parameters (for POST)

        Returns:
            Headers dict with Authorization header
        """
        # Parse URL to get base URL and query params
        parsed = urllib.parse.urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

        # OAuth parameters
        oauth_params = {
            "oauth_consumer_key": self.api_key,
            "oauth_nonce": self._generate_nonce(),
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": self._generate_timestamp(),
            "oauth_token": self.access_token,
            "oauth_version": "1.0",
        }

        # Collect all parameters for signature
        all_params = dict(oauth_params)

        # Add query string params
        if parsed.query:
            query_params = urllib.parse.parse_qs(parsed.query)
            for k, v in query_params.items():
                all_params[k] = v[0] if len(v) == 1 else v

        # Add body params for POST (if form-encoded)
        # Note: For JSON body, we don't include body in signature
        # X API v2 uses JSON, so we skip this

        # Sort and encode parameters
        sorted_params = sorted(all_params.items())
        param_string = "&".join(
            f"{self._percent_encode(k)}={self._percent_encode(v)}"
            for k, v in sorted_params
        )

        # Create signature base string
        signature_base = "&".join([
            method.upper(),
            self._percent_encode(base_url),
            self._percent_encode(param_string),
        ])

        # Create signing key
        signing_key = "&".join([
            self._percent_encode(self.api_secret),
            self._percent_encode(self.access_token_secret),
        ])

        # Generate signature
        signature = base64.b64encode(
            hmac.new(
                signing_key.encode(),
                signature_base.encode(),
                hashlib.sha1,
            ).digest()
        ).decode()

        oauth_params["oauth_signature"] = signature

        # Build Authorization header
        auth_header = "OAuth " + ", ".join(
            f'{self._percent_encode(k)}="{self._percent_encode(v)}"'
            for k, v in sorted(oauth_params.items())
        )

        return {"Authorization": auth_header}


class RealXProvider(XProvider):
    """
    Production X API v2 provider.

    Uses:
    - Bearer token for read operations (GET)
    - OAuth 1.0a for write operations (POST, DELETE)

    Requires environment variables:
    - X_BEARER_TOKEN: For read operations
    - X_API_KEY, X_API_SECRET: Consumer credentials
    - X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET: User credentials
    - X_BOT_USER_ID: The bot's user ID (for fetching mentions)
    """

    # Fields to request from X API
    USER_FIELDS = "id,username,name,created_at,verified,public_metrics,description,location,profile_image_url"
    TWEET_FIELDS = "id,text,author_id,conversation_id,created_at,in_reply_to_user_id,referenced_tweets"
    EXPANSIONS = "author_id,referenced_tweets.id"

    def __init__(self):
        """Initialize real X provider with credentials."""
        self.bearer_token = os.getenv("X_BEARER_TOKEN")
        self.api_key = os.getenv("X_API_KEY")
        self.api_secret = os.getenv("X_API_SECRET")
        self.access_token = os.getenv("X_ACCESS_TOKEN")
        self.access_token_secret = os.getenv("X_ACCESS_TOKEN_SECRET")
        self.bot_user_id = os.getenv("X_BOT_USER_ID")

        # Rate limit tracking
        self._retry_count = 0
        self._last_rate_limit: Optional[float] = None

        # OAuth signer for write operations
        self._oauth_signer: Optional[OAuth1Signer] = None
        if all([self.api_key, self.api_secret, self.access_token, self.access_token_secret]):
            self._oauth_signer = OAuth1Signer(
                self.api_key,
                self.api_secret,
                self.access_token,
                self.access_token_secret,
            )

        # HTTP client
        self._client: Optional[httpx.AsyncClient] = None

        if not self.bearer_token:
            logger.warning("X_BEARER_TOKEN not configured - read operations will fail")

        if not self._oauth_signer:
            logger.warning("X OAuth credentials incomplete - write operations will fail")

        if not self.bot_user_id:
            logger.warning("X_BOT_USER_ID not configured - mention fetching will fail")

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    def _get_bearer_headers(self) -> dict:
        """Get Bearer token headers for read operations."""
        if not self.bearer_token:
            raise XAuthError("X_BEARER_TOKEN not configured")

        return {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
        }

    async def _handle_response(
        self,
        response: httpx.Response,
        context: str = "request",
    ) -> dict:
        """
        Handle API response, raising appropriate exceptions.

        Args:
            response: httpx Response object
            context: Description for logging

        Returns:
            Parsed JSON response

        Raises:
            XRateLimitError: On 429
            XAuthError: On 401/403
            XNotFoundError: On 404
            XProviderError: On other errors
        """
        if response.status_code == 200 or response.status_code == 201:
            self._retry_count = 0
            return response.json()

        if response.status_code == 429:
            # Rate limited - extract retry-after if available
            retry_after = response.headers.get("retry-after")
            retry_seconds = int(retry_after) if retry_after else self._calculate_backoff()

            self._last_rate_limit = time.time()
            self._retry_count += 1

            logger.warning(
                "x_api_rate_limited",
                context=context,
                retry_after=retry_seconds,
                retry_count=self._retry_count,
            )

            raise XRateLimitError(
                f"Rate limited on {context}",
                retry_after_seconds=retry_seconds,
            )

        if response.status_code == 401:
            raise XAuthError(f"Unauthorized: {response.text}")

        if response.status_code == 403:
            raise XAuthError(f"Forbidden: {response.text}")

        if response.status_code == 404:
            raise XNotFoundError(f"Not found: {response.text}")

        # Other errors
        raise XProviderError(
            f"X API error ({response.status_code}): {response.text}"
        )

    def _calculate_backoff(self) -> int:
        """Calculate exponential backoff delay."""
        base = get_backoff_base()
        max_backoff = get_backoff_max()

        # Exponential backoff with jitter
        delay = min(base * (2 ** self._retry_count), max_backoff)
        jitter = random.uniform(0, delay * 0.1)

        return int(delay + jitter)

    def _parse_user(self, data: dict) -> XUser:
        """Parse user data from API response."""
        public_metrics = data.get("public_metrics", {})

        # Parse created_at
        created_at = datetime.now(timezone.utc)
        if "created_at" in data:
            created_at = datetime.fromisoformat(
                data["created_at"].replace("Z", "+00:00")
            )

        # Check for default profile image
        profile_image = data.get("profile_image_url", "")
        default_profile_image = "default" in profile_image.lower()

        return XUser(
            id=data["id"],
            username=data["username"],
            name=data.get("name", data["username"]),
            created_at=created_at,
            followers_count=public_metrics.get("followers_count", 0),
            following_count=public_metrics.get("following_count", 0),
            tweet_count=public_metrics.get("tweet_count", 0),
            verified=data.get("verified", False),
            description=data.get("description"),
            location=data.get("location"),
            profile_image_url=profile_image,
            default_profile_image=default_profile_image,
        )

    def _parse_tweet(
        self,
        data: dict,
        users_by_id: Optional[dict[str, XUser]] = None,
    ) -> XTweet:
        """Parse tweet data from API response."""
        # Parse created_at
        created_at = None
        if "created_at" in data:
            created_at = datetime.fromisoformat(
                data["created_at"].replace("Z", "+00:00")
            )

        # Extract reply_to_tweet_id from referenced_tweets
        reply_to_tweet_id = None
        referenced_tweets = data.get("referenced_tweets", [])
        for ref in referenced_tweets:
            if ref.get("type") == "replied_to":
                reply_to_tweet_id = ref.get("id")
                break

        # Get author if available
        author = None
        author_id = data.get("author_id")
        if users_by_id and author_id:
            author = users_by_id.get(author_id)

        return XTweet(
            id=data["id"],
            text=data["text"],
            author_id=author_id or "",
            conversation_id=data.get("conversation_id"),
            reply_to_tweet_id=reply_to_tweet_id,
            reply_to_user_id=data.get("in_reply_to_user_id"),
            created_at=created_at,
            author=author,
        )

    async def fetch_mentions(
        self,
        since_id: Optional[str] = None,
        max_results: int = 100,
    ) -> list[XTweet]:
        """
        Fetch mentions of the bot user.

        Uses GET /2/users/:id/mentions endpoint.
        """
        if not self.bot_user_id:
            raise XAuthError("X_BOT_USER_ID not configured")

        client = await self._get_client()
        url = f"{X_API_BASE}/users/{self.bot_user_id}/mentions"

        params = {
            "max_results": min(max_results, 100),  # API max is 100
            "tweet.fields": self.TWEET_FIELDS,
            "user.fields": self.USER_FIELDS,
            "expansions": self.EXPANSIONS,
        }

        if since_id:
            params["since_id"] = since_id

        logger.debug(
            "x_api_fetch_mentions",
            bot_user_id=self.bot_user_id,
            since_id=since_id,
            max_results=max_results,
        )

        response = await client.get(
            url,
            headers=self._get_bearer_headers(),
            params=params,
        )

        result = await self._handle_response(response, "fetch_mentions")

        # Parse users from includes
        users_by_id: dict[str, XUser] = {}
        if "includes" in result and "users" in result["includes"]:
            for user_data in result["includes"]["users"]:
                user = self._parse_user(user_data)
                users_by_id[user.id] = user

        # Parse tweets
        tweets = []
        if "data" in result:
            for tweet_data in result["data"]:
                tweet = self._parse_tweet(tweet_data, users_by_id)
                tweets.append(tweet)

        logger.info(
            "x_api_mentions_fetched",
            count=len(tweets),
            since_id=since_id,
        )

        return tweets

    async def fetch_thread_context(
        self,
        tweet_id: str,
        max_depth: int = 10,
    ) -> list[XTweet]:
        """
        Fetch conversation thread context by walking reply chain.

        Returns tweets in chronological order (oldest first).
        """
        client = await self._get_client()
        thread = []
        current_id = tweet_id
        depth = 0

        # First, get the target tweet
        current_tweet = await self.get_tweet(tweet_id)
        thread.append(current_tweet)

        # Walk up the reply chain
        while current_tweet.reply_to_tweet_id and depth < max_depth:
            try:
                parent_tweet = await self.get_tweet(current_tweet.reply_to_tweet_id)
                thread.insert(0, parent_tweet)  # Insert at beginning
                current_tweet = parent_tweet
                depth += 1
            except XNotFoundError:
                # Parent tweet may be deleted
                break
            except XRateLimitError:
                # Stop walking if rate limited
                break

        logger.debug(
            "x_api_thread_context_fetched",
            tweet_id=tweet_id,
            thread_length=len(thread),
            depth=depth,
        )

        return thread

    async def post_tweet(
        self,
        text: str,
        reply_to: Optional[str] = None,
    ) -> XTweet:
        """
        Post a new tweet.

        Uses POST /2/tweets with OAuth 1.0a authentication.
        """
        if len(text) > 280:
            raise ValueError(f"Tweet exceeds 280 characters (got {len(text)})")

        if not self._oauth_signer:
            raise XAuthError("OAuth credentials not configured for posting")

        client = await self._get_client()
        url = f"{X_API_BASE}/tweets"

        # Build request body
        body: dict[str, Any] = {"text": text}
        if reply_to:
            body["reply"] = {"in_reply_to_tweet_id": reply_to}

        # Sign request with OAuth 1.0a
        oauth_headers = self._oauth_signer.sign_request("POST", url)
        headers = {
            **oauth_headers,
            "Content-Type": "application/json",
        }

        logger.info(
            "x_api_posting_tweet",
            text_length=len(text),
            reply_to=reply_to,
        )

        response = await client.post(url, headers=headers, json=body)
        result = await self._handle_response(response, "post_tweet")

        # Parse the created tweet
        tweet_data = result.get("data", {})
        tweet = XTweet(
            id=tweet_data.get("id", ""),
            text=tweet_data.get("text", text),
            author_id=self.bot_user_id or "",
            conversation_id=tweet_data.get("conversation_id"),
            reply_to_tweet_id=reply_to,
            created_at=datetime.now(timezone.utc),
        )

        logger.info(
            "x_api_tweet_posted",
            tweet_id=tweet.id,
            reply_to=reply_to,
        )

        return tweet

    async def get_user(self, user_id: str) -> XUser:
        """Fetch user profile by ID."""
        client = await self._get_client()
        url = f"{X_API_BASE}/users/{user_id}"

        params = {"user.fields": self.USER_FIELDS}

        response = await client.get(
            url,
            headers=self._get_bearer_headers(),
            params=params,
        )

        result = await self._handle_response(response, f"get_user({user_id})")

        if "data" not in result:
            raise XNotFoundError(f"User {user_id} not found")

        return self._parse_user(result["data"])

    async def get_user_by_username(self, username: str) -> XUser:
        """Fetch user profile by username."""
        client = await self._get_client()
        # Remove @ if present
        username = username.lstrip("@")
        url = f"{X_API_BASE}/users/by/username/{username}"

        params = {"user.fields": self.USER_FIELDS}

        response = await client.get(
            url,
            headers=self._get_bearer_headers(),
            params=params,
        )

        result = await self._handle_response(response, f"get_user_by_username({username})")

        if "data" not in result:
            raise XNotFoundError(f"User @{username} not found")

        return self._parse_user(result["data"])

    async def get_tweet(self, tweet_id: str) -> XTweet:
        """Fetch a single tweet by ID."""
        client = await self._get_client()
        url = f"{X_API_BASE}/tweets/{tweet_id}"

        params = {
            "tweet.fields": self.TWEET_FIELDS,
            "user.fields": self.USER_FIELDS,
            "expansions": self.EXPANSIONS,
        }

        response = await client.get(
            url,
            headers=self._get_bearer_headers(),
            params=params,
        )

        result = await self._handle_response(response, f"get_tweet({tweet_id})")

        if "data" not in result:
            raise XNotFoundError(f"Tweet {tweet_id} not found")

        # Parse users from includes
        users_by_id: dict[str, XUser] = {}
        if "includes" in result and "users" in result["includes"]:
            for user_data in result["includes"]["users"]:
                user = self._parse_user(user_data)
                users_by_id[user.id] = user

        return self._parse_tweet(result["data"], users_by_id)

    async def delete_tweet(self, tweet_id: str) -> bool:
        """Delete a tweet."""
        if not self._oauth_signer:
            raise XAuthError("OAuth credentials not configured for deletion")

        client = await self._get_client()
        url = f"{X_API_BASE}/tweets/{tweet_id}"

        # Sign request with OAuth 1.0a
        oauth_headers = self._oauth_signer.sign_request("DELETE", url)

        logger.info("x_api_deleting_tweet", tweet_id=tweet_id)

        response = await client.delete(url, headers=oauth_headers)

        if response.status_code == 404:
            raise XNotFoundError(f"Tweet {tweet_id} not found")

        await self._handle_response(response, f"delete_tweet({tweet_id})")

        logger.info("x_api_tweet_deleted", tweet_id=tweet_id)

        return True

    async def health_check(self) -> bool:
        """
        Check if the provider is healthy by calling GET /2/users/me.

        Note: /2/users/me requires OAuth 1.0a user context, not Bearer token.
        """
        if not self._oauth_signer:
            logger.warning("x_api_health_check_failed", error="OAuth 1.0a credentials not configured")
            return False

        try:
            client = await self._get_client()
            url = f"{X_API_BASE}/users/me"

            # Use OAuth 1.0a signing (required for /users/me endpoint)
            headers = self._oauth_signer.sign_request("GET", url)

            response = await client.get(
                url,
                headers=headers,
                timeout=10.0,
            )

            if response.status_code == 200:
                logger.info("x_api_health_check_passed")
                return True
            else:
                # Log the actual error from X API
                try:
                    body = response.json()
                except Exception:
                    body = response.text[:500]
                logger.warning(
                    "x_api_health_check_failed",
                    status_code=response.status_code,
                    response=body,
                )
                return False
        except Exception as e:
            logger.warning("x_api_health_check_failed", error=str(e))
            return False

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

#!/usr/bin/env python3
"""
Jeffrey AIstein - X (Twitter) Credentials Verification Script

Verifies X API credentials using OAuth 1.0a authentication.
Run this BEFORE starting the X bot to ensure credentials are valid.

Usage:
    cd apps/api
    source venv/Scripts/activate  # Windows: venv\Scripts\activate
    python scripts/verify_x_credentials.py
"""

import base64
import hashlib
import hmac
import os
import random
import string
import sys
import time
import urllib.parse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Try to load .env from multiple locations
for env_path in [
    Path(__file__).parent.parent / ".env",
    Path(__file__).parent.parent.parent.parent / ".env",
    Path.cwd() / ".env",
]:
    if env_path.exists():
        print(f"Loading .env from: {env_path}")
        for line in env_path.read_text().splitlines():
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())
        break

try:
    import httpx
except ImportError:
    print("Installing httpx...")
    os.system(f"{sys.executable} -m pip install httpx")
    import httpx


def percent_encode(s: str) -> str:
    """RFC 3986 percent encoding."""
    return urllib.parse.quote(s, safe="")


def generate_nonce() -> str:
    """Generate a random nonce string."""
    return "".join(random.choices(string.ascii_letters + string.digits, k=32))


def create_oauth_signature(
    method: str,
    url: str,
    oauth_params: dict,
    consumer_secret: str,
    token_secret: str,
) -> str:
    """Create OAuth 1.0a HMAC-SHA1 signature."""
    # Sort and encode parameters
    sorted_params = sorted(oauth_params.items())
    param_string = "&".join(f"{percent_encode(k)}={percent_encode(str(v))}" for k, v in sorted_params)

    # Create signature base string
    base_string = "&".join([
        method.upper(),
        percent_encode(url),
        percent_encode(param_string),
    ])

    # Create signing key
    signing_key = f"{percent_encode(consumer_secret)}&{percent_encode(token_secret)}"

    # Generate signature
    signature = hmac.new(
        signing_key.encode("utf-8"),
        base_string.encode("utf-8"),
        hashlib.sha1,
    ).digest()

    return base64.b64encode(signature).decode("utf-8")


def create_oauth_header(
    method: str,
    url: str,
    consumer_key: str,
    consumer_secret: str,
    access_token: str,
    access_token_secret: str,
) -> str:
    """Create OAuth 1.0a Authorization header."""
    oauth_params = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": generate_nonce(),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": access_token,
        "oauth_version": "1.0",
    }

    # Generate signature
    signature = create_oauth_signature(
        method,
        url,
        oauth_params,
        consumer_secret,
        access_token_secret,
    )
    oauth_params["oauth_signature"] = signature

    # Build header string
    header_params = ", ".join(
        f'{percent_encode(k)}="{percent_encode(str(v))}"'
        for k, v in sorted(oauth_params.items())
    )

    return f"OAuth {header_params}"


def create_oauth_header_with_params(
    method: str,
    url: str,
    query_params: dict,
    consumer_key: str,
    consumer_secret: str,
    access_token: str,
    access_token_secret: str,
) -> str:
    """Create OAuth 1.0a Authorization header including query params in signature."""
    oauth_params = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": generate_nonce(),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": access_token,
        "oauth_version": "1.0",
    }

    # Combine OAuth params with query params for signature
    all_params = {**oauth_params, **query_params}

    # Generate signature
    signature = create_oauth_signature(
        method,
        url,
        all_params,
        consumer_secret,
        access_token_secret,
    )
    oauth_params["oauth_signature"] = signature

    # Build header string (only OAuth params, not query params)
    header_params = ", ".join(
        f'{percent_encode(k)}="{percent_encode(str(v))}"'
        for k, v in sorted(oauth_params.items())
    )

    return f"OAuth {header_params}"


def verify_oauth_credentials() -> dict | None:
    """
    Verify OAuth 1.0a credentials by calling GET /2/users/me.

    Returns:
        User data dict on success, None on failure
    """
    consumer_key = os.getenv("X_API_KEY")
    consumer_secret = os.getenv("X_API_SECRET")
    access_token = os.getenv("X_ACCESS_TOKEN")
    access_token_secret = os.getenv("X_ACCESS_TOKEN_SECRET")

    # Check all required credentials
    missing = []
    if not consumer_key:
        missing.append("X_API_KEY")
    if not consumer_secret:
        missing.append("X_API_SECRET")
    if not access_token:
        missing.append("X_ACCESS_TOKEN")
    if not access_token_secret:
        missing.append("X_ACCESS_TOKEN_SECRET")

    if missing:
        print(f"\n❌ Missing OAuth credentials: {', '.join(missing)}")
        print("   Set them in your .env file")
        return None

    print("\n🔍 Verifying OAuth 1.0a credentials...")
    print(f"   API Key prefix: {consumer_key[:10]}...")
    print(f"   Access Token prefix: {access_token[:10]}...")

    url = "https://api.x.com/2/users/me"
    params = {"user.fields": "id,username,name,created_at,verified,public_metrics"}

    # Create authorization header (including query params in signature)
    auth_header = create_oauth_header_with_params(
        "GET",
        url,
        params,
        consumer_key,
        consumer_secret,
        access_token,
        access_token_secret,
    )

    try:
        response = httpx.get(
            url,
            headers={"Authorization": auth_header},
            params=params,
            timeout=10,
        )

        if response.status_code == 200:
            data = response.json().get("data", {})
            print("   ✅ OAuth authentication successful!")
            return data
        elif response.status_code == 401:
            print(f"❌ FAILED: 401 Unauthorized")
            print("   OAuth credentials are invalid")
            print("   Regenerate Access Token at console.x.com")
            return None
        elif response.status_code == 403:
            print(f"❌ FAILED: 403 Forbidden")
            print("   App may need User Authentication settings configured")
            print("   Go to console.x.com > Apps > your app > Set up User Authentication")
            # Try to show more details
            try:
                error_data = response.json()
                if "detail" in error_data:
                    print(f"   Detail: {error_data['detail']}")
            except:
                pass
            return None
        elif response.status_code == 429:
            print(f"❌ FAILED: 429 Rate Limited")
            print("   Wait a few minutes and try again")
            return None
        else:
            print(f"❌ FAILED: {response.status_code}")
            print(f"   Response: {response.text[:300]}")
            return None

    except httpx.TimeoutException:
        print("❌ FAILED: Request timed out")
        return None
    except Exception as e:
        print(f"❌ FAILED: {type(e).__name__}: {e}")
        return None


def check_bot_user_id() -> bool:
    """Check if X_BOT_USER_ID is set."""
    bot_user_id = os.getenv("X_BOT_USER_ID")

    if bot_user_id:
        print(f"\n✓ X_BOT_USER_ID is set: {bot_user_id}")
        return True
    else:
        print("\n⚠️  X_BOT_USER_ID is NOT set")
        print("   The verification will show you the user ID to add to your .env")
        return False


def check_bearer_token() -> bool:
    """Check if Bearer token is set (optional for pay-per-use)."""
    bearer_token = os.getenv("X_BEARER_TOKEN")
    if bearer_token:
        print(f"\n✓ X_BEARER_TOKEN is set: {bearer_token[:20]}...")
        return True
    else:
        print("\n⚠️  X_BEARER_TOKEN is NOT set (may be optional for pay-per-use)")
        return False


def main():
    print("=" * 60)
    print("Jeffrey AIstein - X (Twitter) Credentials Verification")
    print("=" * 60)

    # Check if user ID is pre-configured
    check_bot_user_id()

    # Check bearer token (informational)
    check_bearer_token()

    # Verify OAuth 1.0a credentials (this is what matters for posting)
    user_data = verify_oauth_credentials()

    if user_data:
        print("\n" + "=" * 60)
        print("✅ X CREDENTIALS VERIFIED SUCCESSFULLY")
        print("=" * 60)
        print(f"\n   Bot Username:  @{user_data.get('username', 'unknown')}")
        print(f"   Bot Name:      {user_data.get('name', 'unknown')}")
        print(f"   Bot User ID:   {user_data.get('id', 'unknown')}")
        print(f"   Verified:      {user_data.get('verified', False)}")

        metrics = user_data.get("public_metrics", {})
        if metrics:
            print(f"   Followers:     {metrics.get('followers_count', 0):,}")
            print(f"   Following:     {metrics.get('following_count', 0):,}")
            print(f"   Tweets:        {metrics.get('tweet_count', 0):,}")

        # Suggest adding user ID to .env
        bot_user_id = os.getenv("X_BOT_USER_ID")
        if not bot_user_id or bot_user_id != user_data.get("id"):
            print(f"\n📝 Add/update this in your .env file:")
            print(f"   X_BOT_USER_ID={user_data.get('id')}")

        print("\n" + "-" * 60)
        print("✅ Ready for X bot operations (read + write)")
        print("-" * 60)

        return 0
    else:
        print("\n" + "=" * 60)
        print("❌ X CREDENTIALS VERIFICATION FAILED")
        print("=" * 60)
        print("\nTroubleshooting steps:")
        print("1. Go to console.x.com > Apps > your app")
        print("2. Click 'Set up' under User Authentication Settings")
        print("3. Set App Permissions to 'Read and write'")
        print("4. Set Type of App to 'Web App, Automated App or Bot'")
        print("5. Add callback URL: http://localhost:3000/callback")
        print("6. Save, then Regenerate your Access Token")
        print("7. Update credentials in your .env file")
        print("8. Run this script again")
        print("-" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())

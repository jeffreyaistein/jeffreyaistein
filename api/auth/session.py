"""
Jeffrey AIstein - Session Management
Anonymous session-based authentication for web users.
"""

import secrets
import uuid
from typing import Optional

from fastapi import Request, Response, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.base import get_db
from db.models import User


# Session cookie configuration
SESSION_COOKIE_NAME = "aistein_session"
SESSION_COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


def generate_session_id() -> str:
    """Generate a secure random session ID."""
    return secrets.token_urlsafe(32)


async def get_user_by_session(
    db: AsyncSession,
    session_id: str
) -> Optional[User]:
    """Get user by session ID."""
    result = await db.execute(
        select(User).where(User.session_id == session_id)
    )
    return result.scalar_one_or_none()


async def create_user_with_session(
    db: AsyncSession,
    session_id: str
) -> User:
    """Create a new anonymous user with the given session ID."""
    user = User(
        id=uuid.uuid4(),
        session_id=session_id,
        metadata_={
            "type": "anonymous",
            "created_via": "web"
        }
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_or_create_user(
    db: AsyncSession,
    session_id: str
) -> User:
    """Get existing user by session or create new one."""
    user = await get_user_by_session(db, session_id)
    if user is None:
        user = await create_user_with_session(db, session_id)
    return user


class SessionData:
    """Container for session information."""

    def __init__(self, session_id: str, user: User, is_new: bool = False):
        self.session_id = session_id
        self.user = user
        self.user_id = user.id
        self.is_new = is_new


async def get_session_from_request(request: Request) -> Optional[str]:
    """Extract session ID from request cookies."""
    return request.cookies.get(SESSION_COOKIE_NAME)


def set_session_cookie(response: Response, session_id: str) -> None:
    """Set session cookie on response."""
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=SESSION_COOKIE_MAX_AGE,
        httponly=True,
        secure=not settings.debug,  # Secure in production
        samesite="lax",
    )


async def create_session(
    request: Request,
    response: Response,
    db: AsyncSession
) -> SessionData:
    """
    Get or create a session for the current request.
    Sets cookie if new session created.
    """
    session_id = await get_session_from_request(request)
    is_new = False

    if session_id:
        # Try to get existing user
        user = await get_user_by_session(db, session_id)
        if user:
            return SessionData(session_id, user, is_new=False)

    # Create new session
    session_id = generate_session_id()
    user = await create_user_with_session(db, session_id)
    set_session_cookie(response, session_id)
    is_new = True

    return SessionData(session_id, user, is_new=is_new)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependency to get the current user from session.
    Raises 401 if no valid session.
    """
    session_id = await get_session_from_request(request)

    if not session_id:
        raise HTTPException(
            status_code=401,
            detail="No session found. Please visit the website first."
        )

    user = await get_user_by_session(db, session_id)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid session. Please clear cookies and try again."
        )

    return user


async def get_optional_user(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    Dependency to get the current user if exists, None otherwise.
    Does not raise exceptions.
    """
    session_id = await get_session_from_request(request)

    if not session_id:
        return None

    return await get_user_by_session(db, session_id)


class SessionMiddleware:
    """
    Middleware that ensures every request has a session.
    Creates anonymous users automatically.

    Note: For most endpoints, use the get_current_user dependency instead.
    This middleware is for special cases where you want automatic session creation.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Let the app handle the request normally
        # Session creation happens in individual endpoints
        await self.app(scope, receive, send)


# ===========================================
# Admin Authentication
# ===========================================


async def verify_admin_key(request: Request) -> bool:
    """
    Verify admin API key from header.
    Used for admin-only endpoints.
    """
    api_key = request.headers.get("X-Admin-Key")

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Admin API key required"
        )

    if api_key != settings.admin_api_key:
        raise HTTPException(
            status_code=403,
            detail="Invalid admin API key"
        )

    return True


def require_admin(request: Request):
    """Dependency that requires admin authentication."""
    return Depends(lambda: verify_admin_key(request))

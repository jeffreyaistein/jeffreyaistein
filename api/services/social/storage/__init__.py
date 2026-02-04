"""
Jeffrey AIstein - Storage Package

Factory functions for repository access.

Storage Selection Logic:
- If USE_MEMORY_STORAGE=true: Use in-memory storage (for testing/dev)
- If DATABASE_URL is set and USE_MEMORY_STORAGE is not true: Use Postgres
- Otherwise: Fallback to in-memory storage

In production (Fly.io), DATABASE_URL is always set, so Postgres is used by default.
Set USE_MEMORY_STORAGE=true explicitly to use memory storage for development.
"""

import os
from typing import Optional

import structlog

from services.social.storage.base import (
    # Data classes
    DraftEntry,
    DraftStatus,
    InboxEntry,
    PostEntry,
    ReplyLogEntry,
    Settings,
    ThreadState,
    UserLimitState,
    # Repository interfaces
    DraftRepository,
    InboxRepository,
    PostRepository,
    ReplyLogRepository,
    SettingsRepository,
    ThreadRepository,
    UserLimitRepository,
    # Setting keys
    SETTING_LAST_MENTION_ID,
    SETTING_LAST_REPLY_ID,
    SETTING_LAST_TIMELINE_POST,
    SETTING_NEXT_TIMELINE_POST,
    SETTING_SAFE_MODE,
    SETTING_APPROVAL_REQUIRED,
)
from services.social.types import PostStatus, PostType
from services.social.storage.memory import (
    InMemoryDraftRepository,
    InMemoryInboxRepository,
    InMemoryPostRepository,
    InMemoryReplyLogRepository,
    InMemorySettingsRepository,
    InMemoryThreadRepository,
    InMemoryUserLimitRepository,
)

logger = structlog.get_logger()


# Singleton instances
_inbox_repo: Optional[InboxRepository] = None
_post_repo: Optional[PostRepository] = None
_draft_repo: Optional[DraftRepository] = None
_reply_log_repo: Optional[ReplyLogRepository] = None
_thread_repo: Optional[ThreadRepository] = None
_user_limit_repo: Optional[UserLimitRepository] = None
_settings_repo: Optional[SettingsRepository] = None


def _use_memory_storage() -> bool:
    """
    Check if we should use in-memory storage.

    Priority:
    1. USE_MEMORY_STORAGE=true -> Use memory (explicit override)
    2. DATABASE_URL set -> Use Postgres
    3. No DATABASE_URL -> Use memory (fallback for local dev)
    """
    use_memory = os.getenv("USE_MEMORY_STORAGE", "").lower() in ("true", "1", "yes")
    if use_memory:
        return True

    db_url = os.getenv("DATABASE_URL")
    return not db_url


def get_inbox_repository() -> InboxRepository:
    """Get inbox repository instance."""
    global _inbox_repo
    if _inbox_repo is None:
        if _use_memory_storage():
            logger.info("storage_init", repo="inbox", type="memory")
            _inbox_repo = InMemoryInboxRepository()
        else:
            from services.social.storage.postgres import PostgresInboxRepository
            logger.info("storage_init", repo="inbox", type="postgres")
            _inbox_repo = PostgresInboxRepository()
    return _inbox_repo


def get_post_repository() -> PostRepository:
    """Get post repository instance."""
    global _post_repo
    if _post_repo is None:
        if _use_memory_storage():
            logger.info("storage_init", repo="post", type="memory")
            _post_repo = InMemoryPostRepository()
        else:
            from services.social.storage.postgres import PostgresPostRepository
            logger.info("storage_init", repo="post", type="postgres")
            _post_repo = PostgresPostRepository()
    return _post_repo


def get_draft_repository() -> DraftRepository:
    """Get draft repository instance."""
    global _draft_repo
    if _draft_repo is None:
        if _use_memory_storage():
            logger.info("storage_init", repo="draft", type="memory")
            _draft_repo = InMemoryDraftRepository()
        else:
            from services.social.storage.postgres import PostgresDraftRepository
            logger.info("storage_init", repo="draft", type="postgres")
            _draft_repo = PostgresDraftRepository()
    return _draft_repo


def get_reply_log_repository() -> ReplyLogRepository:
    """Get reply log repository instance."""
    global _reply_log_repo
    if _reply_log_repo is None:
        if _use_memory_storage():
            logger.info("storage_init", repo="reply_log", type="memory")
            _reply_log_repo = InMemoryReplyLogRepository()
        else:
            from services.social.storage.postgres import PostgresReplyLogRepository
            logger.info("storage_init", repo="reply_log", type="postgres")
            _reply_log_repo = PostgresReplyLogRepository()
    return _reply_log_repo


def get_thread_repository() -> ThreadRepository:
    """Get thread repository instance."""
    global _thread_repo
    if _thread_repo is None:
        if _use_memory_storage():
            logger.info("storage_init", repo="thread", type="memory")
            _thread_repo = InMemoryThreadRepository()
        else:
            from services.social.storage.postgres import PostgresThreadRepository
            logger.info("storage_init", repo="thread", type="postgres")
            _thread_repo = PostgresThreadRepository()
    return _thread_repo


def get_user_limit_repository() -> UserLimitRepository:
    """Get user limit repository instance."""
    global _user_limit_repo
    if _user_limit_repo is None:
        if _use_memory_storage():
            logger.info("storage_init", repo="user_limit", type="memory")
            _user_limit_repo = InMemoryUserLimitRepository()
        else:
            from services.social.storage.postgres import PostgresUserLimitRepository
            logger.info("storage_init", repo="user_limit", type="postgres")
            _user_limit_repo = PostgresUserLimitRepository()
    return _user_limit_repo


def get_settings_repository() -> SettingsRepository:
    """Get settings repository instance."""
    global _settings_repo
    if _settings_repo is None:
        if _use_memory_storage():
            logger.info("storage_init", repo="settings", type="memory")
            _settings_repo = InMemorySettingsRepository()
        else:
            from services.social.storage.postgres import PostgresSettingsRepository
            logger.info("storage_init", repo="settings", type="postgres")
            _settings_repo = PostgresSettingsRepository()
    return _settings_repo


def reset_all_repositories():
    """Reset all repository singletons (for testing)."""
    global _inbox_repo, _post_repo, _draft_repo, _reply_log_repo
    global _thread_repo, _user_limit_repo, _settings_repo

    _inbox_repo = None
    _post_repo = None
    _draft_repo = None
    _reply_log_repo = None
    _thread_repo = None
    _user_limit_repo = None
    _settings_repo = None


async def get_runtime_setting(key: str, env_var: str, default: str = "false") -> bool:
    """
    Get a runtime setting, checking database first then falling back to env var.

    Args:
        key: The setting key in the database (e.g., SETTING_SAFE_MODE)
        env_var: The environment variable name (e.g., "SAFE_MODE")
        default: Default value if neither db nor env var is set

    Returns:
        True if the setting is enabled (value is "true", "1", or "yes")
    """
    settings_repo = get_settings_repository()
    db_value = await settings_repo.get(key)

    if db_value is not None:
        return db_value.lower() in ("true", "1", "yes")

    # Convert default to string for os.getenv (it expects str, not bool)
    default_str = str(default).lower() if default is not None else "false"
    env_value = os.getenv(env_var, default_str)
    return str(env_value).lower() in ("true", "1", "yes")


__all__ = [
    # Data classes
    "DraftEntry",
    "DraftStatus",
    "InboxEntry",
    "PostEntry",
    "PostStatus",
    "PostType",
    "ReplyLogEntry",
    "Settings",
    "ThreadState",
    "UserLimitState",
    # Repository interfaces
    "DraftRepository",
    "InboxRepository",
    "PostRepository",
    "ReplyLogRepository",
    "SettingsRepository",
    "ThreadRepository",
    "UserLimitRepository",
    # In-memory implementations
    "InMemoryDraftRepository",
    "InMemoryInboxRepository",
    "InMemoryPostRepository",
    "InMemoryReplyLogRepository",
    "InMemorySettingsRepository",
    "InMemoryThreadRepository",
    "InMemoryUserLimitRepository",
    # Factory functions
    "get_inbox_repository",
    "get_post_repository",
    "get_draft_repository",
    "get_reply_log_repository",
    "get_thread_repository",
    "get_user_limit_repository",
    "get_settings_repository",
    "reset_all_repositories",
    # Setting keys
    "SETTING_LAST_MENTION_ID",
    "SETTING_LAST_REPLY_ID",
    "SETTING_LAST_TIMELINE_POST",
    "SETTING_NEXT_TIMELINE_POST",
    "SETTING_SAFE_MODE",
    "SETTING_APPROVAL_REQUIRED",
    # Utility
    "_use_memory_storage",
    "get_runtime_setting",
]

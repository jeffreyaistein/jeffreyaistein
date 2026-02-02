"""
Jeffrey AIstein - Storage Package

Factory functions for repository access.
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
    SETTING_LAST_TIMELINE_POST,
    SETTING_NEXT_TIMELINE_POST,
)
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
    """Check if we should use in-memory storage."""
    # For now, always use memory storage since Docker is blocked
    # In production, check for database URL
    db_url = os.getenv("DATABASE_URL")
    use_memory = os.getenv("USE_MEMORY_STORAGE", "").lower() in ("true", "1", "yes")
    return use_memory or not db_url


def get_inbox_repository() -> InboxRepository:
    """Get inbox repository instance."""
    global _inbox_repo
    if _inbox_repo is None:
        if _use_memory_storage():
            logger.info("storage_init", repo="inbox", type="memory")
            _inbox_repo = InMemoryInboxRepository()
        else:
            # TODO: Implement PostgresInboxRepository
            raise NotImplementedError("Postgres storage not yet implemented")
    return _inbox_repo


def get_post_repository() -> PostRepository:
    """Get post repository instance."""
    global _post_repo
    if _post_repo is None:
        if _use_memory_storage():
            logger.info("storage_init", repo="post", type="memory")
            _post_repo = InMemoryPostRepository()
        else:
            raise NotImplementedError("Postgres storage not yet implemented")
    return _post_repo


def get_draft_repository() -> DraftRepository:
    """Get draft repository instance."""
    global _draft_repo
    if _draft_repo is None:
        if _use_memory_storage():
            logger.info("storage_init", repo="draft", type="memory")
            _draft_repo = InMemoryDraftRepository()
        else:
            raise NotImplementedError("Postgres storage not yet implemented")
    return _draft_repo


def get_reply_log_repository() -> ReplyLogRepository:
    """Get reply log repository instance."""
    global _reply_log_repo
    if _reply_log_repo is None:
        if _use_memory_storage():
            logger.info("storage_init", repo="reply_log", type="memory")
            _reply_log_repo = InMemoryReplyLogRepository()
        else:
            raise NotImplementedError("Postgres storage not yet implemented")
    return _reply_log_repo


def get_thread_repository() -> ThreadRepository:
    """Get thread repository instance."""
    global _thread_repo
    if _thread_repo is None:
        if _use_memory_storage():
            logger.info("storage_init", repo="thread", type="memory")
            _thread_repo = InMemoryThreadRepository()
        else:
            raise NotImplementedError("Postgres storage not yet implemented")
    return _thread_repo


def get_user_limit_repository() -> UserLimitRepository:
    """Get user limit repository instance."""
    global _user_limit_repo
    if _user_limit_repo is None:
        if _use_memory_storage():
            logger.info("storage_init", repo="user_limit", type="memory")
            _user_limit_repo = InMemoryUserLimitRepository()
        else:
            raise NotImplementedError("Postgres storage not yet implemented")
    return _user_limit_repo


def get_settings_repository() -> SettingsRepository:
    """Get settings repository instance."""
    global _settings_repo
    if _settings_repo is None:
        if _use_memory_storage():
            logger.info("storage_init", repo="settings", type="memory")
            _settings_repo = InMemorySettingsRepository()
        else:
            raise NotImplementedError("Postgres storage not yet implemented")
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


__all__ = [
    # Data classes
    "DraftEntry",
    "DraftStatus",
    "InboxEntry",
    "PostEntry",
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
    "SETTING_LAST_TIMELINE_POST",
    "SETTING_NEXT_TIMELINE_POST",
]

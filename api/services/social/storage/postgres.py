"""
Jeffrey AIstein - Postgres Storage Implementations

Production-grade Postgres implementations for X bot state management.
Data persists across restarts, enabling proper approval workflows.
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import async_session_maker
from services.social.storage.base import (
    DraftEntry,
    DraftRepository,
    DraftStatus,
    InboxEntry,
    InboxRepository,
    PostEntry,
    PostRepository,
    PostStatus,
    ReplyLogEntry,
    ReplyLogRepository,
    Settings,
    SettingsRepository,
    ThreadRepository,
    ThreadState,
    UserLimitRepository,
    UserLimitState,
)
from services.social.types import XTweet, XUser

logger = structlog.get_logger()


def _serialize_tweet(tweet: XTweet) -> dict:
    """Serialize XTweet to JSON-compatible dict."""
    data = {
        "id": tweet.id,
        "text": tweet.text,
        "author_id": tweet.author_id,
        "conversation_id": tweet.conversation_id,
        "reply_to_tweet_id": tweet.reply_to_tweet_id,
        "reply_to_user_id": tweet.reply_to_user_id,
        "created_at": tweet.created_at.isoformat() if tweet.created_at else None,
    }
    if tweet.author:
        data["author"] = {
            "id": tweet.author.id,
            "username": tweet.author.username,
            "name": tweet.author.name,
            "created_at": tweet.author.created_at.isoformat(),
            "followers_count": tweet.author.followers_count,
            "following_count": tweet.author.following_count,
            "tweet_count": tweet.author.tweet_count,
            "verified": tweet.author.verified,
            "description": tweet.author.description,
            "location": tweet.author.location,
            "profile_image_url": tweet.author.profile_image_url,
            "default_profile_image": tweet.author.default_profile_image,
        }
    return data


def _deserialize_tweet(data: dict) -> XTweet:
    """Deserialize XTweet from JSON dict."""
    author = None
    if "author" in data and data["author"]:
        author_data = data["author"]
        author = XUser(
            id=author_data["id"],
            username=author_data["username"],
            name=author_data["name"],
            created_at=datetime.fromisoformat(author_data["created_at"]),
            followers_count=author_data.get("followers_count", 0),
            following_count=author_data.get("following_count", 0),
            tweet_count=author_data.get("tweet_count", 0),
            verified=author_data.get("verified", False),
            description=author_data.get("description"),
            location=author_data.get("location"),
            profile_image_url=author_data.get("profile_image_url"),
            default_profile_image=author_data.get("default_profile_image", True),
        )

    created_at = None
    if data.get("created_at"):
        created_at = datetime.fromisoformat(data["created_at"])

    return XTweet(
        id=data["id"],
        text=data["text"],
        author_id=data["author_id"],
        conversation_id=data.get("conversation_id"),
        reply_to_tweet_id=data.get("reply_to_tweet_id"),
        reply_to_user_id=data.get("reply_to_user_id"),
        created_at=created_at,
        author=author,
    )


class PostgresDraftRepository(DraftRepository):
    """Postgres-backed draft repository."""

    async def _get_session(self) -> AsyncSession:
        return async_session_maker()

    async def save(self, entry: DraftEntry) -> DraftEntry:
        async with await self._get_session() as session:
            # Upsert the draft
            await session.execute(
                text("""
                    INSERT INTO x_drafts (id, text, post_type, reply_to_id, status, created_at, approved_at, rejected_at, rejection_reason)
                    VALUES (:id, :text, :post_type, :reply_to_id, :status, :created_at, :approved_at, :rejected_at, :rejection_reason)
                    ON CONFLICT (id) DO UPDATE SET
                        text = EXCLUDED.text,
                        status = EXCLUDED.status,
                        approved_at = EXCLUDED.approved_at,
                        rejected_at = EXCLUDED.rejected_at,
                        rejection_reason = EXCLUDED.rejection_reason
                """),
                {
                    "id": entry.id,
                    "text": entry.text,
                    "post_type": entry.post_type.value if hasattr(entry.post_type, 'value') else entry.post_type,
                    "reply_to_id": entry.reply_to_id,
                    "status": entry.status.value if hasattr(entry.status, 'value') else entry.status,
                    "created_at": entry.created_at or datetime.now(timezone.utc),
                    "approved_at": entry.approved_at,
                    "rejected_at": entry.rejected_at,
                    "rejection_reason": entry.rejection_reason,
                }
            )
            await session.commit()
            logger.debug("draft_entry_saved", draft_id=entry.id)
            return entry

    async def get(self, draft_id: str) -> Optional[DraftEntry]:
        async with await self._get_session() as session:
            result = await session.execute(
                text("SELECT * FROM x_drafts WHERE id = :id"),
                {"id": draft_id}
            )
            row = result.mappings().fetchone()
            if not row:
                return None

            from services.social.types import PostType
            return DraftEntry(
                id=row["id"],
                text=row["text"],
                post_type=PostType(row["post_type"]),
                reply_to_id=row["reply_to_id"],
                status=DraftStatus(row["status"]),
                created_at=row["created_at"],
                approved_at=row["approved_at"],
                rejected_at=row["rejected_at"],
                rejection_reason=row["rejection_reason"],
            )

    async def list_pending(self, limit: int = 100) -> list[DraftEntry]:
        async with await self._get_session() as session:
            result = await session.execute(
                text("""
                    SELECT * FROM x_drafts
                    WHERE status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT :limit
                """),
                {"limit": limit}
            )
            rows = result.mappings().fetchall()

            from services.social.types import PostType
            return [
                DraftEntry(
                    id=row["id"],
                    text=row["text"],
                    post_type=PostType(row["post_type"]),
                    reply_to_id=row["reply_to_id"],
                    status=DraftStatus(row["status"]),
                    created_at=row["created_at"],
                    approved_at=row["approved_at"],
                    rejected_at=row["rejected_at"],
                    rejection_reason=row["rejection_reason"],
                )
                for row in rows
            ]

    async def approve(self, draft_id: str) -> bool:
        async with await self._get_session() as session:
            result = await session.execute(
                text("""
                    UPDATE x_drafts
                    SET status = 'approved', approved_at = :now
                    WHERE id = :id AND status = 'pending'
                """),
                {"id": draft_id, "now": datetime.now(timezone.utc)}
            )
            await session.commit()
            return result.rowcount > 0

    async def reject(self, draft_id: str, reason: Optional[str] = None) -> bool:
        async with await self._get_session() as session:
            result = await session.execute(
                text("""
                    UPDATE x_drafts
                    SET status = 'rejected', rejected_at = :now, rejection_reason = :reason
                    WHERE id = :id AND status = 'pending'
                """),
                {"id": draft_id, "now": datetime.now(timezone.utc), "reason": reason}
            )
            await session.commit()
            return result.rowcount > 0


class PostgresInboxRepository(InboxRepository):
    """Postgres-backed inbox repository."""

    async def _get_session(self) -> AsyncSession:
        return async_session_maker()

    async def save(self, entry: InboxEntry) -> InboxEntry:
        async with await self._get_session() as session:
            tweet_data = _serialize_tweet(entry.tweet)
            await session.execute(
                text("""
                    INSERT INTO x_inbox (id, tweet_data, author_id, quality_score, received_at, processed, processed_at, skipped, skip_reason)
                    VALUES (:id, :tweet_data, :author_id, :quality_score, :received_at, :processed, :processed_at, :skipped, :skip_reason)
                    ON CONFLICT (id) DO UPDATE SET
                        processed = EXCLUDED.processed,
                        processed_at = EXCLUDED.processed_at,
                        skipped = EXCLUDED.skipped,
                        skip_reason = EXCLUDED.skip_reason
                """),
                {
                    "id": entry.id,
                    "tweet_data": json.dumps(tweet_data),
                    "author_id": entry.author_id,
                    "quality_score": entry.quality_score,
                    "received_at": entry.received_at,
                    "processed": entry.processed,
                    "processed_at": entry.processed_at,
                    "skipped": entry.skipped,
                    "skip_reason": entry.skip_reason,
                }
            )
            await session.commit()
            logger.debug("inbox_entry_saved", tweet_id=entry.id)
            return entry

    async def get(self, tweet_id: str) -> Optional[InboxEntry]:
        async with await self._get_session() as session:
            result = await session.execute(
                text("SELECT * FROM x_inbox WHERE id = :id"),
                {"id": tweet_id}
            )
            row = result.mappings().fetchone()
            if not row:
                return None

            tweet_data = row["tweet_data"]
            if isinstance(tweet_data, str):
                tweet_data = json.loads(tweet_data)

            return InboxEntry(
                id=row["id"],
                tweet=_deserialize_tweet(tweet_data),
                author_id=row["author_id"],
                quality_score=row["quality_score"],
                received_at=row["received_at"],
                processed=row["processed"],
                processed_at=row["processed_at"],
                skipped=row["skipped"],
                skip_reason=row["skip_reason"],
            )

    async def exists(self, tweet_id: str) -> bool:
        async with await self._get_session() as session:
            result = await session.execute(
                text("SELECT 1 FROM x_inbox WHERE id = :id"),
                {"id": tweet_id}
            )
            return result.fetchone() is not None

    async def list_unprocessed(self, limit: int = 100) -> list[InboxEntry]:
        async with await self._get_session() as session:
            result = await session.execute(
                text("""
                    SELECT * FROM x_inbox
                    WHERE processed = false
                    ORDER BY received_at ASC
                    LIMIT :limit
                """),
                {"limit": limit}
            )
            rows = result.mappings().fetchall()

            entries = []
            for row in rows:
                tweet_data = row["tweet_data"]
                if isinstance(tweet_data, str):
                    tweet_data = json.loads(tweet_data)

                entries.append(InboxEntry(
                    id=row["id"],
                    tweet=_deserialize_tweet(tweet_data),
                    author_id=row["author_id"],
                    quality_score=row["quality_score"],
                    received_at=row["received_at"],
                    processed=row["processed"],
                    processed_at=row["processed_at"],
                    skipped=row["skipped"],
                    skip_reason=row["skip_reason"],
                ))
            return entries

    async def mark_processed(
        self,
        tweet_id: str,
        skipped: bool = False,
        skip_reason: Optional[str] = None,
    ) -> bool:
        async with await self._get_session() as session:
            result = await session.execute(
                text("""
                    UPDATE x_inbox
                    SET processed = true, processed_at = :now, skipped = :skipped, skip_reason = :skip_reason
                    WHERE id = :id
                """),
                {
                    "id": tweet_id,
                    "now": datetime.now(timezone.utc),
                    "skipped": skipped,
                    "skip_reason": skip_reason,
                }
            )
            await session.commit()
            return result.rowcount > 0


class PostgresPostRepository(PostRepository):
    """Postgres-backed post repository."""

    async def _get_session(self) -> AsyncSession:
        return async_session_maker()

    async def save(self, entry: PostEntry) -> PostEntry:
        async with await self._get_session() as session:
            await session.execute(
                text("""
                    INSERT INTO x_posts (id, tweet_id, text, post_type, reply_to_id, status, created_at, posted_at)
                    VALUES (:id, :tweet_id, :text, :post_type, :reply_to_id, :status, :created_at, :posted_at)
                    ON CONFLICT (id) DO UPDATE SET
                        tweet_id = EXCLUDED.tweet_id,
                        status = EXCLUDED.status,
                        posted_at = EXCLUDED.posted_at
                """),
                {
                    "id": entry.id,
                    "tweet_id": entry.tweet_id,
                    "text": entry.text,
                    "post_type": entry.post_type.value if hasattr(entry.post_type, 'value') else entry.post_type,
                    "reply_to_id": entry.reply_to_id,
                    "status": entry.status.value if hasattr(entry.status, 'value') else entry.status,
                    "created_at": entry.created_at or datetime.now(timezone.utc),
                    "posted_at": entry.posted_at,
                }
            )
            await session.commit()
            logger.debug("post_entry_saved", post_id=entry.id, tweet_id=entry.tweet_id)
            return entry

    async def get(self, post_id: str) -> Optional[PostEntry]:
        async with await self._get_session() as session:
            result = await session.execute(
                text("SELECT * FROM x_posts WHERE id = :id"),
                {"id": post_id}
            )
            row = result.mappings().fetchone()
            if not row:
                return None

            from services.social.types import PostType
            return PostEntry(
                id=row["id"],
                tweet_id=row["tweet_id"],
                text=row["text"],
                post_type=PostType(row["post_type"]),
                reply_to_id=row["reply_to_id"],
                status=PostStatus(row["status"]),
                created_at=row["created_at"],
                posted_at=row["posted_at"],
            )

    async def get_by_tweet_id(self, tweet_id: str) -> Optional[PostEntry]:
        async with await self._get_session() as session:
            result = await session.execute(
                text("SELECT * FROM x_posts WHERE tweet_id = :tweet_id"),
                {"tweet_id": tweet_id}
            )
            row = result.mappings().fetchone()
            if not row:
                return None

            from services.social.types import PostType
            return PostEntry(
                id=row["id"],
                tweet_id=row["tweet_id"],
                text=row["text"],
                post_type=PostType(row["post_type"]),
                reply_to_id=row["reply_to_id"],
                status=PostStatus(row["status"]),
                created_at=row["created_at"],
                posted_at=row["posted_at"],
            )

    async def update_status(
        self,
        post_id: str,
        status: PostStatus,
        tweet_id: Optional[str] = None,
    ) -> bool:
        async with await self._get_session() as session:
            posted_at = datetime.now(timezone.utc) if status == PostStatus.POSTED else None
            result = await session.execute(
                text("""
                    UPDATE x_posts
                    SET status = :status, tweet_id = COALESCE(:tweet_id, tweet_id), posted_at = COALESCE(:posted_at, posted_at)
                    WHERE id = :id
                """),
                {
                    "id": post_id,
                    "status": status.value,
                    "tweet_id": tweet_id,
                    "posted_at": posted_at,
                }
            )
            await session.commit()
            return result.rowcount > 0

    async def count_today(self) -> int:
        async with await self._get_session() as session:
            result = await session.execute(
                text("""
                    SELECT COUNT(*) FROM x_posts
                    WHERE posted_at >= :today_start AND status = 'posted'
                """),
                {"today_start": datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)}
            )
            return result.scalar() or 0

    async def count_last_hour(self) -> int:
        async with await self._get_session() as session:
            result = await session.execute(
                text("""
                    SELECT COUNT(*) FROM x_posts
                    WHERE posted_at >= :one_hour_ago AND status = 'posted'
                """),
                {"one_hour_ago": datetime.now(timezone.utc) - timedelta(hours=1)}
            )
            return result.scalar() or 0

    async def list_recent(self, limit: int = 10) -> list[PostEntry]:
        """List recent posts (for conversation tracking)."""
        async with await self._get_session() as session:
            result = await session.execute(
                text("""
                    SELECT * FROM x_posts
                    WHERE status = 'posted' AND tweet_id IS NOT NULL
                    ORDER BY posted_at DESC
                    LIMIT :limit
                """),
                {"limit": limit}
            )
            rows = result.mappings().fetchall()

            from services.social.types import PostType
            return [
                PostEntry(
                    id=row["id"],
                    tweet_id=row["tweet_id"],
                    text=row["text"],
                    post_type=PostType(row["post_type"]),
                    reply_to_id=row["reply_to_id"],
                    status=PostStatus(row["status"]),
                    created_at=row["created_at"],
                    posted_at=row["posted_at"],
                )
                for row in rows
            ]


class PostgresReplyLogRepository(ReplyLogRepository):
    """Postgres-backed reply log repository for idempotency."""

    async def _get_session(self) -> AsyncSession:
        return async_session_maker()

    async def save(self, entry: ReplyLogEntry) -> ReplyLogEntry:
        async with await self._get_session() as session:
            await session.execute(
                text("""
                    INSERT INTO x_reply_log (tweet_id, reply_tweet_id, replied_at)
                    VALUES (:tweet_id, :reply_tweet_id, :replied_at)
                    ON CONFLICT (tweet_id) DO NOTHING
                """),
                {
                    "tweet_id": entry.tweet_id,
                    "reply_tweet_id": entry.reply_tweet_id,
                    "replied_at": entry.replied_at,
                }
            )
            await session.commit()
            logger.debug(
                "reply_log_saved",
                tweet_id=entry.tweet_id,
                reply_tweet_id=entry.reply_tweet_id,
            )
            return entry

    async def has_replied(self, tweet_id: str) -> bool:
        async with await self._get_session() as session:
            result = await session.execute(
                text("SELECT 1 FROM x_reply_log WHERE tweet_id = :tweet_id"),
                {"tweet_id": tweet_id}
            )
            return result.fetchone() is not None

    async def get(self, tweet_id: str) -> Optional[ReplyLogEntry]:
        async with await self._get_session() as session:
            result = await session.execute(
                text("SELECT * FROM x_reply_log WHERE tweet_id = :tweet_id"),
                {"tweet_id": tweet_id}
            )
            row = result.mappings().fetchone()
            if not row:
                return None

            return ReplyLogEntry(
                tweet_id=row["tweet_id"],
                reply_tweet_id=row["reply_tweet_id"],
                replied_at=row["replied_at"],
            )


class PostgresThreadRepository(ThreadRepository):
    """Postgres-backed thread state repository."""

    async def _get_session(self) -> AsyncSession:
        return async_session_maker()

    async def save(self, state: ThreadState) -> ThreadState:
        async with await self._get_session() as session:
            await session.execute(
                text("""
                    INSERT INTO x_threads (conversation_id, author_id, our_reply_count, last_reply_at, stopped, stop_reason)
                    VALUES (:conversation_id, :author_id, :our_reply_count, :last_reply_at, :stopped, :stop_reason)
                    ON CONFLICT (conversation_id) DO UPDATE SET
                        our_reply_count = EXCLUDED.our_reply_count,
                        last_reply_at = EXCLUDED.last_reply_at,
                        stopped = EXCLUDED.stopped,
                        stop_reason = EXCLUDED.stop_reason
                """),
                {
                    "conversation_id": state.conversation_id,
                    "author_id": state.author_id,
                    "our_reply_count": state.our_reply_count,
                    "last_reply_at": state.last_reply_at,
                    "stopped": state.stopped,
                    "stop_reason": state.stop_reason,
                }
            )
            await session.commit()
            logger.debug(
                "thread_state_saved",
                conversation_id=state.conversation_id,
                reply_count=state.our_reply_count,
            )
            return state

    async def get(self, conversation_id: str) -> Optional[ThreadState]:
        async with await self._get_session() as session:
            result = await session.execute(
                text("SELECT * FROM x_threads WHERE conversation_id = :conversation_id"),
                {"conversation_id": conversation_id}
            )
            row = result.mappings().fetchone()
            if not row:
                return None

            return ThreadState(
                conversation_id=row["conversation_id"],
                author_id=row["author_id"],
                our_reply_count=row["our_reply_count"],
                last_reply_at=row["last_reply_at"],
                stopped=row["stopped"],
                stop_reason=row["stop_reason"],
            )

    async def increment_reply_count(self, conversation_id: str) -> int:
        async with await self._get_session() as session:
            result = await session.execute(
                text("""
                    INSERT INTO x_threads (conversation_id, author_id, our_reply_count, last_reply_at)
                    VALUES (:conversation_id, '', 1, :now)
                    ON CONFLICT (conversation_id) DO UPDATE SET
                        our_reply_count = x_threads.our_reply_count + 1,
                        last_reply_at = :now
                    RETURNING our_reply_count
                """),
                {"conversation_id": conversation_id, "now": datetime.now(timezone.utc)}
            )
            await session.commit()
            row = result.fetchone()
            return row[0] if row else 1

    async def stop_thread(self, conversation_id: str, reason: str) -> bool:
        async with await self._get_session() as session:
            await session.execute(
                text("""
                    INSERT INTO x_threads (conversation_id, author_id, stopped, stop_reason)
                    VALUES (:conversation_id, '', true, :reason)
                    ON CONFLICT (conversation_id) DO UPDATE SET
                        stopped = true,
                        stop_reason = :reason
                """),
                {"conversation_id": conversation_id, "reason": reason}
            )
            await session.commit()
            logger.info(
                "thread_stopped",
                conversation_id=conversation_id,
                reason=reason,
            )
            return True

    async def is_stopped(self, conversation_id: str) -> bool:
        async with await self._get_session() as session:
            result = await session.execute(
                text("SELECT stopped FROM x_threads WHERE conversation_id = :conversation_id"),
                {"conversation_id": conversation_id}
            )
            row = result.fetchone()
            return row[0] if row else False


class PostgresUserLimitRepository(UserLimitRepository):
    """Postgres-backed per-user daily limit repository."""

    async def _get_session(self) -> AsyncSession:
        return async_session_maker()

    async def get_today_count(self, user_id: str) -> int:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        async with await self._get_session() as session:
            result = await session.execute(
                text("SELECT reply_count FROM x_user_limits WHERE user_id = :user_id AND date = :date"),
                {"user_id": user_id, "date": date}
            )
            row = result.fetchone()
            return row[0] if row else 0

    async def increment(self, user_id: str) -> int:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        async with await self._get_session() as session:
            result = await session.execute(
                text("""
                    INSERT INTO x_user_limits (user_id, date, reply_count)
                    VALUES (:user_id, :date, 1)
                    ON CONFLICT (user_id, date) DO UPDATE SET
                        reply_count = x_user_limits.reply_count + 1
                    RETURNING reply_count
                """),
                {"user_id": user_id, "date": date}
            )
            await session.commit()
            row = result.fetchone()
            logger.debug(
                "user_limit_incremented",
                user_id=user_id,
                date=date,
                count=row[0] if row else 1,
            )
            return row[0] if row else 1

    async def reset_for_day(self, date: str) -> int:
        async with await self._get_session() as session:
            result = await session.execute(
                text("DELETE FROM x_user_limits WHERE date < :date"),
                {"date": date}
            )
            await session.commit()
            return result.rowcount or 0


class PostgresSettingsRepository(SettingsRepository):
    """Postgres-backed settings repository."""

    async def _get_session(self) -> AsyncSession:
        return async_session_maker()

    async def get(self, key: str) -> Optional[str]:
        async with await self._get_session() as session:
            result = await session.execute(
                text("SELECT value FROM x_settings WHERE key = :key"),
                {"key": key}
            )
            row = result.fetchone()
            return row[0] if row else None

    async def set(self, key: str, value: str) -> bool:
        async with await self._get_session() as session:
            await session.execute(
                text("""
                    INSERT INTO x_settings (key, value, updated_at)
                    VALUES (:key, :value, :now)
                    ON CONFLICT (key) DO UPDATE SET
                        value = EXCLUDED.value,
                        updated_at = EXCLUDED.updated_at
                """),
                {"key": key, "value": value, "now": datetime.now(timezone.utc)}
            )
            await session.commit()
            return True

    async def delete(self, key: str) -> bool:
        async with await self._get_session() as session:
            result = await session.execute(
                text("DELETE FROM x_settings WHERE key = :key"),
                {"key": key}
            )
            await session.commit()
            return result.rowcount > 0

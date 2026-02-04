"""
Jeffrey AIstein - API Gateway
FastAPI application entry point
"""

import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

import redis.asyncio as aioredis
import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Request, Response, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.base import get_db, engine, async_session_maker
from db.models import User, Conversation, Message, Event
from auth.session import (
    create_session,
    verify_admin_key,
)
from services.chat import ChatService, ChatContext
from services.llm import get_llm_provider
from services.social.providers import get_x_provider
from services.social.scheduler import (
    IngestionLoop,
    TimelinePosterLoop,
    LearningWorker,
    SelfStyleWorker,
    is_self_style_enabled,
)
from services.social.storage import (
    DraftStatus,
    get_draft_repository,
    get_post_repository,
    get_settings_repository,
    get_runtime_setting,
    PostEntry,
    PostStatus,
    SETTING_SAFE_MODE,
    SETTING_APPROVAL_REQUIRED,
)
from services.social.types import PostType
from services.persona.style_rewriter import (
    get_style_rewriter,
    reload_style_rewriter_async,
    _validate_hard_constraints,
)
from services.persona.kol_profiles import get_kol_loader
from services.persona.blender import (
    get_blend_settings,
    get_persona_status as get_blender_status,
    build_and_save_persona,
    get_compiled_persona,
)

logger = structlog.get_logger()


def is_x_bot_enabled() -> bool:
    """Check if X bot is enabled."""
    return os.getenv("X_BOT_ENABLED", "").lower() in ("true", "1", "yes")


# Global references to scheduler loops for admin control
_ingestion_loop: Optional[IngestionLoop] = None
_timeline_loop: Optional[TimelinePosterLoop] = None
_learning_worker: Optional[LearningWorker] = None
_self_style_worker: Optional[SelfStyleWorker] = None
_scheduler_tasks: list[asyncio.Task] = []


def get_ingestion_loop() -> Optional[IngestionLoop]:
    """Get the ingestion loop instance (if running)."""
    return _ingestion_loop


def get_timeline_loop() -> Optional[TimelinePosterLoop]:
    """Get the timeline poster loop instance (if running)."""
    return _timeline_loop


def get_learning_worker() -> Optional[LearningWorker]:
    """Get the learning worker instance (if running)."""
    return _learning_worker


def get_self_style_worker() -> Optional[SelfStyleWorker]:
    """Get the self-style worker instance (if created)."""
    return _self_style_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global _ingestion_loop, _timeline_loop, _learning_worker, _self_style_worker, _scheduler_tasks

    print("AIstein API starting up...")
    logger.info("api_startup")

    # Log TTS configuration status
    from services.tts import is_tts_configured
    tts_configured = is_tts_configured()
    logger.info(
        "tts_config_status",
        elevenlabs_configured=tts_configured,
        api_key_set=bool(settings.elevenlabs_api_key),
        voice_id_set=bool(settings.elevenlabs_voice_id),
        enabled=settings.enable_tts,
    )
    print(f"TTS: elevenlabs_configured={tts_configured}")

    # Start SelfStyleWorker if enabled (independent of X bot)
    # Worker handles its own gating (SELF_STYLE_ENABLED, Redis availability)
    _self_style_worker = SelfStyleWorker()
    if is_self_style_enabled():
        logger.info("self_style_worker_creating", enabled=True)
        self_style_task = asyncio.create_task(
            _self_style_worker.start(),
            name="self_style_worker",
        )
        _scheduler_tasks.append(self_style_task)
    else:
        logger.info("self_style_worker_disabled", reason="SELF_STYLE_ENABLED not set")

    # Start X bot scheduler loops if enabled
    if is_x_bot_enabled():
        logger.info("x_bot_starting", enabled=True)

        try:
            x_provider = get_x_provider()

            # Verify provider health
            is_healthy = await x_provider.health_check()
            if not is_healthy:
                logger.error("x_provider_health_check_failed")
            else:
                logger.info("x_provider_health_check_passed")

                # Create scheduler loop instances
                _ingestion_loop = IngestionLoop(x_provider=x_provider)
                _timeline_loop = TimelinePosterLoop(x_provider=x_provider)
                _learning_worker = LearningWorker()

                # Start as background tasks
                ingestion_task = asyncio.create_task(
                    _ingestion_loop.start(),
                    name="x_ingestion_loop",
                )
                timeline_task = asyncio.create_task(
                    _timeline_loop.start(),
                    name="x_timeline_loop",
                )
                learning_task = asyncio.create_task(
                    _learning_worker.start(),
                    name="x_learning_worker",
                )
                _scheduler_tasks = [ingestion_task, timeline_task, learning_task]

                logger.info(
                    "x_bot_schedulers_started",
                    ingestion_interval=_ingestion_loop.poll_interval,
                    timeline_interval=_timeline_loop.interval,
                    learning_interval=_learning_worker.interval,
                )

        except Exception as e:
            logger.exception("x_bot_startup_failed", error=str(e))
    else:
        logger.info("x_bot_disabled", reason="X_BOT_ENABLED not set")

    yield

    # Shutdown
    print("AIstein API shutting down...")
    logger.info("api_shutdown")

    # Stop X bot scheduler loops gracefully
    if _ingestion_loop:
        logger.info("stopping_ingestion_loop")
        await _ingestion_loop.stop()

    if _timeline_loop:
        logger.info("stopping_timeline_loop")
        await _timeline_loop.stop()

    if _learning_worker:
        logger.info("stopping_learning_worker")
        await _learning_worker.stop()

    if _self_style_worker and _self_style_worker._running:
        logger.info("stopping_self_style_worker")
        await _self_style_worker.stop()

    # Wait for tasks to complete (with timeout)
    if _scheduler_tasks:
        logger.info("waiting_for_scheduler_tasks", count=len(_scheduler_tasks))
        done, pending = await asyncio.wait(
            _scheduler_tasks,
            timeout=10.0,
            return_when=asyncio.ALL_COMPLETED,
        )
        for task in pending:
            logger.warning("cancelling_stuck_task", task_name=task.get_name())
            task.cancel()

    # Reset globals
    _ingestion_loop = None
    _timeline_loop = None
    _learning_worker = None
    _self_style_worker = None
    _scheduler_tasks = []

    await engine.dispose()
    logger.info("api_shutdown_complete")


# Create FastAPI application
app = FastAPI(
    title="Jeffrey AIstein API",
    description="AGI-style agent with memory, hologram avatar, and social presence",
    version="0.1.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===========================================
# Pydantic Models
# ===========================================


class CreateConversationRequest(BaseModel):
    title: Optional[str] = None


class ConversationResponse(BaseModel):
    id: str
    user_id: str
    title: Optional[str]
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime
    metadata: dict = {}

    class Config:
        from_attributes = True


class ConversationWithMessagesResponse(BaseModel):
    id: str
    title: Optional[str]
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse]
    has_more_messages: bool = False

    class Config:
        from_attributes = True


class ConversationListResponse(BaseModel):
    conversations: List[ConversationResponse]
    total: int
    has_more: bool


# ===========================================
# Root & Health Endpoints
# ===========================================


@app.get("/")
async def root():
    """Root endpoint - confirms API is running."""
    return {"ok": True, "service": "Jeffrey AIstein API", "version": "0.1.0"}


@app.get("/health")
async def health():
    """Basic health check."""
    return {"status": "ok"}


@app.get("/health/ready")
async def ready(db: AsyncSession = Depends(get_db)):
    """Readiness check with dependency status."""
    db_ok = False
    db_error = None
    try:
        await db.execute(select(1))
        db_ok = True
    except Exception as e:
        db_error = f"{type(e).__name__}: {e}"
        logger.warning("health_check_db_failed", error=db_error, exc_info=True)

    # Check Redis connectivity
    redis_ok = False
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        try:
            redis_client = aioredis.from_url(redis_url)
            await redis_client.ping()
            redis_ok = True
            await redis_client.close()
        except Exception as e:
            logger.warning("health_check_redis_failed", error=str(e))
    else:
        # No Redis URL configured - mark as N/A (not an error)
        redis_ok = None

    # Check X bot status
    x_bot_ok = True
    x_bot_running = False
    learning_worker_running = False
    if is_x_bot_enabled():
        ingestion_loop = get_ingestion_loop()
        timeline_loop = get_timeline_loop()
        learning_worker = get_learning_worker()
        x_bot_running = (
            ingestion_loop is not None
            and timeline_loop is not None
            and ingestion_loop.get_stats().get("running", False)
            and timeline_loop.get_stats().get("running", False)
        )
        learning_worker_running = (
            learning_worker is not None
            and learning_worker.get_stats().get("running", False)
        )
        x_bot_ok = x_bot_running

    return {
        "ready": db_ok,
        "checks": {
            "database": db_ok,
            "redis": redis_ok,
            "llm": True,  # TODO: Add real check
            "x_bot": x_bot_ok if is_x_bot_enabled() else None,
        },
        "x_bot_enabled": is_x_bot_enabled(),
        "x_bot_running": x_bot_running,
        "learning_worker_running": learning_worker_running,
    }


@app.get("/health/live")
async def live():
    """Liveness check."""
    return {"live": True}


# ===========================================
# Session Endpoint
# ===========================================


@app.post("/api/session")
async def init_session(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """
    Initialize or validate a session.
    Creates anonymous user if no session exists.
    """
    session = await create_session(request, response, db)
    return {
        "user_id": str(session.user_id),
        "session_id": session.session_id,
        "is_new": session.is_new,
    }


# ===========================================
# API Info
# ===========================================


@app.get("/api/info")
async def info():
    """Get API information."""
    return {
        "name": "Jeffrey AIstein",
        "version": "0.1.0",
        "phase": 1,
        "description": "AGI-style agent with memory and persona",
    }


# ===========================================
# Conversations CRUD (Phase 1)
# ===========================================


@app.post("/api/conversations", response_model=ConversationResponse)
async def create_conversation(
    request: Request,
    response: Response,
    body: CreateConversationRequest = CreateConversationRequest(),
    db: AsyncSession = Depends(get_db),
):
    """Create a new conversation."""
    # Get or create session/user
    session = await create_session(request, response, db)

    # Create conversation
    conversation = Conversation(
        id=uuid.uuid4(),
        user_id=session.user_id,
        title=body.title,
    )
    db.add(conversation)

    # Log event
    event = Event(
        id=uuid.uuid4(),
        type="conversation_created",
        source="web",
        user_id=session.user_id,
        payload={"conversation_id": str(conversation.id), "title": body.title},
    )
    db.add(event)

    await db.commit()
    await db.refresh(conversation)

    return ConversationResponse(
        id=str(conversation.id),
        user_id=str(conversation.user_id),
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=0,
    )


@app.get("/api/conversations", response_model=ConversationListResponse)
async def list_conversations(
    request: Request,
    response: Response,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List user's conversations."""
    # Get or create session/user
    session = await create_session(request, response, db)

    # Count total
    count_result = await db.execute(
        select(func.count(Conversation.id)).where(Conversation.user_id == session.user_id)
    )
    total = count_result.scalar()

    # Get conversations with message count
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == session.user_id)
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    conversations = result.scalars().all()

    # Get message counts for each conversation
    conversation_responses = []
    for conv in conversations:
        msg_count_result = await db.execute(
            select(func.count(Message.id)).where(Message.conversation_id == conv.id)
        )
        msg_count = msg_count_result.scalar()

        conversation_responses.append(
            ConversationResponse(
                id=str(conv.id),
                user_id=str(conv.user_id),
                title=conv.title,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                message_count=msg_count,
            )
        )

    return ConversationListResponse(
        conversations=conversation_responses,
        total=total,
        has_more=offset + len(conversations) < total,
    )


@app.get("/api/conversations/{conversation_id}", response_model=ConversationWithMessagesResponse)
async def get_conversation(
    conversation_id: str,
    request: Request,
    response: Response,
    messages_limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Get conversation with messages."""
    # Get or create session/user
    session = await create_session(request, response, db)

    # Parse UUID
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID format")

    # Get conversation
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conv_uuid)
        .where(Conversation.user_id == session.user_id)
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get messages (most recent first, then reverse for display order)
    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv_uuid)
        .order_by(Message.created_at.desc())
        .limit(messages_limit + 1)  # Get one extra to check has_more
    )
    messages = list(msg_result.scalars().all())

    has_more = len(messages) > messages_limit
    if has_more:
        messages = messages[:messages_limit]

    # Reverse to get chronological order
    messages.reverse()

    message_responses = [
        MessageResponse(
            id=str(msg.id),
            role=msg.role,
            content=msg.content,
            created_at=msg.created_at,
            metadata=msg.metadata_ or {},
        )
        for msg in messages
    ]

    return ConversationWithMessagesResponse(
        id=str(conversation.id),
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=message_responses,
        has_more_messages=has_more,
    )


# ===========================================
# SSE Chat Endpoint (Phase 2 - WebSocket Fallback)
# ===========================================


class ChatRequest(BaseModel):
    content: str
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    user_message_id: str
    assistant_message_id: str
    conversation_id: str
    content: str


async def sse_chat_generator(
    user: User,
    content: str,
    conversation_id: Optional[str],
    db: AsyncSession,
):
    """
    Generator for SSE chat responses.
    Yields Server-Sent Events formatted strings.
    """
    import asyncio
    import json

    # Helper to format SSE
    def sse_event(event_type: str, data: dict) -> str:
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

    conversation = None

    # Validate or create conversation
    if conversation_id:
        try:
            conv_uuid = uuid.UUID(conversation_id)
            result = await db.execute(
                select(Conversation)
                .where(Conversation.id == conv_uuid)
                .where(Conversation.user_id == user.id)
            )
            conversation = result.scalar_one_or_none()

            if not conversation:
                yield sse_event("error", {
                    "code": "NOT_FOUND",
                    "message": "Conversation not found or access denied.",
                })
                return
        except ValueError:
            yield sse_event("error", {
                "code": "INVALID_ID",
                "message": "Invalid conversation ID format.",
            })
            return
    else:
        # Auto-create conversation
        conversation = Conversation(
            id=uuid.uuid4(),
            user_id=user.id,
            title=content[:50] + ("..." if len(content) > 50 else ""),
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)

        yield sse_event("conversation_created", {
            "conversation_id": str(conversation.id),
        })

    # Generate message IDs
    user_message_id = uuid.uuid4()
    assistant_message_id = uuid.uuid4()

    # Save user message
    user_message = Message(
        id=user_message_id,
        conversation_id=conversation.id,
        role="user",
        content=content,
        metadata_={"source": "sse"},
    )
    db.add(user_message)

    # Log event
    user_event = Event(
        id=uuid.uuid4(),
        type="message_received",
        source="web",
        user_id=user.id,
        payload={
            "conversation_id": str(conversation.id),
            "message_id": str(user_message_id),
            "content": content,
        },
    )
    db.add(user_event)

    # Update conversation timestamp
    conversation.updated_at = datetime.utcnow()
    await db.commit()

    # Acknowledge user message
    yield sse_event("message_saved", {
        "message_id": str(user_message_id),
        "role": "user",
    })

    # Start assistant response
    yield sse_event("message_start", {
        "message_id": str(assistant_message_id),
        "role": "assistant",
    })

    # Build conversation history (just the current message for SSE single-shot)
    chat_messages = [{"role": "user", "content": content}]

    # Create chat context
    chat_context = ChatContext(
        user_id=str(user.id),
        conversation_id=str(conversation.id),
        channel="web",
    )

    # Stream response from LLM
    chat_service = ChatService(channel="web")
    response = ""
    async for chunk in chat_service.stream(chat_messages, context=chat_context):
        response += chunk
        yield sse_event("content_delta", {
            "message_id": str(assistant_message_id),
            "delta": chunk,
        })

    # Save assistant message
    llm_provider = get_llm_provider()
    assistant_message = Message(
        id=assistant_message_id,
        conversation_id=conversation.id,
        role="assistant",
        content=response,
        metadata_={
            "source": "sse",
            "model": llm_provider.get_model_name(),
            "provider": "anthropic" if llm_provider.is_available else "mock",
        },
    )
    db.add(assistant_message)

    # Log event
    assistant_event = Event(
        id=uuid.uuid4(),
        type="message_sent",
        source="web",
        user_id=user.id,
        payload={
            "conversation_id": str(conversation.id),
            "message_id": str(assistant_message_id),
            "content": response,
            "in_reply_to": str(user_message_id),
        },
    )
    db.add(assistant_event)

    await db.commit()

    # Send completion
    yield sse_event("message_end", {
        "message_id": str(assistant_message_id),
        "content": response,
        "conversation_id": str(conversation.id),
    })


@app.post("/api/chat")
async def chat_sse(
    request: Request,
    response: Response,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    SSE chat endpoint - fallback for clients that can't use WebSocket.
    Returns Server-Sent Events stream.
    """
    # Validate content
    content = body.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Message content cannot be empty")

    # Get or create session/user
    session = await create_session(request, response, db)

    return StreamingResponse(
        sse_chat_generator(session.user, content, body.conversation_id, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


# ===========================================
# Token Metrics (Phase 5 placeholder)
# ===========================================


@app.get("/api/token/metrics")
async def get_token_metrics():
    """
    Get current token metrics.

    State values:
    - "indexing": Token data is being indexed (no live data yet)
    - "live": Live data available from on-chain source
    """
    # TODO: Integrate with Solana RPC or DEX API for live data
    # For now, return indexing state until data source is connected
    return {
        "state": "indexing",  # "indexing" | "live"
        "market_cap": 0,
        "market_cap_formatted": "$0",
        "holders": 0,
        "volume_24h": 0,
        "volume_24h_formatted": "$0",
        "price": 0,
        "meter_max": 1000000,
        "meter_fill": 0,
        "is_ath": False,
        "updated_at": None,
    }


# ===========================================
# Agent Stats (Public)
# ===========================================


@app.get("/api/stats/agent")
async def get_agent_stats(db: AsyncSession = Depends(get_db)):
    """
    Get agent statistics from the database.

    Returns aggregated counts (no private content exposed).
    """
    from datetime import datetime

    # Count total messages by role
    user_count_result = await db.execute(
        select(func.count(Message.id)).where(Message.role == "user")
    )
    user_messages = user_count_result.scalar() or 0

    assistant_count_result = await db.execute(
        select(func.count(Message.id)).where(Message.role == "assistant")
    )
    assistant_messages = assistant_count_result.scalar() or 0

    # Count conversations
    conv_count_result = await db.execute(
        select(func.count(Conversation.id))
    )
    total_conversations = conv_count_result.scalar() or 0

    # Get last message timestamp
    last_msg_result = await db.execute(
        select(Message.created_at)
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    last_msg = last_msg_result.scalar()

    # Calculate a simple "learning score" based on activity
    # Scale: 0-100, based on total interactions
    total_interactions = user_messages + assistant_messages
    learning_score = min(100, int((total_interactions / 1000) * 100)) if total_interactions > 0 else 0

    return {
        "state": "live",
        "messages_processed": user_messages,
        "messages_replied": assistant_messages,
        "total_conversations": total_conversations,
        "channel_breakdown": {"web": total_conversations, "x": 0},  # All web for now
        "learning_score": learning_score,
        "updated_at": last_msg.isoformat() if last_msg else None,
    }


# ===========================================
# Public Conversation Archive
# ===========================================


@app.get("/api/archive/conversations")
async def public_list_conversations(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    """
    Public endpoint to list conversations for the archive.
    Returns conversations sorted by most recent activity (newest first).
    """
    offset = (page - 1) * page_size

    # Subquery for message counts and last active time
    msg_stats = (
        select(
            Message.conversation_id,
            func.count(Message.id).label("message_count"),
            func.max(Message.created_at).label("last_active_at"),
        )
        .group_by(Message.conversation_id)
        .subquery()
    )

    # Get the first user message for preview
    first_msg = (
        select(
            Message.conversation_id,
            Message.content,
            func.row_number().over(
                partition_by=Message.conversation_id,
                order_by=Message.created_at.asc()
            ).label("rn")
        )
        .where(Message.role == "user")
        .subquery()
    )

    first_msg_filtered = (
        select(
            first_msg.c.conversation_id,
            first_msg.c.content.label("first_message"),
        )
        .where(first_msg.c.rn == 1)
        .subquery()
    )

    # Main query - only show conversations with at least 2 messages (user + assistant)
    base_query = (
        select(
            Conversation.id,
            Conversation.title,
            Conversation.created_at,
            func.coalesce(msg_stats.c.message_count, 0).label("message_count"),
            func.coalesce(msg_stats.c.last_active_at, Conversation.created_at).label("last_active_at"),
            first_msg_filtered.c.first_message,
        )
        .outerjoin(msg_stats, Conversation.id == msg_stats.c.conversation_id)
        .outerjoin(first_msg_filtered, Conversation.id == first_msg_filtered.c.conversation_id)
        .where(func.coalesce(msg_stats.c.message_count, 0) >= 2)  # At least user + assistant
    )

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total_count = total_result.scalar() or 0

    # Apply ordering (newest first) and pagination
    query = (
        base_query
        .order_by(func.coalesce(msg_stats.c.last_active_at, Conversation.created_at).desc())
        .offset(offset)
        .limit(page_size)
    )

    result = await db.execute(query)
    rows = result.all()

    # Format response
    items = []
    for row in rows:
        # Create preview from first message (truncate to 120 chars)
        preview = ""
        if row.first_message:
            preview = row.first_message[:120]
            if len(row.first_message) > 120:
                preview += "..."

        # Generate title from first message if no title
        title = row.title
        if not title and row.first_message:
            title = row.first_message[:50]
            if len(row.first_message) > 50:
                title += "..."

        items.append({
            "id": str(row.id),
            "title": title or "Conversation",
            "preview": preview,
            "message_count": row.message_count,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "last_active_at": row.last_active_at.isoformat() if row.last_active_at else None,
        })

    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total_count": total_count,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
    }


@app.get("/api/archive/conversations/{conversation_id}")
async def public_get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Public endpoint to get a single conversation with all messages.
    """
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")

    # Get conversation
    conv_result = await db.execute(
        select(Conversation).where(Conversation.id == conv_uuid)
    )
    conversation = conv_result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get all messages in chronological order
    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv_uuid)
        .order_by(Message.created_at.asc())
    )
    messages = msg_result.scalars().all()

    # Format messages
    items = []
    for msg in messages:
        items.append({
            "id": str(msg.id),
            "role": msg.role,
            "content": msg.content,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        })

    # Generate title from first user message if no title
    title = conversation.title
    if not title and items:
        first_user = next((m for m in items if m["role"] == "user"), None)
        if first_user:
            title = first_user["content"][:50]
            if len(first_user["content"]) > 50:
                title += "..."

    return {
        "id": str(conversation.id),
        "title": title or "Conversation",
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        "messages": items,
        "message_count": len(items),
    }


# ===========================================
# Text-to-Speech
# ===========================================


class TTSRequest(BaseModel):
    """TTS request body."""
    text: str


# Simple in-memory rate limiting for TTS
_tts_request_times: dict[str, list[float]] = {}


def _check_tts_rate_limit(client_ip: str) -> bool:
    """Check if client is within rate limit. Returns True if allowed."""
    import time
    now = time.time()
    window = 60.0  # 1 minute window

    if client_ip not in _tts_request_times:
        _tts_request_times[client_ip] = []

    # Clean old entries
    _tts_request_times[client_ip] = [
        t for t in _tts_request_times[client_ip]
        if now - t < window
    ]

    # Check limit
    if len(_tts_request_times[client_ip]) >= settings.tts_rate_limit_per_minute:
        return False

    # Record this request
    _tts_request_times[client_ip].append(now)
    return True


@app.post("/api/tts")
async def text_to_speech(request: Request, body: TTSRequest):
    """
    Convert text to speech using ElevenLabs.

    Returns audio/mpeg stream.

    Rate limited to prevent abuse.
    """
    from services.tts import get_tts_client, is_tts_configured, TTSError

    # Check if TTS is configured
    if not is_tts_configured():
        raise HTTPException(status_code=503, detail="TTS not configured")

    # Get client IP for rate limiting
    client_ip = request.client.host if request.client else "unknown"

    # Check rate limit
    if not _check_tts_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limited. Max {settings.tts_rate_limit_per_minute} requests per minute."
        )

    # Validate text
    if not body.text or not body.text.strip():
        raise HTTPException(status_code=400, detail="Text is required")

    if len(body.text) > settings.tts_max_text_length:
        raise HTTPException(
            status_code=400,
            detail=f"Text too long. Max {settings.tts_max_text_length} characters."
        )

    try:
        tts_client = get_tts_client()
        audio_bytes = await tts_client.synthesize(body.text)

        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "inline; filename=speech.mp3",
                "Cache-Control": "no-cache",
            },
        )

    except TTSError as e:
        logger.error("tts_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("tts_unexpected_error", error=str(e))
        raise HTTPException(status_code=500, detail="TTS generation failed")


@app.get("/api/tts/status")
async def tts_status():
    """Check TTS configuration status."""
    from services.tts import is_tts_configured

    return {
        "configured": is_tts_configured(),
        "enabled": settings.enable_tts,
        "provider": settings.tts_provider,
        "voice_id_set": bool(settings.elevenlabs_voice_id),
        "api_key_set": bool(settings.elevenlabs_api_key),
    }


# ===========================================
# WebSocket Endpoints
# ===========================================


async def get_ws_session(websocket: WebSocket, db: AsyncSession) -> tuple[User | None, str | None]:
    """
    Get user from WebSocket cookies.
    Returns (user, error_message) tuple.
    """
    from auth.session import get_user_by_session, SESSION_COOKIE_NAME

    session_id = websocket.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        return None, "No session found. Please initialize a session first."

    user = await get_user_by_session(db, session_id)
    if not user:
        return None, "Invalid session. Please refresh the page."

    return user, None


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for chat with message persistence."""
    await websocket.accept()

    conversation_id_str = websocket.query_params.get("conversation_id")

    # Get database session
    async with async_session_maker() as db:
        # Authenticate user via cookies
        user, error = await get_ws_session(websocket, db)
        if not user:
            await websocket.send_json({
                "type": "error",
                "code": "AUTH_ERROR",
                "message": error,
            })
            await websocket.close(code=4001)
            return

        # Validate or create conversation
        conversation = None
        if conversation_id_str:
            try:
                conv_uuid = uuid.UUID(conversation_id_str)
                result = await db.execute(
                    select(Conversation)
                    .where(Conversation.id == conv_uuid)
                    .where(Conversation.user_id == user.id)
                )
                conversation = result.scalar_one_or_none()

                if not conversation:
                    await websocket.send_json({
                        "type": "error",
                        "code": "NOT_FOUND",
                        "message": "Conversation not found or access denied.",
                    })
                    await websocket.close(code=4004)
                    return
            except ValueError:
                await websocket.send_json({
                    "type": "error",
                    "code": "INVALID_ID",
                    "message": "Invalid conversation ID format.",
                })
                await websocket.close(code=4000)
                return
        else:
            # Auto-create conversation if none specified
            conversation = Conversation(
                id=uuid.uuid4(),
                user_id=user.id,
                title=None,  # Will be set from first message
            )
            db.add(conversation)
            await db.commit()
            await db.refresh(conversation)

            # Notify client of new conversation
            await websocket.send_json({
                "type": "conversation_created",
                "conversation_id": str(conversation.id),
            })

        # Send ready signal
        await websocket.send_json({
            "type": "ready",
            "conversation_id": str(conversation.id),
            "user_id": str(user.id),
        })

        try:
            while True:
                data = await websocket.receive_json()

                if data.get("type") == "message":
                    content = data.get("content", "").strip()

                    if not content:
                        await websocket.send_json({
                            "type": "error",
                            "code": "EMPTY_MESSAGE",
                            "message": "Message content cannot be empty.",
                        })
                        continue

                    # Generate message IDs
                    user_message_id = uuid.uuid4()
                    assistant_message_id = uuid.uuid4()

                    # Save user message
                    user_message = Message(
                        id=user_message_id,
                        conversation_id=conversation.id,
                        role="user",
                        content=content,
                        metadata_={"source": "websocket"},
                    )
                    db.add(user_message)

                    # Log event for memory system
                    user_event = Event(
                        id=uuid.uuid4(),
                        type="message_received",
                        source="web",
                        user_id=user.id,
                        payload={
                            "conversation_id": str(conversation.id),
                            "message_id": str(user_message_id),
                            "content": content,
                        },
                    )
                    db.add(user_event)

                    # Update conversation title if not set (use first message)
                    if not conversation.title:
                        conversation.title = content[:50] + ("..." if len(content) > 50 else "")

                    # Update conversation timestamp
                    conversation.updated_at = datetime.utcnow()

                    await db.commit()

                    # Acknowledge user message saved
                    await websocket.send_json({
                        "type": "message_saved",
                        "message_id": str(user_message_id),
                        "role": "user",
                    })

                    # Send assistant response start
                    await websocket.send_json({
                        "type": "message_start",
                        "message_id": str(assistant_message_id),
                        "role": "assistant",
                    })

                    # Build conversation history for LLM
                    msg_result = await db.execute(
                        select(Message)
                        .where(Message.conversation_id == conversation.id)
                        .order_by(Message.created_at)
                        .limit(20)  # Limit context window
                    )
                    history_messages = list(msg_result.scalars().all())

                    # Convert to chat format
                    chat_messages = [
                        {"role": msg.role, "content": msg.content}
                        for msg in history_messages
                    ]
                    # Add current message if not already included
                    if not chat_messages or chat_messages[-1]["content"] != content:
                        chat_messages.append({"role": "user", "content": content})

                    # Create chat context
                    chat_context = ChatContext(
                        user_id=str(user.id),
                        conversation_id=str(conversation.id),
                        channel="web",
                    )

                    # Stream response from LLM
                    chat_service = ChatService(channel="web")
                    response = ""
                    async for chunk in chat_service.stream(chat_messages, context=chat_context):
                        response += chunk
                        await websocket.send_json({
                            "type": "content_delta",
                            "message_id": str(assistant_message_id),
                            "delta": chunk,
                        })

                    # Save assistant message
                    llm_provider = get_llm_provider()
                    assistant_message = Message(
                        id=assistant_message_id,
                        conversation_id=conversation.id,
                        role="assistant",
                        content=response,
                        metadata_={
                            "source": "websocket",
                            "model": llm_provider.get_model_name(),
                            "provider": "anthropic" if llm_provider.is_available else "mock",
                        },
                    )
                    db.add(assistant_message)

                    # Log event for memory system
                    assistant_event = Event(
                        id=uuid.uuid4(),
                        type="message_sent",
                        source="web",
                        user_id=user.id,
                        payload={
                            "conversation_id": str(conversation.id),
                            "message_id": str(assistant_message_id),
                            "content": response,
                            "in_reply_to": str(user_message_id),
                        },
                    )
                    db.add(assistant_event)

                    await db.commit()

                    # Send completion
                    await websocket.send_json({
                        "type": "message_end",
                        "message_id": str(assistant_message_id),
                        "content": response,
                    })

                elif data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})

        except WebSocketDisconnect:
            print(f"WebSocket disconnected: user={user.id}, conversation={conversation.id}")


@app.websocket("/ws/token")
async def websocket_token(websocket: WebSocket):
    """WebSocket endpoint for token data updates."""
    await websocket.accept()

    try:
        await websocket.send_json({
            "type": "token_update",
            "data": {
                "market_cap": 0,
                "meter_max": 1000000,
                "meter_fill": 0,
            },
        })

        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass


@app.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    """WebSocket endpoint for agent metrics updates."""
    await websocket.accept()

    try:
        await websocket.send_json({
            "type": "metrics_update",
            "data": {
                "messages_processed": 0,
                "learning_score": 0,
            },
        })

        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass


# ===========================================
# Admin Endpoints
# ===========================================


@app.get("/api/admin/memory/user/{user_id}")
async def admin_get_user_memories(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Get all memories for a user (admin only)."""
    await verify_admin_key(request)
    # TODO: Implement in Phase 4
    return JSONResponse(
        status_code=501,
        content={"error": {"code": "NOT_IMPLEMENTED", "message": "Coming in Phase 4"}},
    )


@app.get("/api/admin/retrieval/{message_id}")
async def admin_get_retrieval_trace(
    message_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Get retrieval trace for a message (admin only)."""
    await verify_admin_key(request)
    # TODO: Implement in Phase 4
    return JSONResponse(
        status_code=501,
        content={"error": {"code": "NOT_IMPLEMENTED", "message": "Coming in Phase 4"}},
    )


@app.get("/api/admin/social/status")
async def admin_get_social_status(request: Request):
    """Get X bot status and scheduler stats (admin only)."""
    await verify_admin_key(request)

    ingestion_loop = get_ingestion_loop()
    timeline_loop = get_timeline_loop()
    learning_worker = get_learning_worker()
    self_style_worker = get_self_style_worker()

    # Get runtime settings (DB overrides env)
    safe_mode = await get_runtime_setting(SETTING_SAFE_MODE, "SAFE_MODE", "false")
    approval_required = await get_runtime_setting(SETTING_APPROVAL_REQUIRED, "APPROVAL_REQUIRED", "true")

    return {
        "enabled": is_x_bot_enabled(),
        "ingestion": ingestion_loop.get_stats() if ingestion_loop else None,
        "timeline": timeline_loop.get_stats() if timeline_loop else None,
        "learning": learning_worker.get_stats() if learning_worker else None,
        "self_style": self_style_worker.get_stats() if self_style_worker else None,
        "safe_mode": safe_mode,
        "approval_required": approval_required,
    }


class DraftResponse(BaseModel):
    id: str
    text: str
    post_type: str
    reply_to_id: Optional[str]
    status: str
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class DraftListResponse(BaseModel):
    drafts: List[DraftResponse]
    total: int


class RejectDraftRequest(BaseModel):
    reason: Optional[str] = None


@app.get("/api/admin/social/drafts", response_model=DraftListResponse)
async def admin_get_drafts(request: Request):
    """Get pending social media drafts (admin only)."""
    await verify_admin_key(request)

    draft_repo = get_draft_repository()
    drafts = await draft_repo.list_pending()

    return DraftListResponse(
        drafts=[
            DraftResponse(
                id=d.id,
                text=d.text,
                post_type=d.post_type.value if hasattr(d.post_type, 'value') else str(d.post_type),
                reply_to_id=d.reply_to_id,
                status=d.status.value if hasattr(d.status, 'value') else str(d.status),
                created_at=d.created_at,
            )
            for d in drafts
        ],
        total=len(drafts),
    )


@app.post("/api/admin/social/drafts/{draft_id}/approve")
async def admin_approve_draft(draft_id: str, request: Request):
    """Approve a draft and post it to X (admin only)."""
    await verify_admin_key(request)

    draft_repo = get_draft_repository()
    post_repo = get_post_repository()

    # Get the draft
    draft = await draft_repo.get(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    if draft.status != DraftStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Draft is not pending (status: {draft.status})")

    # Check safe mode (DB overrides env)
    if await get_runtime_setting(SETTING_SAFE_MODE, "SAFE_MODE", "false"):
        raise HTTPException(status_code=400, detail="Cannot post in SAFE_MODE")

    # Post to X
    try:
        x_provider = get_x_provider()
        tweet = await x_provider.post_tweet(
            text=draft.text,
            reply_to=draft.reply_to_id,
        )

        # Update draft status
        await draft_repo.approve(draft_id)

        # Record in post log
        post = PostEntry(
            id="",
            tweet_id=tweet.id,
            text=draft.text,
            post_type=draft.post_type,
            reply_to_id=draft.reply_to_id,
            status=PostStatus.POSTED,
            posted_at=datetime.utcnow(),
        )
        await post_repo.save(post)

        logger.info(
            "draft_approved_and_posted",
            draft_id=draft_id,
            tweet_id=tweet.id,
        )

        return {
            "success": True,
            "draft_id": draft_id,
            "tweet_id": tweet.id,
            "tweet_url": f"https://x.com/i/status/{tweet.id}",
        }

    except Exception as e:
        logger.exception("draft_post_failed", draft_id=draft_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to post: {str(e)}")


@app.post("/api/admin/social/drafts/{draft_id}/reject")
async def admin_reject_draft(draft_id: str, request: Request, body: RejectDraftRequest = RejectDraftRequest()):
    """Reject a draft (admin only)."""
    await verify_admin_key(request)

    draft_repo = get_draft_repository()

    # Get the draft
    draft = await draft_repo.get(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    if draft.status != DraftStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Draft is not pending (status: {draft.status})")

    # Reject draft
    await draft_repo.reject(draft_id, body.reason)

    logger.info(
        "draft_rejected",
        draft_id=draft_id,
        reason=body.reason,
    )

    return {
        "success": True,
        "draft_id": draft_id,
        "status": "rejected",
        "reason": body.reason,
    }


@app.get("/api/admin/social/settings")
async def admin_get_social_settings(request: Request):
    """Get X bot settings (admin only)."""
    await verify_admin_key(request)

    # Get runtime settings (DB overrides env)
    safe_mode = await get_runtime_setting(SETTING_SAFE_MODE, "SAFE_MODE", "false")
    approval_required = await get_runtime_setting(SETTING_APPROVAL_REQUIRED, "APPROVAL_REQUIRED", "true")

    return {
        "safe_mode": safe_mode,
        "approval_required": approval_required,
        "x_bot_enabled": is_x_bot_enabled(),
        "poll_interval_seconds": int(os.getenv("X_POLL_INTERVAL_SECONDS", "45")),
        "timeline_interval_seconds": int(os.getenv("X_TIMELINE_POST_INTERVAL_SECONDS", "10800")),
        "hourly_post_limit": int(os.getenv("X_HOURLY_POST_LIMIT", "5")),
        "daily_post_limit": int(os.getenv("X_DAILY_POST_LIMIT", "20")),
        "max_replies_per_thread": int(os.getenv("X_MAX_REPLIES_PER_THREAD", "5")),
        "max_replies_per_user_per_day": int(os.getenv("X_MAX_REPLIES_PER_USER_PER_DAY", "10")),
        "quality_threshold": int(os.getenv("X_QUALITY_THRESHOLD", "30")),
    }


@app.get("/api/admin/kill_switch")
async def admin_get_kill_switch(request: Request):
    """Get kill switch status (admin only). Kill switch = SAFE_MODE."""
    await verify_admin_key(request)
    safe_mode = await get_runtime_setting(SETTING_SAFE_MODE, "SAFE_MODE", "false")
    return {
        "enabled": safe_mode,
        "note": "Use PATCH /api/admin/social/settings to toggle SAFE_MODE at runtime without restart",
    }


@app.post("/api/admin/kill_switch")
async def admin_toggle_kill_switch(request: Request):
    """
    Toggle kill switch (admin only).

    Note: Use PATCH /api/admin/social/settings to change SAFE_MODE at runtime.
    """
    await verify_admin_key(request)

    current = await get_runtime_setting(SETTING_SAFE_MODE, "SAFE_MODE", "false")

    return {
        "current_state": current,
        "note": "Use PATCH /api/admin/social/settings to toggle SAFE_MODE at runtime without restart",
        "example": {
            "method": "PATCH",
            "url": "/api/admin/social/settings",
            "body": {"safe_mode": False, "approval_required": True},
        },
    }


class UpdateSettingsRequest(BaseModel):
    """Request body for updating social bot settings."""
    safe_mode: Optional[bool] = None
    approval_required: Optional[bool] = None


@app.patch("/api/admin/social/settings")
async def admin_update_social_settings(request: Request, body: UpdateSettingsRequest):
    """
    Update X bot settings at runtime (admin only).

    This stores settings in the database, which take precedence over environment variables.
    Changes take effect immediately without restart.

    Settings:
    - safe_mode: If true, prevents all posting (read-only mode)
    - approval_required: If true, drafts require admin approval before posting
    """
    await verify_admin_key(request)

    from services.social.storage import (
        get_settings_repository,
        SETTING_SAFE_MODE,
        SETTING_APPROVAL_REQUIRED,
    )

    settings_repo = get_settings_repository()
    updated = {}

    if body.safe_mode is not None:
        await settings_repo.set(SETTING_SAFE_MODE, "true" if body.safe_mode else "false")
        updated["safe_mode"] = body.safe_mode

    if body.approval_required is not None:
        await settings_repo.set(SETTING_APPROVAL_REQUIRED, "true" if body.approval_required else "false")
        updated["approval_required"] = body.approval_required

    # Get current effective values
    safe_mode_db = await settings_repo.get(SETTING_SAFE_MODE)
    approval_db = await settings_repo.get(SETTING_APPROVAL_REQUIRED)

    return {
        "updated": updated,
        "current": {
            "safe_mode": safe_mode_db == "true" if safe_mode_db else os.getenv("SAFE_MODE", "").lower() in ("true", "1", "yes"),
            "approval_required": approval_db == "true" if approval_db else os.getenv("APPROVAL_REQUIRED", "true").lower() in ("true", "1", "yes"),
        },
        "note": "Settings stored in database take precedence over environment variables",
    }


@app.get("/api/admin/persona/status")
async def admin_get_persona_status(request: Request):
    """
    Get persona system status (admin only).

    Returns status of style guide, KOL profiles, blend settings, and brand rules enforcement.
    """
    await verify_admin_key(request)

    # Get style rewriter status
    style_rewriter = get_style_rewriter()
    style_guide_loaded = style_rewriter.is_available()
    style_guide_generated_at = style_rewriter.get_generated_at() if style_guide_loaded else None

    # Get KOL profiles status
    kol_loader = get_kol_loader()
    kol_profiles_loaded_count = kol_loader.profile_count
    kol_profiles_generated_at = kol_loader.get_generated_at() if kol_loader.is_available() else None

    # Get blend status
    blend_status = get_blender_status()

    return {
        "style_guide_loaded": style_guide_loaded,
        "style_guide_generated_at": style_guide_generated_at,
        "kol_profiles_loaded_count": kol_profiles_loaded_count,
        "kol_profiles_generated_at": kol_profiles_generated_at,
        "brand_rules_enforced": True,
        "no_emojis": True,
        "no_hashtags": True,
        # Blend settings
        "snark_level": blend_status.get("snark_level", 2),
        "epstein_persona_blend": blend_status.get("epstein_persona_blend", False),
        "blend_weights": blend_status.get("weights", {}),
        "compiled_at": blend_status.get("compiled_at"),
        "blend_components_loaded": blend_status.get("components_loaded", {}),
    }


@app.post("/api/admin/persona/rebuild")
async def admin_rebuild_persona(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Rebuild compiled persona from components (admin only).

    This regenerates:
    - services/persona/epstein_tone.json (from DB summaries)
    - services/persona/compiled_persona.json
    - services/persona/compiled_persona_prompt.md
    """
    await verify_admin_key(request)

    from services.corpus.epstein.tone_builder import build_and_save_tone, validate_tone_safety

    # Build tone from DB
    tone_json = await build_and_save_tone(db)

    # Validate tone safety
    is_safe, violations = validate_tone_safety(tone_json)
    if not is_safe:
        return JSONResponse(
            status_code=400,
            content={
                "error": "Tone validation failed",
                "violations": violations,
            }
        )

    # Build compiled persona
    compiled_json, compiled_prompt = build_and_save_persona()

    return {
        "success": True,
        "tone_generated": True,
        "tone_doc_count": tone_json.get("metadata", {}).get("source_document_count", 0),
        "persona_compiled": True,
        "compiled_at": compiled_json.get("generated_at"),
        "epstein_persona_blend": compiled_json.get("settings", {}).get("epstein_persona_blend", False),
        "snark_level": compiled_json.get("settings", {}).get("snark_level", 2),
    }


@app.patch("/api/admin/persona/settings")
async def admin_update_persona_settings(request: Request):
    """
    Update persona blend settings (admin only).

    Supports:
    - epstein_persona_blend: true/false (toggle casefile parody cadence)
    - snark_level: 0-5 (default 2)

    Note: EPSTEIN_MODE is always false (no retrieval).
    EPSTEIN_PERSONA_BLEND only affects tone/cadence, not content.
    """
    await verify_admin_key(request)

    body = await request.json()

    updated = {}

    # Update EPSTEIN_PERSONA_BLEND
    if "epstein_persona_blend" in body:
        new_value = str(body["epstein_persona_blend"]).lower() == "true"
        os.environ["EPSTEIN_PERSONA_BLEND"] = str(new_value).lower()
        updated["epstein_persona_blend"] = new_value

    # Update SNARK_LEVEL
    if "snark_level" in body:
        new_level = int(body["snark_level"])
        new_level = max(0, min(5, new_level))  # Clamp to 0-5
        os.environ["SNARK_LEVEL"] = str(new_level)
        updated["snark_level"] = new_level

    # Rebuild persona with new settings
    if updated:
        compiled_json, _ = build_and_save_persona()
        updated["compiled_at"] = compiled_json.get("generated_at")

    return {
        "success": True,
        "updated": updated,
        "note": "Settings updated in environment. Restart not required.",
    }


@app.get("/api/admin/learning/status")
async def admin_get_learning_status(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Get learning system persistence status (admin only).

    Returns counts of stored inbound/outbound tweets, drafts, and thread linkage status.
    """
    await verify_admin_key(request)

    from sqlalchemy import text

    # Query inbound tweets count
    inbound_result = await db.execute(text("SELECT COUNT(*) FROM x_inbox"))
    inbound_tweets_count = inbound_result.scalar() or 0

    # Query outbound posts count (only posted)
    outbound_result = await db.execute(
        text("SELECT COUNT(*) FROM x_posts WHERE status = 'posted'")
    )
    outbound_posts_count = outbound_result.scalar() or 0

    # Query drafts by status
    drafts_result = await db.execute(
        text("SELECT status, COUNT(*) as count FROM x_drafts GROUP BY status")
    )
    drafts_rows = drafts_result.fetchall()
    drafts_count = {
        "pending": 0,
        "approved": 0,
        "rejected": 0,
    }
    for row in drafts_rows:
        if row[0] in drafts_count:
            drafts_count[row[0]] = row[1]

    # Query last ingest timestamp
    last_ingest_result = await db.execute(
        text("SELECT MAX(received_at) FROM x_inbox")
    )
    last_ingest_at = last_ingest_result.scalar()

    # Query last post timestamp
    last_post_result = await db.execute(
        text("SELECT MAX(posted_at) FROM x_posts WHERE status = 'posted'")
    )
    last_post_at = last_post_result.scalar()

    # Check thread linkage - verify columns exist and have data
    # x_inbox stores thread info in tweet_data JSONB (conversation_id, reply_to_tweet_id)
    # x_posts has reply_to_id column for thread linkage
    thread_linkage_ok = True
    thread_linkage_details = {}

    try:
        # Check x_inbox has tweet_data with thread info
        inbox_thread_result = await db.execute(
            text("""
                SELECT COUNT(*) FROM x_inbox
                WHERE tweet_data->>'conversation_id' IS NOT NULL
                   OR tweet_data->>'reply_to_tweet_id' IS NOT NULL
            """)
        )
        inbox_thread_count = inbox_thread_result.scalar() or 0
        thread_linkage_details["inbound_with_thread_info"] = inbox_thread_count

        # Check x_posts has reply_to_id populated
        posts_reply_result = await db.execute(
            text("SELECT COUNT(*) FROM x_posts WHERE reply_to_id IS NOT NULL")
        )
        posts_reply_count = posts_reply_result.scalar() or 0
        thread_linkage_details["outbound_with_reply_to"] = posts_reply_count

        # Check x_threads table has data
        threads_result = await db.execute(text("SELECT COUNT(*) FROM x_threads"))
        threads_count = threads_result.scalar() or 0
        thread_linkage_details["threads_tracked"] = threads_count

    except Exception as e:
        thread_linkage_ok = False
        thread_linkage_details["error"] = str(e)

    # Query learning extraction stats
    learning_stats = {}
    try:
        # Extracted memories count
        memories_result = await db.execute(
            text("SELECT COUNT(*) FROM memories WHERE type LIKE 'x_%'")
        )
        learning_stats["extracted_memories_count"] = memories_result.scalar() or 0

        # Processed inbox count
        processed_inbox_result = await db.execute(
            text("SELECT COUNT(*) FROM x_inbox WHERE learning_processed = true")
        )
        learning_stats["processed_inbox_count"] = processed_inbox_result.scalar() or 0

        # Processed posts count
        processed_posts_result = await db.execute(
            text("SELECT COUNT(*) FROM x_posts WHERE learning_processed = true")
        )
        learning_stats["processed_posts_count"] = processed_posts_result.scalar() or 0

        # Last learning job timestamp
        last_learning_result = await db.execute(
            text("""
                SELECT GREATEST(
                    (SELECT MAX(learning_processed_at) FROM x_inbox),
                    (SELECT MAX(learning_processed_at) FROM x_posts)
                )
            """)
        )
        last_learning_at = last_learning_result.scalar()
        learning_stats["last_learning_job_at"] = last_learning_at.isoformat() if last_learning_at else None

    except Exception as e:
        learning_stats["error"] = str(e)
        learning_stats["extracted_memories_count"] = 0
        learning_stats["processed_inbox_count"] = 0
        learning_stats["processed_posts_count"] = 0
        learning_stats["last_learning_job_at"] = None

    # Get SelfStyleWorker status
    self_style_worker = get_self_style_worker()
    self_style_status = None
    if self_style_worker:
        worker_stats = self_style_worker.get_stats()
        self_style_status = {
            "enabled": worker_stats.get("enabled", False),
            "disabled_reason": worker_stats.get("disabled_reason"),
            "last_run_status": worker_stats.get("last_run_status"),
            "last_run_finished_at": worker_stats.get("last_run_finished_at"),
            "last_proposal_version_id": worker_stats.get("last_proposal_version_id"),
        }

    return {
        "inbound_tweets_count": inbound_tweets_count,
        "outbound_posts_count": outbound_posts_count,
        "drafts_count": drafts_count,
        "last_ingest_at": last_ingest_at.isoformat() if last_ingest_at else None,
        "last_post_at": last_post_at.isoformat() if last_post_at else None,
        "last_learning_job_at": learning_stats.get("last_learning_job_at"),
        "last_self_style_job_at": self_style_status.get("last_run_finished_at") if self_style_status else None,
        "last_self_style_status": self_style_status.get("last_run_status") if self_style_status else None,
        "thread_linkage_ok": thread_linkage_ok,
        "thread_linkage_details": thread_linkage_details,
        "learning": learning_stats,
        "self_style": self_style_status,
        "tables_used": [
            "x_inbox",
            "x_posts",
            "x_drafts",
            "x_threads",
            "x_reply_log",
            "memories",
            "style_guide_versions",
        ],
    }


@app.get("/api/admin/learning/recent")
async def admin_get_learning_recent(
    request: Request,
    db: AsyncSession = Depends(get_db),
    kind: Optional[str] = Query(default=None, description="Filter by kind: x_slang, x_narrative, x_risk_flag, x_engagement"),
    limit: int = Query(default=50, ge=1, le=200),
):
    """
    Get recent extracted learning memories (admin only).

    Returns the most recent memories extracted from X interactions.
    """
    await verify_admin_key(request)

    from sqlalchemy import text

    # Build query
    if kind and kind in ("x_slang", "x_narrative", "x_risk_flag", "x_engagement"):
        query = text("""
            SELECT id, type, content, confidence, source_tweet_ids, metadata, created_at
            FROM memories
            WHERE type = :kind
            ORDER BY created_at DESC
            LIMIT :limit
        """)
        params = {"kind": kind, "limit": limit}
    else:
        query = text("""
            SELECT id, type, content, confidence, source_tweet_ids, metadata, created_at
            FROM memories
            WHERE type LIKE 'x_%'
            ORDER BY created_at DESC
            LIMIT :limit
        """)
        params = {"limit": limit}

    result = await db.execute(query, params)
    rows = result.mappings().fetchall()

    memories = []
    for row in rows:
        memories.append({
            "id": str(row["id"]),
            "kind": row["type"],
            "content": row["content"],
            "confidence": row["confidence"],
            "source_tweet_ids": row["source_tweet_ids"] or [],
            "metadata": row["metadata"] or {},
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        })

    return {
        "memories": memories,
        "total": len(memories),
        "filter": kind,
    }


# =============================================================================
# Style Guide Version Management Endpoints
# =============================================================================


@app.get("/api/admin/persona/style/versions")
async def admin_list_style_versions(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    List all style guide versions (admin only).

    Returns all proposals ordered by generated_at descending.
    Does not include full JSON rules content.
    """
    await verify_admin_key(request)

    from sqlalchemy import text

    query = text("""
        SELECT
            version_id,
            generated_at,
            source,
            tweet_count,
            md_path,
            json_path,
            is_active,
            activated_at,
            deactivated_at,
            created_at
        FROM style_guide_versions
        ORDER BY generated_at DESC
    """)

    result = await db.execute(query)
    rows = result.mappings().fetchall()

    versions = []
    for row in rows:
        versions.append({
            "version_id": row["version_id"],
            "generated_at": row["generated_at"].isoformat() if row["generated_at"] else None,
            "source": row["source"],
            "tweet_count": row["tweet_count"],
            "md_path": row["md_path"],
            "json_path": row["json_path"],
            "is_active": row["is_active"],
            "activated_at": row["activated_at"].isoformat() if row["activated_at"] else None,
            "deactivated_at": row["deactivated_at"].isoformat() if row["deactivated_at"] else None,
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        })

    return {
        "versions": versions,
        "total": len(versions),
    }


class ActivateStyleVersionRequest(BaseModel):
    """Request body for activating a style guide version."""
    version_id: str


@app.post("/api/admin/persona/style/activate")
async def admin_activate_style_version(
    request: Request,
    body: ActivateStyleVersionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Activate a style guide version (admin only).

    - Validates version exists
    - Validates hard constraints (emojis_allowed=0, hashtags_allowed=0)
    - Deactivates current active version
    - Activates requested version
    - Reloads StyleRewriter in-process
    """
    await verify_admin_key(request)

    import json
    from pathlib import Path
    from sqlalchemy import text

    version_id = body.version_id

    # Check version exists
    check_query = text("""
        SELECT version_id, json_path, is_active
        FROM style_guide_versions
        WHERE version_id = :version_id
    """)
    result = await db.execute(check_query, {"version_id": version_id})
    row = result.mappings().fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Version {version_id} not found")

    if row["is_active"]:
        raise HTTPException(status_code=400, detail=f"Version {version_id} is already active")

    # Load and validate the JSON file
    json_path = row["json_path"]
    json_file = Path(json_path)
    if not json_file.is_absolute():
        # Relative path - resolve from api root
        json_file = Path(__file__).parent / json_path

    if not json_file.exists():
        raise HTTPException(
            status_code=400,
            detail=f"JSON file not found: {json_path}"
        )

    try:
        with open(json_file, "r", encoding="utf-8") as f:
            guide = json.load(f)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to load JSON: {str(e)}"
        )

    # Validate hard constraints
    is_valid, error = _validate_hard_constraints(guide)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail=f"Guide fails safety validation: {error}"
        )

    # Transaction: deactivate current, activate new
    now = datetime.utcnow()

    # Deactivate current active version (if any)
    deactivate_query = text("""
        UPDATE style_guide_versions
        SET is_active = false, deactivated_at = :now
        WHERE is_active = true
    """)
    await db.execute(deactivate_query, {"now": now})

    # Activate requested version
    activate_query = text("""
        UPDATE style_guide_versions
        SET is_active = true, activated_at = :now
        WHERE version_id = :version_id
    """)
    await db.execute(activate_query, {"version_id": version_id, "now": now})

    await db.commit()

    logger.info(
        "style_guide_version_activated",
        version_id=version_id,
        activated_at=now.isoformat(),
    )

    # Reload StyleRewriter in-process
    reload_success = await reload_style_rewriter_async()

    # Get updated status
    style_rewriter = get_style_rewriter()
    status = style_rewriter.get_status()

    return {
        "activated": True,
        "version_id": version_id,
        "activated_at": now.isoformat(),
        "reload_success": reload_success,
        "style_rewriter_status": status,
    }


class RollbackStyleVersionRequest(BaseModel):
    """Request body for rolling back style guide version."""
    version_id: Optional[str] = None
    previous: Optional[bool] = False


@app.post("/api/admin/persona/style/rollback")
async def admin_rollback_style_version(
    request: Request,
    body: RollbackStyleVersionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Rollback to a previous style guide version (admin only).

    - If previous=true, activates the most recently deactivated version
    - If version_id provided, activates that specific version
    - Reloads StyleRewriter in-process
    """
    await verify_admin_key(request)

    import json
    from pathlib import Path
    from sqlalchemy import text

    target_version_id = body.version_id

    # If previous=true, find most recently deactivated
    if body.previous and not target_version_id:
        query = text("""
            SELECT version_id
            FROM style_guide_versions
            WHERE is_active = false AND deactivated_at IS NOT NULL
            ORDER BY deactivated_at DESC
            LIMIT 1
        """)
        result = await db.execute(query)
        row = result.mappings().fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="No previously active version found to rollback to"
            )

        target_version_id = row["version_id"]

    if not target_version_id:
        raise HTTPException(
            status_code=400,
            detail="Must provide version_id or set previous=true"
        )

    # Check version exists
    check_query = text("""
        SELECT version_id, json_path, is_active
        FROM style_guide_versions
        WHERE version_id = :version_id
    """)
    result = await db.execute(check_query, {"version_id": target_version_id})
    row = result.mappings().fetchone()

    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"Version {target_version_id} not found"
        )

    if row["is_active"]:
        raise HTTPException(
            status_code=400,
            detail=f"Version {target_version_id} is already active"
        )

    # Validate the JSON file
    json_path = row["json_path"]
    json_file = Path(json_path)
    if not json_file.is_absolute():
        json_file = Path(__file__).parent / json_path

    if not json_file.exists():
        raise HTTPException(
            status_code=400,
            detail=f"JSON file not found: {json_path}"
        )

    try:
        with open(json_file, "r", encoding="utf-8") as f:
            guide = json.load(f)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to load JSON: {str(e)}"
        )

    is_valid, error = _validate_hard_constraints(guide)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail=f"Guide fails safety validation: {error}"
        )

    # Transaction: deactivate current, activate target
    now = datetime.utcnow()

    deactivate_query = text("""
        UPDATE style_guide_versions
        SET is_active = false, deactivated_at = :now
        WHERE is_active = true
    """)
    await db.execute(deactivate_query, {"now": now})

    activate_query = text("""
        UPDATE style_guide_versions
        SET is_active = true, activated_at = :now
        WHERE version_id = :version_id
    """)
    await db.execute(activate_query, {"version_id": target_version_id, "now": now})

    await db.commit()

    logger.info(
        "style_guide_version_rollback",
        version_id=target_version_id,
        activated_at=now.isoformat(),
    )

    # Reload StyleRewriter
    reload_success = await reload_style_rewriter_async()

    style_rewriter = get_style_rewriter()
    status = style_rewriter.get_status()

    return {
        "rolled_back": True,
        "version_id": target_version_id,
        "activated_at": now.isoformat(),
        "reload_success": reload_success,
        "style_rewriter_status": status,
    }


@app.get("/api/admin/persona/style/status")
async def admin_get_style_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Get style guide status (admin only).

    Returns StyleRewriter status plus active version details.
    """
    await verify_admin_key(request)

    from sqlalchemy import text

    # Get StyleRewriter status
    style_rewriter = get_style_rewriter()
    rewriter_status = style_rewriter.get_status()

    # Get active version from DB (if any)
    query = text("""
        SELECT
            version_id,
            generated_at,
            source,
            tweet_count,
            md_path,
            json_path,
            activated_at
        FROM style_guide_versions
        WHERE is_active = true
        LIMIT 1
    """)
    result = await db.execute(query)
    row = result.mappings().fetchone()

    active_version = None
    if row:
        active_version = {
            "version_id": row["version_id"],
            "generated_at": row["generated_at"].isoformat() if row["generated_at"] else None,
            "source": row["source"],
            "tweet_count": row["tweet_count"],
            "md_path": row["md_path"],
            "json_path": row["json_path"],
            "activated_at": row["activated_at"].isoformat() if row["activated_at"] else None,
        }

    # Get most recent proposal from DB (regardless of active status)
    latest_query = text("""
        SELECT
            version_id,
            generated_at,
            source,
            tweet_count,
            is_active
        FROM style_guide_versions
        ORDER BY generated_at DESC
        LIMIT 1
    """)
    latest_result = await db.execute(latest_query)
    latest_row = latest_result.mappings().fetchone()

    last_proposal = None
    if latest_row:
        last_proposal = {
            "version_id": latest_row["version_id"],
            "generated_at": latest_row["generated_at"].isoformat() if latest_row["generated_at"] else None,
            "source": latest_row["source"],
            "tweet_count": latest_row["tweet_count"],
            "is_active": latest_row["is_active"],
        }

    # Get SelfStyleWorker stats (if available)
    self_style_worker = get_self_style_worker()
    self_style_worker_stats = None
    if self_style_worker:
        worker_stats = self_style_worker.get_stats()
        self_style_worker_stats = {
            "enabled": worker_stats.get("enabled", False),
            "disabled_reason": worker_stats.get("disabled_reason"),
            "last_run_status": worker_stats.get("last_run_status"),
            "last_run_started_at": worker_stats.get("last_run_started_at"),
            "last_run_finished_at": worker_stats.get("last_run_finished_at"),
            "last_error": worker_stats.get("last_error"),
            "last_proposal_version_id": worker_stats.get("last_proposal_version_id"),
            "total_proposals_generated": worker_stats.get("total_proposals_generated", 0),
            "total_proposals_skipped": worker_stats.get("total_proposals_skipped", 0),
            "leader_lock": worker_stats.get("leader_lock", {}),
        }

    # Derive last_proposal_error from worker stats if available
    last_proposal_error = None
    if self_style_worker_stats and self_style_worker_stats.get("last_error"):
        last_proposal_error = self_style_worker_stats["last_error"]

    return {
        "style_rewriter": rewriter_status,
        "active_version": active_version,
        "last_proposal": last_proposal,
        "last_proposal_error": last_proposal_error,
        "self_style_worker": self_style_worker_stats,
        "hard_rules_enforced": {
            "emojis_allowed": 0,
            "hashtags_allowed": 0,
        },
    }


@app.post("/api/admin/persona/style/generate")
async def admin_generate_style_proposal(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger style guide proposal generation (admin only).

    This endpoint triggers the proposal generation process WITHOUT activation.
    The generated proposal will have is_active=false and require explicit
    activation via the /activate endpoint.

    IMPORTANT: This does NOT auto-activate - admin approval required.
    """
    await verify_admin_key(request)

    self_style_worker = get_self_style_worker()
    if not self_style_worker:
        return JSONResponse(
            status_code=503,
            content={"error": "SelfStyleWorker not initialized"},
        )

    # Check if Redis is available (required for locking)
    redis_available = await self_style_worker._lock.is_available()
    if not redis_available:
        return JSONResponse(
            status_code=503,
            content={"error": "Redis unavailable - leader lock required"},
        )

    # Trigger proposal generation via _run_with_lock
    # This handles locking, generation, and DB insertion
    result = await self_style_worker._run_with_lock()

    # Check for errors
    if result.get("error"):
        return JSONResponse(
            status_code=500,
            content={
                "error": result.get("error"),
                "skip_reason": result.get("skip_reason"),
            },
        )

    if result.get("skipped"):
        return {
            "generated": False,
            "skipped": True,
            "skip_reason": result.get("skip_reason"),
            "lock_acquired": result.get("lock_acquired", False),
        }

    return {
        "generated": result.get("proposal_generated", False),
        "version_id": result.get("version_id"),
        "tweet_count": result.get("tweet_count"),
        "is_active": False,  # NEVER auto-activated
        "message": "Proposal generated - requires admin activation via /activate endpoint",
    }


# =============================================================================
# Epstein Corpus Admin Endpoints
# =============================================================================


@app.get("/api/admin/corpus/epstein/status")
async def admin_corpus_epstein_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Get Epstein corpus ingestion status (admin only).

    Returns document counts, last ingestion info, and EPSTEIN_MODE status.
    """
    await verify_admin_key(request)

    from services.corpus.epstein.ingest import get_corpus_status

    status = await get_corpus_status(db)

    # Get EPSTEIN_MODE setting
    epstein_mode = await get_runtime_setting("epstein_mode", "EPSTEIN_MODE", "false")

    return {
        **status,
        "epstein_mode": epstein_mode,
        "epstein_persona_blend": await get_runtime_setting("epstein_persona_blend", "EPSTEIN_PERSONA_BLEND", "false"),
    }


@app.get("/api/admin/corpus/epstein/samples")
async def admin_corpus_epstein_samples(
    request: Request,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """
    Get sample sanitized summaries for admin review (admin only).

    Returns only sanitized_summary and basic metadata.
    Never returns raw text or blocked content.
    """
    await verify_admin_key(request)

    if limit < 1 or limit > 100:
        limit = 20

    from services.corpus.epstein.ingest import get_corpus_samples

    samples = await get_corpus_samples(db, limit=limit)

    return {
        "samples": samples,
        "count": len(samples),
        "note": "Review these samples before enabling EPSTEIN_MODE",
    }


@app.post("/api/admin/corpus/epstein/enable")
async def admin_corpus_epstein_enable(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Enable EPSTEIN_MODE after admin review (admin only).

    This enables:
    - search_knowledge() with source="epstein"
    - Casefile tone blending in persona (if EPSTEIN_PERSONA_BLEND also enabled)

    WARNING: Only enable after reviewing samples via /samples endpoint.
    """
    await verify_admin_key(request)

    # Set EPSTEIN_MODE=true in runtime settings
    await set_runtime_setting(db, "epstein_mode", True)

    logger.warning(
        "epstein_mode_enabled",
        admin_action=True,
    )

    return {
        "enabled": True,
        "epstein_mode": True,
        "message": "EPSTEIN_MODE enabled. Knowledge retrieval now active.",
    }


@app.post("/api/admin/corpus/epstein/disable")
async def admin_corpus_epstein_disable(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Disable EPSTEIN_MODE (admin only).

    This disables:
    - search_knowledge() with source="epstein"
    - Casefile tone blending (EPSTEIN_PERSONA_BLEND is also disabled)
    """
    await verify_admin_key(request)

    # Disable both settings
    await set_runtime_setting(db, "epstein_mode", False)
    await set_runtime_setting(db, "epstein_persona_blend", False)

    logger.warning(
        "epstein_mode_disabled",
        admin_action=True,
    )

    return {
        "disabled": True,
        "epstein_mode": False,
        "epstein_persona_blend": False,
        "message": "EPSTEIN_MODE disabled. Corpus is now inactive.",
    }


# ===========================================
# Conversation Archive (Admin)
# ===========================================


@app.get("/api/admin/conversations")
async def admin_list_conversations(
    request: Request,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    channel: Optional[str] = Query(None, description="Filter by channel (web, x)"),
    q: Optional[str] = Query(None, description="Search in title or messages"),
):
    """
    List all conversations with pagination (admin only).

    Returns conversations sorted by most recent activity (last message).
    """
    await verify_admin_key(request)

    offset = (page - 1) * page_size

    # Subquery for message counts and last active time
    msg_stats = (
        select(
            Message.conversation_id,
            func.count(Message.id).label("message_count"),
            func.max(Message.created_at).label("last_active_at"),
        )
        .group_by(Message.conversation_id)
        .subquery()
    )

    # Get the last message content for snippet using window function
    last_msg = (
        select(
            Message.conversation_id,
            Message.content,
            Message.role,
            func.row_number().over(
                partition_by=Message.conversation_id,
                order_by=Message.created_at.desc()
            ).label("rn")
        )
        .subquery()
    )

    last_msg_filtered = (
        select(
            last_msg.c.conversation_id,
            last_msg.c.content.label("last_content"),
            last_msg.c.role.label("last_role"),
        )
        .where(last_msg.c.rn == 1)
        .subquery()
    )

    # Main query
    base_query = (
        select(
            Conversation.id,
            Conversation.title,
            Conversation.created_at,
            Conversation.user_id,
            func.coalesce(msg_stats.c.message_count, 0).label("message_count"),
            func.coalesce(msg_stats.c.last_active_at, Conversation.created_at).label("last_active_at"),
            last_msg_filtered.c.last_content,
            last_msg_filtered.c.last_role,
        )
        .outerjoin(msg_stats, Conversation.id == msg_stats.c.conversation_id)
        .outerjoin(last_msg_filtered, Conversation.id == last_msg_filtered.c.conversation_id)
    )

    # Apply search filter if provided
    if q:
        search_term = f"%{q}%"
        # Search in title or in any message content
        msg_search = (
            select(Message.conversation_id)
            .where(Message.content.ilike(search_term))
            .distinct()
            .subquery()
        )
        base_query = base_query.where(
            (Conversation.title.ilike(search_term)) |
            (Conversation.id.in_(select(msg_search.c.conversation_id)))
        )

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total_count = total_result.scalar() or 0

    # Apply ordering and pagination
    query = (
        base_query
        .order_by(func.coalesce(msg_stats.c.last_active_at, Conversation.created_at).desc())
        .offset(offset)
        .limit(page_size)
    )

    result = await db.execute(query)
    rows = result.all()

    # Format response
    items = []
    for row in rows:
        snippet = ""
        if row.last_content:
            # Truncate to 100 chars
            snippet = row.last_content[:100]
            if len(row.last_content) > 100:
                snippet += "..."
            if row.last_role:
                snippet = f"[{row.last_role}] {snippet}"

        items.append({
            "id": str(row.id),
            "title": row.title,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "last_active_at": row.last_active_at.isoformat() if row.last_active_at else None,
            "message_count": row.message_count,
            "snippet": snippet,
        })

    has_next = (offset + len(items)) < total_count

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total_count": total_count,
        "has_next": has_next,
    }


@app.get("/api/admin/conversations/{conversation_id}/messages")
async def admin_get_conversation_messages(
    conversation_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    order: str = Query("asc", regex="^(asc|desc)$"),
):
    """
    Get messages for a conversation with pagination (admin only).

    Default ordering is chronological (oldest first, asc).
    Use order=desc for newest first.
    """
    await verify_admin_key(request)

    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID format")

    offset = (page - 1) * page_size

    # Get conversation metadata
    conv_result = await db.execute(
        select(Conversation).where(Conversation.id == conv_uuid)
    )
    conversation = conv_result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get last active time from messages
    last_active_result = await db.execute(
        select(func.max(Message.created_at))
        .where(Message.conversation_id == conv_uuid)
    )
    last_active_at = last_active_result.scalar() or conversation.created_at

    # Get total message count
    count_result = await db.execute(
        select(func.count(Message.id))
        .where(Message.conversation_id == conv_uuid)
    )
    total_count = count_result.scalar() or 0

    # Get messages with pagination
    order_clause = Message.created_at.asc() if order == "asc" else Message.created_at.desc()

    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv_uuid)
        .order_by(order_clause)
        .offset(offset)
        .limit(page_size)
    )
    messages = msg_result.scalars().all()

    # Format response
    items = []
    for msg in messages:
        items.append({
            "id": str(msg.id),
            "role": msg.role,
            "content": msg.content,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
            "metadata": msg.metadata_ or {},
        })

    has_next = (offset + len(items)) < total_count

    return {
        "conversation": {
            "id": str(conversation.id),
            "title": conversation.title,
            "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
            "last_active_at": last_active_at.isoformat() if last_active_at else None,
        },
        "items": items,
        "page": page,
        "page_size": page_size,
        "total_count": total_count,
        "has_next": has_next,
    }


async def set_runtime_setting(db: AsyncSession, key: str, value) -> None:
    """Set a runtime setting in the database."""
    import json

    # Check if x_settings table exists and use it
    query = text("""
        INSERT INTO x_settings (key, value, updated_at)
        VALUES (:key, :value, NOW())
        ON CONFLICT (key) DO UPDATE SET
            value = :value,
            updated_at = NOW()
    """)

    await db.execute(query, {"key": key, "value": json.dumps(value)})
    await db.commit()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

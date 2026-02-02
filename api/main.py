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
from services.social.scheduler import IngestionLoop, TimelinePosterLoop
from services.social.storage import (
    DraftStatus,
    get_draft_repository,
    get_post_repository,
    get_settings_repository,
    PostEntry,
    PostStatus,
)
from services.social.types import PostType

logger = structlog.get_logger()


def is_x_bot_enabled() -> bool:
    """Check if X bot is enabled."""
    return os.getenv("X_BOT_ENABLED", "").lower() in ("true", "1", "yes")


# Global references to scheduler loops for admin control
_ingestion_loop: Optional[IngestionLoop] = None
_timeline_loop: Optional[TimelinePosterLoop] = None
_scheduler_tasks: list[asyncio.Task] = []


def get_ingestion_loop() -> Optional[IngestionLoop]:
    """Get the ingestion loop instance (if running)."""
    return _ingestion_loop


def get_timeline_loop() -> Optional[TimelinePosterLoop]:
    """Get the timeline poster loop instance (if running)."""
    return _timeline_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global _ingestion_loop, _timeline_loop, _scheduler_tasks

    print("AIstein API starting up...")
    logger.info("api_startup")

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

                # Start as background tasks
                ingestion_task = asyncio.create_task(
                    _ingestion_loop.start(),
                    name="x_ingestion_loop",
                )
                timeline_task = asyncio.create_task(
                    _timeline_loop.start(),
                    name="x_timeline_loop",
                )
                _scheduler_tasks = [ingestion_task, timeline_task]

                logger.info(
                    "x_bot_schedulers_started",
                    ingestion_interval=_ingestion_loop.poll_interval,
                    timeline_interval=_timeline_loop.interval,
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
# Health Endpoints
# ===========================================


@app.get("/health")
async def health():
    """Basic health check."""
    return {"status": "ok"}


@app.get("/health/ready")
async def ready(db: AsyncSession = Depends(get_db)):
    """Readiness check with dependency status."""
    db_ok = False
    try:
        await db.execute(select(1))
        db_ok = True
    except Exception:
        pass

    # Check X bot status
    x_bot_ok = True
    x_bot_running = False
    if is_x_bot_enabled():
        ingestion_loop = get_ingestion_loop()
        timeline_loop = get_timeline_loop()
        x_bot_running = (
            ingestion_loop is not None
            and timeline_loop is not None
            and ingestion_loop.get_stats().get("running", False)
            and timeline_loop.get_stats().get("running", False)
        )
        x_bot_ok = x_bot_running

    return {
        "ready": db_ok,
        "checks": {
            "database": db_ok,
            "redis": True,  # TODO: Add real check
            "llm": True,  # TODO: Add real check
            "x_bot": x_bot_ok if is_x_bot_enabled() else None,
        },
        "x_bot_enabled": is_x_bot_enabled(),
        "x_bot_running": x_bot_running,
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
    """Get current token metrics."""
    return {
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
# Agent Stats (Phase 6 placeholder)
# ===========================================


@app.get("/api/stats/agent")
async def get_agent_stats():
    """Get agent statistics."""
    return {
        "messages_processed": 0,
        "messages_replied": 0,
        "channel_breakdown": {"web": 0, "x": 0},
        "learning_score": 0,
        "semantic_memories_count": 0,
        "updated_at": None,
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

    return {
        "enabled": is_x_bot_enabled(),
        "ingestion": ingestion_loop.get_stats() if ingestion_loop else None,
        "timeline": timeline_loop.get_stats() if timeline_loop else None,
        "safe_mode": os.getenv("SAFE_MODE", "").lower() in ("true", "1", "yes"),
        "approval_required": os.getenv("APPROVAL_REQUIRED", "true").lower() in ("true", "1", "yes"),
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

    # Check safe mode
    if os.getenv("SAFE_MODE", "").lower() in ("true", "1", "yes"):
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

    settings_repo = get_settings_repository()

    # Get current settings from env (these are read-only at runtime for now)
    return {
        "safe_mode": os.getenv("SAFE_MODE", "").lower() in ("true", "1", "yes"),
        "approval_required": os.getenv("APPROVAL_REQUIRED", "true").lower() in ("true", "1", "yes"),
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
    return {
        "enabled": os.getenv("SAFE_MODE", "").lower() in ("true", "1", "yes"),
        "note": "To toggle SAFE_MODE, update the .env file and restart the server, or use your deployment platform's config.",
    }


@app.post("/api/admin/kill_switch")
async def admin_toggle_kill_switch(request: Request):
    """
    Toggle kill switch (admin only).

    Note: This cannot dynamically change env vars at runtime.
    Returns instructions for how to enable/disable SAFE_MODE.
    """
    await verify_admin_key(request)

    current = os.getenv("SAFE_MODE", "").lower() in ("true", "1", "yes")

    return {
        "current_state": current,
        "note": "SAFE_MODE cannot be toggled at runtime. To change it:",
        "instructions": [
            "1. Edit your .env file: SAFE_MODE=true (to enable) or SAFE_MODE=false (to disable)",
            "2. Restart the API server",
            "3. Or use your deployment platform's environment variable settings",
        ],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

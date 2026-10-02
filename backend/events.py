"""
Real-Time Event Distribution Layer using Server-Sent Events (SSE) & Redis Pub/Sub.

Architecture:
  RQ Worker / Flask API
         │
         ▼ (publish_complaint_event)
  Redis Pub/Sub (Channel: 'complaints:<ticket_id>' & 'admin:events')
         │
         ▼ (subscribe_complaint_events)
  Flask SSE Stream Generator
         │
         ▼ (text/event-stream)
  Browser (EventSource)

Guarantees:
1. Database remains the authoritative source of truth.
2. Initial event on SSE connect immediately emits current DB status.
3. Citizen access strictly scoped to own ticket; Admin can monitor all.
4. Seamless in-memory event bus fallback when Redis is absent (local dev/testing).
5. No sensitive data, stack traces, or internal server paths exposed.
"""

import json
import logging
import queue
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Generator, Optional

logger = logging.getLogger(__name__)

# Canonical Event Types
EVENT_COMPLAINT_SUBMITTED = "complaint_submitted"
EVENT_PROCESSING_STARTED = "processing_started"
EVENT_STAGE_CHANGED = "processing_stage_changed"
EVENT_PROCESSING_COMPLETED = "processing_completed"
EVENT_PROCESSING_FAILED = "processing_failed"
EVENT_STATUS_CHANGED = "complaint_status_changed"
EVENT_HEARTBEAT = "heartbeat"

# In-memory subscriber registry for testing / fallback mode
_memory_subscribers: Dict[str, list] = {}
_memory_lock = threading.Lock()


def format_sse(data: Dict[str, Any], event: Optional[str] = None, event_id: Optional[str] = None) -> str:
    """Format dictionary as Server-Sent Event string."""
    msg = ""
    if event:
        msg += f"event: {event}\n"
    if event_id:
        msg += f"id: {event_id}\n"
    msg += f"data: {json.dumps(data)}\n\n"
    return msg


def publish_complaint_event(
    ticket_id: str,
    event_type: str,
    payload: Dict[str, Any],
    app=None
) -> None:
    """
    Publish an event to the complaint's channel and admin event channel.
    Uses Redis Pub/Sub in production/async mode, with in-memory fallback for tests.
    """
    if app is None:
        try:
            from flask import current_app
            app = current_app._get_current_object()
        except Exception:
            app = None

    # Sanitized standardized envelope
    timestamp = datetime.now(timezone.utc).isoformat()
    envelope = {
        "event": event_type,
        "ticket_id": ticket_id,
        "complaint_id": ticket_id,
        "timestamp": timestamp,
        **payload,
    }

    # Scrub any accidental internal or sensitive fields
    for forbidden in ("traceback", "stack_trace", "image_full_path", "internal_error"):
        envelope.pop(forbidden, None)

    channel_name = f"complaints:{ticket_id}"
    serialized = json.dumps(envelope)

    # 1. In-memory distribution (for unit tests / sync mode)
    with _memory_lock:
        for ch in (channel_name, "admin:events"):
            if ch in _memory_subscribers:
                for q in _memory_subscribers[ch]:
                    try:
                        q.put_nowait(envelope)
                    except queue.Full:
                        pass

    # 2. Redis Pub/Sub distribution
    redis_url = None
    if app:
        redis_url = app.config.get("REDIS_URL")
        async_mode = app.config.get("ASYNC_MODE", "redis").lower()
        is_testing = app.config.get("TESTING", False)
        if is_testing or async_mode == "sync":
            return

    if redis_url:
        try:
            import redis
            r = redis.from_url(redis_url, socket_connect_timeout=2)
            r.publish(channel_name, serialized)
            r.publish("admin:events", serialized)
            logger.debug("[SSE PubSub] Published '%s' event to %s", event_type, channel_name)
        except Exception as exc:
            logger.debug("[SSE PubSub] Redis publish failed (%s). Event routed via in-memory bus.", exc)


def subscribe_complaint_events(
    ticket_id: str,
    app,
    user_role: str = "citizen",
    heartbeat_interval: int = 15,
    max_duration: int = 300,
) -> Generator[str, None, None]:
    """
    Generator yielding Server-Sent Events for a specific complaint ticket.
    Subscribes to Redis Pub/Sub, emits initial state, and yields real-time events.
    """
    from models import Complaint, db

    channel_name = f"complaints:{ticket_id}"
    logger.info("[SSE] Client connected to event stream for ticket #%s (role: %s)", ticket_id, user_role)

    # 1. Fetch initial state from database (authoritative source of truth)
    initial_data = None
    is_terminal = False
    with app.app_context():
        complaint = db.session.get(Complaint, ticket_id)
        if complaint:
            initial_data = {
                "ticket_id": complaint.id,
                "status": complaint.status,
                "processing_status": complaint.processing_status,
                "stage": complaint.processing_status,
                "progress_message": f"Complaint currently in stage: {complaint.processing_status}",
                "ai_mode": complaint.ai_mode,
                "severity": complaint.severity_level,
                "department": complaint.department,
                "error": complaint.processing_error if (user_role == "admin" or complaint.processing_error) else None,
            }
            if complaint.processing_status in ("COMPLETED", "FAILED") or complaint.status in ("VERIFIED", "DUPLICATE", "PROCESSING_FAILED"):
                is_terminal = True

    if initial_data:
        yield format_sse(initial_data, event="complaint_status", event_id=f"{ticket_id}-init")
        if is_terminal:
            logger.info("[SSE] Ticket #%s is already in terminal state (%s). Closing stream.", ticket_id, initial_data.get("status"))
            return

    # 2. Setup subscription (Redis Pub/Sub or in-memory fallback)
    redis_conn = None
    pubsub = None
    mem_q = queue.Queue(maxsize=100)

    with _memory_lock:
        if channel_name not in _memory_subscribers:
            _memory_subscribers[channel_name] = []
        _memory_subscribers[channel_name].append(mem_q)

    redis_url = app.config.get("REDIS_URL")
    async_mode = app.config.get("ASYNC_MODE", "redis").lower()
    is_testing = app.config.get("TESTING", False)

    if redis_url and not is_testing and async_mode != "sync":
        try:
            import redis
            redis_conn = redis.from_url(redis_url, socket_connect_timeout=2)
            pubsub = redis_conn.pubsub()
            pubsub.subscribe(channel_name)
            logger.info("[SSE] Redis PubSub subscribed to channel %s", channel_name)
        except Exception as exc:
            logger.warning("[SSE] Could not connect to Redis PubSub (%s). Using fallback bus.", exc)
            pubsub = None

    start_time = time.time()
    last_heartbeat = time.time()

    try:
        while time.time() - start_time < max_duration:
            event_received = None

            # Check Redis Pub/Sub if active
            if pubsub:
                try:
                    message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if message and message.get("type") == "message":
                        raw_data = message.get("data")
                        if isinstance(raw_data, bytes):
                            raw_data = raw_data.decode("utf-8")
                        event_received = json.loads(raw_data)
                except Exception as exc:
                    logger.debug("[SSE] PubSub poll error: %s", exc)

            # Check in-memory queue fallback
            if not event_received:
                try:
                    event_received = mem_q.get(timeout=1.0)
                except queue.Empty:
                    pass

            if event_received:
                evt_name = event_received.get("event", "message")
                evt_id = f"{ticket_id}-{int(time.time() * 1000)}"
                yield format_sse(event_received, event=evt_name, event_id=evt_id)

                # Close stream upon reaching terminal states
                if evt_name in (EVENT_PROCESSING_COMPLETED, EVENT_PROCESSING_FAILED) or \
                   event_received.get("processing_status") in ("COMPLETED", "FAILED") or \
                   event_received.get("status") in ("VERIFIED", "DUPLICATE", "PROCESSING_FAILED"):
                    logger.info("[SSE] Terminal state reached for ticket #%s (%s). Closing stream.", ticket_id, evt_name)
                    break

            # Send heartbeat keepalive to prevent browser/proxy timeouts
            if time.time() - last_heartbeat >= heartbeat_interval:
                last_heartbeat = time.time()
                yield format_sse({"timestamp": datetime.now(timezone.utc).isoformat()}, event=EVENT_HEARTBEAT)

    finally:
        logger.info("[SSE] Closing event stream for ticket #%s", ticket_id)
        if pubsub:
            try:
                pubsub.unsubscribe(channel_name)
                pubsub.close()
            except Exception:
                pass
        with _memory_lock:
            if channel_name in _memory_subscribers and mem_q in _memory_subscribers[channel_name]:
                _memory_subscribers[channel_name].remove(mem_q)


def subscribe_admin_events(
    app,
    heartbeat_interval: int = 15,
    max_duration: int = 600,
) -> Generator[str, None, None]:
    """
    Generator yielding Server-Sent Events across all municipal complaints for administrators.
    """
    channel_name = "admin:events"
    logger.info("[SSE Admin] Administrator connected to municipal global event stream")

    mem_q = queue.Queue(maxsize=200)
    with _memory_lock:
        if channel_name not in _memory_subscribers:
            _memory_subscribers[channel_name] = []
        _memory_subscribers[channel_name].append(mem_q)

    pubsub = None
    redis_url = app.config.get("REDIS_URL")
    if redis_url and not app.config.get("TESTING"):
        try:
            import redis
            r = redis.from_url(redis_url, socket_connect_timeout=2)
            pubsub = r.pubsub()
            pubsub.subscribe(channel_name)
        except Exception:
            pubsub = None

    start_time = time.time()
    last_heartbeat = time.time()

    try:
        # Initial greeting event
        yield format_sse({"connected": True, "channel": "admin:events", "role": "admin"}, event="admin_connected")

        while time.time() - start_time < max_duration:
            event_received = None

            if pubsub:
                try:
                    msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if msg and msg.get("type") == "message":
                        raw = msg.get("data")
                        if isinstance(raw, bytes):
                            raw = raw.decode("utf-8")
                        event_received = json.loads(raw)
                except Exception:
                    pass

            if not event_received:
                try:
                    event_received = mem_q.get(timeout=1.0)
                except queue.Empty:
                    pass

            if event_received:
                yield format_sse(event_received, event=event_received.get("event", "admin_event"))

            if time.time() - last_heartbeat >= heartbeat_interval:
                last_heartbeat = time.time()
                yield format_sse({"timestamp": datetime.now(timezone.utc).isoformat()}, event=EVENT_HEARTBEAT)

    finally:
        logger.info("[SSE Admin] Closing municipal event stream")
        if pubsub:
            try:
                pubsub.unsubscribe(channel_name)
                pubsub.close()
            except Exception:
                pass
        with _memory_lock:
            if channel_name in _memory_subscribers and mem_q in _memory_subscribers[channel_name]:
                _memory_subscribers[channel_name].remove(mem_q)

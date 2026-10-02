"""
Phase 4 Tests — Server-Sent Events (SSE) Real-Time Updates & Redis/Memory Event Bus.

Tests:
1. SSE endpoint requires authentication (401 for unauthenticated).
2. SSE endpoint returns 404 for nonexistent ticket.
3. Citizen access control: Citizen cannot subscribe to another citizen's complaint (403).
4. Citizen access control: Citizen can subscribe to own complaint (200, text/event-stream).
5. Admin access control: Admin can subscribe to any citizen complaint.
6. Admin global municipal event stream: Admin allowed (200), Citizen forbidden (403).
7. Initial state emission: SSE stream immediately emits authoritative DB status.
8. Event format standard: format_sse produces standard event-stream syntax.
9. Event sanitization: No stack traces or sensitive internal paths leaked.
10. End-to-end worker event emission: stages and completion events published.
11. Failure event emission: safe error and retry_available published on failure.
12. Duplicate event emission: DUPLICATE status published when nearby duplicate detected.
13. Terminal state connection cleanup: stream terminates gracefully on terminal status.
14. REST fallback endpoint: /processing-status remains fully functional for fallback clients.
"""

import io
import json
import queue
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from PIL import Image

from ai_config import AI_MODE_MOCK_DEMO
from events import (
    EVENT_COMPLAINT_SUBMITTED,
    EVENT_HEARTBEAT,
    EVENT_PROCESSING_COMPLETED,
    EVENT_PROCESSING_FAILED,
    EVENT_PROCESSING_STARTED,
    EVENT_STAGE_CHANGED,
    EVENT_STATUS_CHANGED,
    _memory_lock,
    _memory_subscribers,
    format_sse,
    publish_complaint_event,
    subscribe_complaint_events,
)
from lifecycle import (
    STAGE_ANALYZING_IMAGE,
    STAGE_ASSIGNING_DEPARTMENT,
    STAGE_CALCULATING_SEVERITY,
    STAGE_CHECKING_DUPLICATES,
    STAGE_COMPLETED,
    STAGE_FAILED,
    STAGE_QUEUED,
    STATUS_AI_PROCESSING,
    STATUS_DUPLICATE,
    STATUS_PROCESSING_FAILED,
    STATUS_VERIFIED,
)
from models import Complaint, db
from tasks import process_complaint_job


def _make_dummy_image(color=(120, 80, 40), size=(300, 300)):
    return Image.new("RGB", size, color=color)


def _create_test_complaint(app, user_id=None, status=STATUS_AI_PROCESSING, processing_status=STAGE_QUEUED):
    with app.app_context():
        c = Complaint(
            id="sse00101",
            user_id=user_id or 1,
            image_path="test_image.jpg",
            address="123 Civic Ave",
            latitude=18.5204,
            longitude=73.8567,
            status=status,
            processing_status=processing_status,
            ai_mode=AI_MODE_MOCK_DEMO,
        )
        db.session.add(c)
        db.session.commit()
        return c.id


# ── 1. Authentication & Authorization Tests ─────────────────────────────────

def test_sse_endpoint_requires_auth(client):
    """Unauthenticated users must be rejected with 401."""
    res = client.get("/api/complaints/test1234/events")
    assert res.status_code == 401
    assert "error" in res.get_json()


def test_sse_endpoint_404_for_invalid_ticket(citizen_client):
    """Nonexistent ticket must return 404."""
    res = citizen_client.get("/api/complaints/nonexistent/events")
    assert res.status_code == 404
    assert "Ticket not found" in res.get_json()["error"]


def test_sse_citizen_cannot_subscribe_other_citizen_ticket(app, client):
    """Citizen cannot stream real-time events for another citizen's complaint (403)."""
    with app.app_context():
        # Create complaint belonging to user_id=999
        c = Complaint(
            id="other999",
            user_id=999,
            image_path="sample.jpg",
            address="Restricted St",
            status=STATUS_AI_PROCESSING,
            processing_status=STAGE_QUEUED,
            ai_mode=AI_MODE_MOCK_DEMO,
        )
        db.session.add(c)
        db.session.commit()

    # Login as citizen (user_id != 999)
    client.post("/api/auth/register", json={
        "username": "citizen_spy",
        "email": "spy@example.com",
        "password": "Password123!",
        "role": "citizen"
    })

    res = client.get("/api/complaints/other999/events")
    assert res.status_code == 403
    assert "Access denied" in res.get_json()["error"]


def test_sse_citizen_can_subscribe_own_ticket(app, citizen_client):
    """Citizen can subscribe to their own complaint; receives 200 text/event-stream."""
    # Find citizen user_id
    res_me = citizen_client.get("/api/auth/me")
    uid = res_me.get_json()["user"]["id"]

    with app.app_context():
        c = Complaint(
            id="myown001",
            user_id=uid,
            image_path="sample.jpg",
            address="Home St",
            status=STATUS_AI_PROCESSING,
            processing_status=STAGE_QUEUED,
            ai_mode=AI_MODE_MOCK_DEMO,
        )
        db.session.add(c)
        db.session.commit()

    res = citizen_client.get("/api/complaints/myown001/events")
    assert res.status_code == 200
    assert "text/event-stream" in res.headers["Content-Type"]
    assert "no-cache" in res.headers.get("Cache-Control", "")


def test_sse_admin_can_subscribe_any_ticket(app, admin_client):
    """Admin can subscribe to any citizen complaint stream."""
    with app.app_context():
        c = Complaint(
            id="citiz002",
            user_id=888,
            image_path="sample.jpg",
            address="Downtown St",
            status=STATUS_AI_PROCESSING,
            processing_status=STAGE_QUEUED,
            ai_mode=AI_MODE_MOCK_DEMO,
        )
        db.session.add(c)
        db.session.commit()

    res = admin_client.get("/api/complaints/citiz002/events")
    assert res.status_code == 200
    assert "text/event-stream" in res.headers["Content-Type"]


def test_sse_admin_global_stream_authorization(admin_client, citizen_client):
    """Admin global events stream requires admin role; citizen is rejected with 403."""
    res_cit = citizen_client.get("/api/complaints/admin/events")
    assert res_cit.status_code == 403

    res_adm = admin_client.get("/api/complaints/admin/events")
    assert res_adm.status_code == 200
    assert "text/event-stream" in res_adm.headers["Content-Type"]


# ── 2. Event Formatting & Sanitization Tests ─────────────────────────────────

def test_format_sse_structure():
    """Verify standard SSE wire format serialization."""
    payload = {"ticket_id": "ABC123", "status": "AI_PROCESSING"}
    out = format_sse(payload, event="stage_change", event_id="101")
    assert out.startswith("event: stage_change\n")
    assert "id: 101\n" in out
    assert 'data: {"ticket_id": "ABC123", "status": "AI_PROCESSING"}\n\n' in out


def test_publish_complaint_event_sanitizes_sensitive_fields(app):
    """Ensure sensitive internal keys (traceback, full paths) are scrubbed before publishing."""
    test_q = queue.Queue()
    with _memory_lock:
        _memory_subscribers["complaints:test_scrub"] = [test_q]

    publish_complaint_event(
        ticket_id="test_scrub",
        event_type=EVENT_PROCESSING_FAILED,
        payload={
            "error": "Safe error message",
            "traceback": "Traceback (most recent call last)... secret_path/bad.py",
            "stack_trace": "line 42 in private_function",
            "image_full_path": "/var/data/private/secrets/img.jpg",
        },
        app=app,
    )

    item = test_q.get(timeout=1.0)
    assert item["ticket_id"] == "test_scrub"
    assert item["error"] == "Safe error message"
    assert "traceback" not in item
    assert "stack_trace" not in item
    assert "image_full_path" not in item
    assert "timestamp" in item


# ── 3. Generator Initial State & Terminal Stream Termination ─────────────────

def test_sse_stream_initial_authoritative_state(app):
    """Connecting to SSE stream immediately yields authoritative DB state."""
    with app.app_context():
        c = Complaint(
            id="init_check",
            user_id=1,
            image_path="img.jpg",
            address="Civic Plaza",
            status=STATUS_AI_PROCESSING,
            processing_status=STAGE_ANALYZING_IMAGE,
            ai_mode=AI_MODE_MOCK_DEMO,
            severity_level="High",
            department="Solid Waste",
        )
        db.session.add(c)
        db.session.commit()

    gen = subscribe_complaint_events("init_check", app, user_role="citizen", heartbeat_interval=999, max_duration=1)
    first_chunk = next(gen)

    assert "event: complaint_status\n" in first_chunk
    lines = first_chunk.strip().split("\n")
    data_line = [l for l in lines if l.startswith("data: ")][0]
    data = json.loads(data_line[6:])

    assert data["ticket_id"] == "init_check"
    assert data["status"] == STATUS_AI_PROCESSING
    assert data["processing_status"] == STAGE_ANALYZING_IMAGE
    assert data["severity"] == "High"
    assert data["department"] == "Solid Waste"


def test_sse_stream_terminates_immediately_for_completed_complaint(app):
    """When a complaint is already in a terminal state (VERIFIED), stream yields state and terminates."""
    with app.app_context():
        c = Complaint(
            id="term_check",
            user_id=1,
            image_path="img.jpg",
            address="Terminal Rd",
            status=STATUS_VERIFIED,
            processing_status=STAGE_COMPLETED,
            ai_mode=AI_MODE_MOCK_DEMO,
        )
        db.session.add(c)
        db.session.commit()

    gen = subscribe_complaint_events("term_check", app, user_role="citizen", heartbeat_interval=999, max_duration=2)
    chunks = list(gen)
    # Exactly one chunk (initial status) is emitted, then generator exits
    assert len(chunks) == 1
    assert "event: complaint_status" in chunks[0]


# ── 4. End-to-End Worker Event Emission ──────────────────────────────────────

def test_worker_publishes_all_lifecycle_events(app):
    """Worker execution produces PROCESSING_STARTED, STAGE_CHANGED, and PROCESSING_COMPLETED."""
    events_captured = []
    test_q = queue.Queue()
    ticket_id = "flow001"

    with app.app_context():
        # Setup complaint
        c = Complaint(
            id=ticket_id,
            user_id=1,
            image_path="test_flow.jpg",
            address="Flow St",
            latitude=18.5204,
            longitude=73.8567,
            status=STATUS_AI_PROCESSING,
            processing_status=STAGE_QUEUED,
            ai_mode=AI_MODE_MOCK_DEMO,
        )
        db.session.add(c)
        db.session.commit()

    # Create dummy image in upload folder
    upload_dir = app.config.get("UPLOAD_FOLDER")
    import os
    img_path = os.path.join(upload_dir, "test_flow.jpg")
    _make_dummy_image().save(img_path)

    # Register in-memory queue to capture events
    channel = f"complaints:{ticket_id}"
    with _memory_lock:
        if channel not in _memory_subscribers:
            _memory_subscribers[channel] = []
        _memory_subscribers[channel].append(test_q)

    # Run worker task
    success = process_complaint_job(ticket_id, app=app)
    assert success is True

    # Harvest all published events
    while not test_q.empty():
        events_captured.append(test_q.get_nowait())

    event_types = [e["event"] for e in events_captured]
    assert EVENT_PROCESSING_STARTED in event_types
    assert EVENT_STAGE_CHANGED in event_types
    assert EVENT_PROCESSING_COMPLETED in event_types

    # Verify stage progression
    stages = [e.get("stage") for e in events_captured if e["event"] == EVENT_STAGE_CHANGED]
    assert STAGE_ANALYZING_IMAGE in stages
    assert STAGE_CALCULATING_SEVERITY in stages
    assert STAGE_CHECKING_DUPLICATES in stages
    assert STAGE_ASSIGNING_DEPARTMENT in stages

    # Check completion payload
    comp_event = [e for e in events_captured if e["event"] == EVENT_PROCESSING_COMPLETED][0]
    assert comp_event["status"] == STATUS_VERIFIED
    assert comp_event["processing_status"] == STAGE_COMPLETED
    assert comp_event["severity"] in ("Low", "Medium", "High")
    assert comp_event["department"] is not None
    assert comp_event["is_duplicate"] is False


def test_worker_publishes_failure_event_on_missing_image(app):
    """When processing encounters an unrecoverable error, EVENT_PROCESSING_FAILED is emitted."""
    events_captured = []
    test_q = queue.Queue()
    ticket_id = "fail001"

    with app.app_context():
        c = Complaint(
            id=ticket_id,
            user_id=1,
            image_path="nonexistent_ghost_image.jpg",
            address="Ghost St",
            status=STATUS_AI_PROCESSING,
            processing_status=STAGE_QUEUED,
            ai_mode=AI_MODE_MOCK_DEMO,
        )
        db.session.add(c)
        db.session.commit()

    channel = f"complaints:{ticket_id}"
    with _memory_lock:
        if channel not in _memory_subscribers:
            _memory_subscribers[channel] = []
        _memory_subscribers[channel].append(test_q)

    success = process_complaint_job(ticket_id, app=app)
    assert success is False

    while not test_q.empty():
        events_captured.append(test_q.get_nowait())

    event_types = [e["event"] for e in events_captured]
    assert EVENT_PROCESSING_FAILED in event_types

    fail_evt = [e for e in events_captured if e["event"] == EVENT_PROCESSING_FAILED][0]
    assert fail_evt["status"] == STATUS_PROCESSING_FAILED
    assert fail_evt["processing_status"] == STAGE_FAILED
    assert "could not be found" in fail_evt["error"]
    assert fail_evt["retry_available"] is True


def test_worker_publishes_duplicate_completion_event(app):
    """When a complaint is within 50m of an existing complaint, DUPLICATE is emitted."""
    import os

    events_captured = []
    test_q = queue.Queue()

    with app.app_context():
        # Original complaint
        orig = Complaint(
            id="orig001",
            user_id=1,
            image_path="orig.jpg",
            address="Same Spot",
            latitude=18.5204,
            longitude=73.8567,
            status=STATUS_VERIFIED,
            processing_status=STAGE_COMPLETED,
            ai_mode=AI_MODE_MOCK_DEMO,
        )
        # Duplicate candidate
        dup = Complaint(
            id="dup002",
            user_id=2,
            image_path="dup.jpg",
            address="Same Spot 2m away",
            latitude=18.52041,
            longitude=73.85671,
            status=STATUS_AI_PROCESSING,
            processing_status=STAGE_QUEUED,
            ai_mode=AI_MODE_MOCK_DEMO,
        )
        db.session.add_all([orig, dup])
        db.session.commit()

    upload_dir = app.config.get("UPLOAD_FOLDER")
    _make_dummy_image().save(os.path.join(upload_dir, "dup.jpg"))

    channel = "complaints:dup002"
    with _memory_lock:
        if channel not in _memory_subscribers:
            _memory_subscribers[channel] = []
        _memory_subscribers[channel].append(test_q)

    success = process_complaint_job("dup002", app=app)
    assert success is True

    while not test_q.empty():
        events_captured.append(test_q.get_nowait())

    comp_evt = [e for e in events_captured if e["event"] == EVENT_PROCESSING_COMPLETED][0]
    assert comp_evt["status"] == STATUS_DUPLICATE
    assert comp_evt["is_duplicate"] is True
    assert comp_evt["duplicate_of_id"] == "orig001"


# ── 5. REST Fallback Endpoint Tests ──────────────────────────────────────────

def test_rest_processing_status_fallback(app, citizen_client):
    """The REST /api/complaints/<id>/processing-status endpoint functions cleanly as fallback."""
    res_me = citizen_client.get("/api/auth/me")
    uid = res_me.get_json()["user"]["id"]

    with app.app_context():
        c = Complaint(
            id="fall001",
            user_id=uid,
            image_path="fall.jpg",
            address="Fallback St",
            status=STATUS_AI_PROCESSING,
            processing_status=STAGE_CALCULATING_SEVERITY,
            ai_mode=AI_MODE_MOCK_DEMO,
        )
        db.session.add(c)
        db.session.commit()

    res = citizen_client.get("/api/complaints/fall001/processing-status")
    assert res.status_code == 200
    data = res.get_json()
    assert data["ticket_id"] == "fall001"
    assert data["status"] == STATUS_AI_PROCESSING
    assert data["processing_status"] == STAGE_CALCULATING_SEVERITY
    assert "severity" in data["progress"].lower()

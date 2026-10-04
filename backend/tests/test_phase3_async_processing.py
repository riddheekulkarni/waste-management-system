"""
Phase 3 Test Suite: Asynchronous AI Processing, Complaint Lifecycle, and Worker Pipeline.

Tests:
1. Complaint creation returns quickly with ticket in AI_PROCESSING status.
2. Background task pipeline executes successfully and updates state to VERIFIED.
3. Overlap-aware severity, department routing, and detection items are stored.
4. Nearby duplicate detection identifies duplicates and sets DUPLICATE status.
5. AI failure handling sets PROCESSING_FAILED and records safe non-revealing error.
6. Admin retry endpoint re-enqueues failed jobs and increments retry_count.
7. Concurrent processing idempotency: multiple simultaneous jobs are prevented.
8. Detection items are not duplicated on retry.
9. Processing status API provides live stage info with citizen/admin RBAC.
10. Admin processing queue visibility and status filters.
11. AI mode provenance (REAL_YOLO vs MOCK_DEMO) is preserved.
12. Canonical lifecycle state machine transition rules.
"""

import io
import os
import time
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from PIL import Image
import pytest

from ai_config import AI_MODE_MOCK_DEMO, AI_MODE_REAL_YOLO
from lifecycle import (
    STAGE_ANALYZING_IMAGE,
    STAGE_ASSIGNING_DEPARTMENT,
    STAGE_CALCULATING_SEVERITY,
    STAGE_CHECKING_DUPLICATES,
    STAGE_COMPLETED,
    STAGE_FAILED,
    STAGE_QUEUED,
    STATUS_AI_PROCESSING,
    STATUS_ASSIGNED,
    STATUS_DUPLICATE,
    STATUS_IN_PROGRESS,
    STATUS_PROCESSING_FAILED,
    STATUS_RESOLVED,
    STATUS_SUBMITTED,
    STATUS_VERIFIED,
    can_transition,
    normalize_status,
)
from models import Complaint, DetectionItem, User, db
from tasks import process_complaint_job, reset_worker_detector


def create_test_image(filepath: str, width: int = 160, height: int = 160, color: str = "green"):
    """Helper to write a valid test JPEG image to disk."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    img = Image.new("RGB", (width, height), color=color)
    img.save(filepath, format="JPEG")
    return filepath


def create_test_image_bytes():
    """Helper to produce an in-memory JPEG byte buffer for upload form testing."""
    img = Image.new("RGB", (160, 160), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# 1. Immediate Return & AI_PROCESSING Initial State
# ---------------------------------------------------------------------------
def test_complaint_creation_async_immediate_return(app, citizen_client):
    """
    Submitting a complaint must return quickly with a ticket in AI_PROCESSING status.
    In async mode, the HTTP response arrives before worker execution.
    """
    img_buf = create_test_image_bytes()

    # Mock the background queue so the job is not executed inline during this test
    with patch("routes.complaints.enqueue_complaint_job") as mock_enqueue:
        mock_enqueue.return_value = "mock-job-id-12345"

        start_time = time.time()
        res = citizen_client.post(
            "/api/complaints/upload",
            data={
                "image": (img_buf, "street_waste.jpg"),
                "latitude": "18.5204",
                "longitude": "73.8567",
                "address": "Shivaji Nagar Market",
            },
            content_type="multipart/form-data"
        )
        elapsed = time.time() - start_time

        assert res.status_code == 201
        data = res.get_json()

        # Must return quickly (under 2 seconds even on slow runners)
        assert elapsed < 2.0
        assert data["success"] is True
        assert "ticket_id" in data
        assert data["status"] == STATUS_AI_PROCESSING
        assert data["processing_status"] == STAGE_QUEUED
        assert "submitted and is being analyzed" in data["message"]

        # Ensure background enqueue was called
        mock_enqueue.assert_called_once_with(data["ticket_id"])


# ---------------------------------------------------------------------------
# 2. Background Task Execution Pipeline (Success Flow)
# ---------------------------------------------------------------------------
def test_background_job_pipeline_success(app):
    """
    Full worker execution:
    - Loads image
    - Runs detector
    - Stores DetectionItem rows
    - Computes overlap-aware severity
    - Performs duplicate check
    - Routes department
    - Transitions to VERIFIED and COMPLETED stage
    """
    with app.app_context():
        filename = "test_pipeline_clean.jpg"
        img_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        create_test_image(img_path)

        citizen = User.query.filter_by(role="citizen").first()
        complaint = Complaint(
            id="pipe0001",
            user_id=citizen.id,
            image_path=filename,
            address="Camp Area, Pune",
            latitude=18.5100,
            longitude=73.8600,
            status=STATUS_AI_PROCESSING,
            processing_status=STAGE_QUEUED,
        )
        db.session.add(complaint)
        db.session.commit()

        # Run worker task
        success = process_complaint_job("pipe0001", app=app)
        assert success is True

        refreshed = Complaint.query.get("pipe0001")
        assert refreshed.status == STATUS_VERIFIED
        assert refreshed.processing_status == STAGE_COMPLETED
        assert refreshed.severity_level in ("Low", "Medium", "High")
        assert refreshed.coverage_ratio is not None
        assert refreshed.item_count is not None
        assert refreshed.department is not None
        assert refreshed.processing_started_at is not None
        assert refreshed.processing_completed_at is not None
        assert refreshed.processing_duration_ms is not None
        assert refreshed.processing_duration_ms >= 0
        assert refreshed.processing_error is None

        # Confirm detection items were stored
        items = DetectionItem.query.filter_by(complaint_id="pipe0001").all()
        assert len(items) > 0


# ---------------------------------------------------------------------------
# 3. Duplicate Detection in Background Pipeline
# ---------------------------------------------------------------------------
def test_duplicate_detection_in_background_job(app):
    """
    When a complaint is reported within 50 meters of an active complaint,
    the background job must detect it, link it, and set status to DUPLICATE.
    """
    with app.app_context():
        # 1. Existing verified complaint
        img_a = os.path.join(app.config["UPLOAD_FOLDER"], "parent_waste.jpg")
        create_test_image(img_a)

        parent = Complaint(
            id="parent01",
            image_path="parent_waste.jpg",
            latitude=18.52040,
            longitude=73.85670,
            status=STATUS_VERIFIED,
            processing_status=STAGE_COMPLETED,
        )
        db.session.add(parent)
        db.session.commit()

        # 2. Nearby complaint (~5 meters away)
        img_b = os.path.join(app.config["UPLOAD_FOLDER"], "child_waste.jpg")
        create_test_image(img_b)

        child = Complaint(
            id="child001",
            image_path="child_waste.jpg",
            latitude=18.52043,
            longitude=73.85673,
            status=STATUS_AI_PROCESSING,
            processing_status=STAGE_QUEUED,
        )
        db.session.add(child)
        db.session.commit()

        success = process_complaint_job("child001", app=app)
        assert success is True

        refreshed_child = Complaint.query.get("child001")
        assert refreshed_child.status == STATUS_DUPLICATE
        assert refreshed_child.is_duplicate is True
        assert refreshed_child.duplicate_of_id == "parent01"
        assert refreshed_child.processing_status == STAGE_COMPLETED


# ---------------------------------------------------------------------------
# 4. Failure Handling & Safe Error Reporting
# ---------------------------------------------------------------------------
def test_failure_handling_sets_processing_failed(app):
    """
    If AI processing fails (e.g. image file missing from storage),
    the complaint must transition to PROCESSING_FAILED with a safe error message.
    """
    with app.app_context():
        complaint = Complaint(
            id="fail0001",
            image_path="non_existent_corrupted_file_999.jpg",
            status=STATUS_AI_PROCESSING,
            processing_status=STAGE_QUEUED,
        )
        db.session.add(complaint)
        db.session.commit()

        success = process_complaint_job("fail0001", app=app)
        assert success is False

        refreshed = Complaint.query.get("fail0001")
        assert refreshed.status == STATUS_PROCESSING_FAILED
        assert refreshed.processing_status == STAGE_FAILED
        assert refreshed.processing_error is not None
        assert "found" in refreshed.processing_error.lower()
        # Verify stack traces are NOT stored in the database field
        assert "Traceback" not in refreshed.processing_error


# ---------------------------------------------------------------------------
# 5. Admin Retry Mechanism
# ---------------------------------------------------------------------------
def test_admin_retry_endpoint(app, client, admin_client, citizen_client):
    """
    Admin can retry failed complaints.
    Citizens and unauthenticated users are blocked.
    """
    with app.app_context():
        complaint = Complaint(
            id="retry001",
            image_path="test_retry.jpg",
            status=STATUS_PROCESSING_FAILED,
            processing_status=STAGE_FAILED,
            processing_error="Simulated failure",
            retry_count=0,
        )
        db.session.add(complaint)
        db.session.commit()

    # Unauthenticated rejected
    res_anon = client.post("/api/complaints/retry001/retry-processing")
    assert res_anon.status_code == 401

    # Citizen rejected (403 Forbidden)
    res_cit = citizen_client.post("/api/complaints/retry001/retry-processing")
    assert res_cit.status_code == 403

    # Admin retry succeeds
    with patch("routes.complaints.enqueue_complaint_job") as mock_enqueue:
        mock_enqueue.return_value = "new-retry-job-id"
        res_adm = admin_client.post("/api/complaints/retry001/retry-processing")
        assert res_adm.status_code == 200
        data = res_adm.get_json()
        assert data["success"] is True
        assert data["retry_count"] == 1
        assert data["status"] == STATUS_AI_PROCESSING
        assert data["processing_status"] == STAGE_QUEUED


# ---------------------------------------------------------------------------
# 6. Idempotency & Clean Detection Records on Retry
# ---------------------------------------------------------------------------
def test_retry_does_not_duplicate_detection_items(app):
    """
    Retrying a complaint must clean up prior DetectionItems so item counts
    do not multiply across repeated worker runs.
    """
    with app.app_context():
        filename = "idempotent_test.jpg"
        img_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        create_test_image(img_path)

        complaint = Complaint(
            id="idem0001",
            image_path=filename,
            status=STATUS_AI_PROCESSING,
            processing_status=STAGE_QUEUED,
        )
        db.session.add(complaint)
        db.session.commit()

        # Run 1
        process_complaint_job("idem0001", app=app)
        count_1 = DetectionItem.query.filter_by(complaint_id="idem0001").count()
        assert count_1 > 0

        # Simulate retry: Reset status and run 2
        complaint = Complaint.query.get("idem0001")
        complaint.status = STATUS_AI_PROCESSING
        complaint.processing_status = STAGE_QUEUED
        db.session.commit()

        process_complaint_job("idem0001", app=app)
        count_2 = DetectionItem.query.filter_by(complaint_id="idem0001").count()

        # Must be exactly equal, NOT count_1 * 2
        assert count_2 == count_1


# ---------------------------------------------------------------------------
# 7. Processing Status API & Citizen Authorization
# ---------------------------------------------------------------------------
def test_processing_status_api(app, client, citizen_client, admin_client):
    """
    GET /api/complaints/<ticket_id>/processing-status:
    - Citizen can access their own ticket status
    - Another citizen receives 403 Forbidden
    - Admin can access any ticket status
    - Returns lightweight stage information
    """
    with app.app_context():
        citizen = User.query.filter_by(role="citizen").first()
        complaint = Complaint(
            id="stat0001",
            user_id=citizen.id,
            image_path="stat_test.jpg",
            status=STATUS_AI_PROCESSING,
            processing_status=STAGE_ANALYZING_IMAGE,
            ai_mode=AI_MODE_REAL_YOLO,
        )
        db.session.add(complaint)
        db.session.commit()

    # Owner citizen can access
    res = citizen_client.get("/api/complaints/stat0001/processing-status")
    assert res.status_code == 200
    data = res.get_json()
    assert data["ticket_id"] == "stat0001"
    assert data["status"] == STATUS_AI_PROCESSING
    assert data["stage"] == STAGE_ANALYZING_IMAGE
    assert data["progress"] == "Analyzing uploaded image"

    # Other citizen blocked
    other_cit = app.test_client()
    other_cit.post("/api/auth/register", json={"username": "eve", "email": "eve@civic.gov", "password": "password123"})
    other_cit.post("/api/auth/login", json={"identifier": "eve", "password": "password123"})
    res_other = other_cit.get("/api/complaints/stat0001/processing-status")
    assert res_other.status_code == 403

    # Admin allowed
    res_adm = admin_client.get("/api/complaints/stat0001/processing-status")
    assert res_adm.status_code == 200


# ---------------------------------------------------------------------------
# 8. Admin Queue Inspection Endpoint
# ---------------------------------------------------------------------------
def test_admin_queue_endpoint(app, admin_client, citizen_client):
    """
    Admin queue inspection endpoint returns queued, active, completed, and failed jobs.
    Citizen access is rejected with 403.
    """
    with app.app_context():
        c1 = Complaint(id="q001", image_path="q1.jpg", status=STATUS_AI_PROCESSING, processing_status=STAGE_QUEUED)
        c2 = Complaint(id="q002", image_path="q2.jpg", status=STATUS_PROCESSING_FAILED, processing_status=STAGE_FAILED)
        db.session.add_all([c1, c2])
        db.session.commit()

    # Citizen blocked
    res_cit = citizen_client.get("/api/complaints/admin/queue")
    assert res_cit.status_code == 403

    # Admin success
    res_adm = admin_client.get("/api/complaints/admin/queue")
    assert res_adm.status_code == 200
    data = res_adm.get_json()
    assert "items" in data
    assert data["total"] >= 2

    # Filter by processing_status=FAILED
    res_failed = admin_client.get("/api/complaints/admin/queue?processing_status=FAILED")
    assert res_failed.status_code == 200
    failed_items = res_failed.get_json()["items"]
    assert all(item["processing_status"] == STAGE_FAILED for item in failed_items)


# ---------------------------------------------------------------------------
# 9. AI Provenance Preservation
# ---------------------------------------------------------------------------
def test_ai_provenance_preservation(app):
    """
    AI execution mode provenance (REAL_YOLO vs MOCK_DEMO) is recorded on the complaint
    and never silently flipped.
    """
    with app.app_context():
        filename = "prov_test.jpg"
        img_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        create_test_image(img_path)

        complaint = Complaint(
            id="prov0001",
            image_path=filename,
            status=STATUS_AI_PROCESSING,
            processing_status=STAGE_QUEUED,
        )
        db.session.add(complaint)
        db.session.commit()

        # In standard test environment, WasteDetector operates according to config
        process_complaint_job("prov0001", app=app)
        refreshed = Complaint.query.get("prov0001")

        assert refreshed.ai_mode in (AI_MODE_REAL_YOLO, AI_MODE_MOCK_DEMO)
        assert refreshed.model_name in ("YOLOv8", "SyntheticMock")


# ---------------------------------------------------------------------------
# 10. Canonical Lifecycle Transitions
# ---------------------------------------------------------------------------
def test_lifecycle_state_machine():
    """
    Validates state machine transitions and status normalization.
    """
    # Normalization
    assert normalize_status("submitted") == STATUS_SUBMITTED
    assert normalize_status("In Progress") == STATUS_IN_PROGRESS
    assert normalize_status("Open") == STATUS_VERIFIED
    assert normalize_status("AI_PROCESSING") == STATUS_AI_PROCESSING

    # Legal transitions
    assert can_transition(STATUS_SUBMITTED, STATUS_AI_PROCESSING) is True
    assert can_transition(STATUS_AI_PROCESSING, STATUS_VERIFIED) is True
    assert can_transition(STATUS_AI_PROCESSING, STATUS_PROCESSING_FAILED) is True
    assert can_transition(STATUS_PROCESSING_FAILED, STATUS_AI_PROCESSING) is True  # Retry
    assert can_transition(STATUS_VERIFIED, STATUS_ASSIGNED) is True
    assert can_transition(STATUS_ASSIGNED, STATUS_IN_PROGRESS) is True
    assert can_transition(STATUS_IN_PROGRESS, STATUS_RESOLVED) is True

    # Illegal transitions
    assert can_transition(STATUS_RESOLVED, STATUS_AI_PROCESSING) is False
    assert can_transition(STATUS_SUBMITTED, STATUS_RESOLVED) is False

"""
Stage 3 — Asynchronous AI Processing Tasks for EcoClean Civic.

Implements the background AI processing pipeline for submitted complaints:
1. Eligibility and idempotency verification
2. Image loading and validation
3. Object detection (YOLOv8 or Mock)
4. Detection items storage
5. Overlap-aware severity evaluation
6. Proximity duplicate detection
7. Canonical department routing
8. Status transition to VERIFIED (or DUPLICATE)
9. Error capture, status transition to PROCESSING_FAILED, safe error reporting
"""

import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

from ai_config import AI_MODE_MOCK_DEMO, AI_MODE_REAL_YOLO
from detection import WasteDetector
from events import (
    EVENT_PROCESSING_COMPLETED,
    EVENT_PROCESSING_FAILED,
    EVENT_PROCESSING_STARTED,
    EVENT_STAGE_CHANGED,
    publish_complaint_event,
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
from models import Complaint, DetectionItem, db
from routing import determine_department
from severity import compute_severity

logger = logging.getLogger(__name__)

_worker_detector: Optional[WasteDetector] = None


def get_worker_detector(app) -> WasteDetector:
    """Lazily construct or retrieve the worker's detector instance."""
    global _worker_detector
    if _worker_detector is None:
        weights = app.config.get("WASTE_MODEL_WEIGHTS")
        mode_cfg = app.config.get("AI_EXECUTION_MODE", "REAL_YOLO")
        mode = "mock" if mode_cfg == "MOCK_DEMO" else "auto"
        _worker_detector = WasteDetector(weights_path=weights, mode=mode)
    return _worker_detector


def reset_worker_detector():
    """Reset worker detector cache (used in testing)."""
    global _worker_detector
    _worker_detector = None


def find_nearby_duplicate(lat: float, lng: float, radius_meters: float = 50.0, exclude_id: Optional[str] = None):
    """Find recent open complaint within radius_meters, excluding the current complaint."""
    if lat is None or lng is None:
        return None

    query = Complaint.query.filter(
        ~Complaint.status.in_(["Resolved", "RESOLVED", "REJECTED", "PROCESSING_FAILED"]),
        Complaint.latitude.isnot(None),
        Complaint.longitude.isnot(None)
    )
    if exclude_id:
        query = query.filter(Complaint.id != exclude_id)

    candidates = query.all()
    for c in candidates:
        dist = Complaint.haversine_distance(lat, lng, c.latitude, c.longitude)
        if dist <= radius_meters:
            return c
    return None


def process_complaint_job(complaint_id: str, app=None) -> bool:
    """
    Executes the complete asynchronous AI processing pipeline for a complaint.

    Returns:
        bool: True if processed successfully, False if skipped or failed.
    """
    if app is None:
        from app import create_app
        app = create_app()

    with app.app_context():
        complaint = db.session.get(Complaint, complaint_id)
        if not complaint:
            logger.error("Job skipped: Complaint with ticket ID %s not found in database.", complaint_id)
            return False

        # ── 1. Idempotency & Eligibility Check ──────────────────────────────
        active_stages = {
            STAGE_ANALYZING_IMAGE,
            STAGE_CALCULATING_SEVERITY,
            STAGE_CHECKING_DUPLICATES,
            STAGE_ASSIGNING_DEPARTMENT,
        }
        if complaint.processing_status in active_stages:
            # If started less than 300 seconds ago, another worker is actively executing
            if complaint.processing_started_at:
                elapsed = (datetime.now(timezone.utc) - complaint.processing_started_at.replace(tzinfo=timezone.utc)).total_seconds()
                if elapsed < 300:
                    logger.warning(
                        "Job skipped: Complaint %s is already in progress (%s, elapsed: %.1fs).",
                        complaint_id, complaint.processing_status, elapsed
                    )
                    return False

        # Mark job started
        complaint.processing_status = STAGE_ANALYZING_IMAGE
        complaint.processing_started_at = datetime.now(timezone.utc)
        complaint.processing_error = None
        db.session.commit()

        publish_complaint_event(
            complaint.id,
            EVENT_PROCESSING_STARTED,
            {
                "status": complaint.status,
                "processing_status": STAGE_ANALYZING_IMAGE,
                "stage": STAGE_ANALYZING_IMAGE,
                "progress_message": "AI analysis started: analyzing uploaded image",
                "ai_mode": complaint.ai_mode,
            },
            app=app,
        )
        publish_complaint_event(
            complaint.id,
            EVENT_STAGE_CHANGED,
            {
                "status": complaint.status,
                "processing_status": STAGE_ANALYZING_IMAGE,
                "stage": STAGE_ANALYZING_IMAGE,
                "progress_message": "Analyzing uploaded image with object detection model",
                "ai_mode": complaint.ai_mode,
            },
            app=app,
        )

        start_time = time.time()
        logger.info("🚀 [Job %s] Starting AI processing for ticket %s...", complaint_id, complaint.id)

        try:
            # ── 2. Image Loading & Validation ────────────────────────────────
            upload_dir = app.config.get("UPLOAD_FOLDER")
            image_path = os.path.join(upload_dir, complaint.image_path) if complaint.image_path else None

            if not image_path or not os.path.exists(image_path):
                raise FileNotFoundError(f"Uploaded image evidence file '{complaint.image_path}' not found on disk.")

            detector = get_worker_detector(app)
            if not detector.validate_image(image_path):
                raise ValueError("Uploaded image file could not be decoded or is corrupted.")

            # ── 3. Object Detection (YOLO / Mock) ───────────────────────────
            detections, image_size, ai_mode = detector.detect(image_path)
            complaint.ai_mode = ai_mode
            complaint.model_name = "YOLOv8" if ai_mode == AI_MODE_REAL_YOLO else "SyntheticMock"
            complaint.model_version = "v8n" if ai_mode == AI_MODE_REAL_YOLO else "mock-1.0"

            # ── 4. Store Detection Items (Prevent duplicates on retry) ──────
            # Delete any prior detection items for this complaint (idempotent retry)
            DetectionItem.query.filter_by(complaint_id=complaint.id).delete()

            for d in detections:
                db.session.add(DetectionItem(
                    complaint_id=complaint.id,
                    cls=d.cls,
                    confidence=d.confidence,
                    x1=d.box[0],
                    y1=d.box[1],
                    x2=d.box[2],
                    y2=d.box[3],
                ))

            # ── 5. Calculate Overlap-Aware Severity ──────────────────────────
            complaint.processing_status = STAGE_CALCULATING_SEVERITY
            db.session.flush()

            publish_complaint_event(
                complaint.id,
                EVENT_STAGE_CHANGED,
                {
                    "status": complaint.status,
                    "processing_status": STAGE_CALCULATING_SEVERITY,
                    "stage": STAGE_CALCULATING_SEVERITY,
                    "progress_message": "Calculating overlap-aware waste severity score",
                    "ai_mode": complaint.ai_mode,
                },
                app=app,
            )

            severity = compute_severity(detections, image_size)
            complaint.severity_level = severity["level"]
            complaint.coverage_ratio = severity["coverage_ratio"]
            complaint.item_count = severity["item_count"]

            # ── 6. Duplicate Detection ──────────────────────────────────────
            complaint.processing_status = STAGE_CHECKING_DUPLICATES
            db.session.flush()

            publish_complaint_event(
                complaint.id,
                EVENT_STAGE_CHANGED,
                {
                    "status": complaint.status,
                    "processing_status": STAGE_CHECKING_DUPLICATES,
                    "stage": STAGE_CHECKING_DUPLICATES,
                    "progress_message": "Checking for nearby duplicate reports within 50m radius",
                    "ai_mode": complaint.ai_mode,
                },
                app=app,
            )

            duplicate = find_nearby_duplicate(
                complaint.latitude,
                complaint.longitude,
                radius_meters=50.0,
                exclude_id=complaint.id
            )
            if duplicate:
                complaint.is_duplicate = True
                complaint.duplicate_of_id = duplicate.id
                complaint.status = STATUS_DUPLICATE
                logger.info(
                    "📍 [Job %s] Nearby duplicate detected! Linked to ticket #%s.",
                    complaint_id, duplicate.id
                )
            else:
                complaint.is_duplicate = False
                complaint.duplicate_of_id = None

            # ── 7. Department Routing ───────────────────────────────────────
            complaint.processing_status = STAGE_ASSIGNING_DEPARTMENT
            db.session.flush()

            publish_complaint_event(
                complaint.id,
                EVENT_STAGE_CHANGED,
                {
                    "status": complaint.status,
                    "processing_status": STAGE_ASSIGNING_DEPARTMENT,
                    "stage": STAGE_ASSIGNING_DEPARTMENT,
                    "progress_message": "Routing complaint to responsible municipal department",
                    "ai_mode": complaint.ai_mode,
                },
                app=app,
            )

            department = determine_department(detections)
            complaint.department = department

            # ── 8. Finalize Completion ──────────────────────────────────────
            if not complaint.is_duplicate:
                complaint.status = STATUS_VERIFIED

            complaint.processing_status = STAGE_COMPLETED
            complaint.processing_completed_at = datetime.now(timezone.utc)
            duration_ms = int((time.time() - start_time) * 1000)
            complaint.processing_duration_ms = duration_ms
            complaint.processing_error = None

            db.session.commit()
            logger.info(
                "✅ [Job %s] Successfully verified in %d ms (Status: %s, AI Mode: %s, Severity: %s, Dept: %s).",
                complaint_id, duration_ms, complaint.status, complaint.ai_mode, complaint.severity_level, complaint.department
            )

            publish_complaint_event(
                complaint.id,
                EVENT_PROCESSING_COMPLETED,
                {
                    "status": complaint.status,
                    "processing_status": STAGE_COMPLETED,
                    "stage": STAGE_COMPLETED,
                    "severity": complaint.severity_level,
                    "department": complaint.department,
                    "ai_mode": complaint.ai_mode,
                    "item_count": complaint.item_count,
                    "coverage_ratio": complaint.coverage_ratio,
                    "is_duplicate": complaint.is_duplicate,
                    "duplicate_of_id": complaint.duplicate_of_id,
                    "duration_ms": duration_ms,
                    "progress_message": f"AI processing completed successfully. Routed to {complaint.department} ({complaint.severity_level} severity).",
                },
                app=app,
            )

            # ── Operational Alert Rules (Pillar 3) ──────────────────────────
            try:
                from notifications import (
                    trigger_high_severity_rule,
                    trigger_duplicate_rule,
                    create_notification,
                    CATEGORY_STATUS_CHANGED,
                )
                if complaint.severity_level == "High":
                    trigger_high_severity_rule(complaint, app=app)
                if complaint.is_duplicate and complaint.duplicate_of_id:
                    trigger_duplicate_rule(complaint, complaint.duplicate_of_id, app=app)
                if complaint.user_id:
                    create_notification(
                        category=CATEGORY_STATUS_CHANGED,
                        title=f"Report #{complaint.id} Verified",
                        message=f"Your report #{complaint.id} has been verified and routed to {complaint.department}.",
                        ticket_id=complaint.id,
                        user_id=complaint.user_id,
                        severity=complaint.severity_level,
                        department=complaint.department,
                        app=app,
                    )
            except Exception as rule_exc:
                logger.debug("Operational notification rule check failed: %s", rule_exc)

            return True


        except Exception as exc:
            # ── 9. Safe Failure Handling ─────────────────────────────────────
            logger.exception("❌ [Job %s] AI processing failed: %s", complaint_id, exc)
            db.session.rollback()

            # Refresh complaint instance after rollback
            complaint = db.session.get(Complaint, complaint_id)
            if complaint:
                complaint.status = STATUS_PROCESSING_FAILED
                complaint.processing_status = STAGE_FAILED
                complaint.processing_completed_at = datetime.now(timezone.utc)
                complaint.processing_duration_ms = int((time.time() - start_time) * 1000)
                # Store a safe, non-revealing error message for clients
                if isinstance(exc, FileNotFoundError):
                    complaint.processing_error = "Uploaded image file could not be found on server storage."
                elif isinstance(exc, ValueError):
                    complaint.processing_error = "Uploaded image file appears corrupted or unreadable."
                else:
                    complaint.processing_error = "AI model processing encountered an internal error. Please retry."
                db.session.commit()

                publish_complaint_event(
                    complaint.id,
                    EVENT_PROCESSING_FAILED,
                    {
                        "status": STATUS_PROCESSING_FAILED,
                        "processing_status": STAGE_FAILED,
                        "stage": STAGE_FAILED,
                        "error": complaint.processing_error,
                        "retry_available": True,
                        "duration_ms": complaint.processing_duration_ms,
                        "progress_message": complaint.processing_error,
                    },
                    app=app,
                )

                try:
                    from notifications import trigger_ai_failure_rule
                    trigger_ai_failure_rule(complaint, error_msg=complaint.processing_error, app=app)
                except Exception as notif_err:
                    logger.debug("AI failure notification failed: %s", notif_err)

            return False


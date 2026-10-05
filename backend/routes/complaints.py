from datetime import datetime, timezone, timedelta
import math
import os
import uuid
from flask import Blueprint, Response, current_app, jsonify, request, session
from PIL import Image
from werkzeug.utils import secure_filename

from ai_config import CANONICAL_DEPARTMENT_MAP
from events import (
    EVENT_COMPLAINT_SUBMITTED,
    EVENT_STAGE_CHANGED,
    EVENT_STATUS_CHANGED,
    EVENT_RESOLUTION_SUBMITTED,
    EVENT_CITIZEN_FEEDBACK,
    EVENT_RESOLUTION_CONFIRMED,
    EVENT_RESOLUTION_NEEDS_ATTENTION,
    publish_complaint_event,
    subscribe_admin_events,
    subscribe_complaint_events,
)
from extensions import limiter
from lifecycle import (
    ALL_CANONICAL_STATUSES,
    ALL_PROCESSING_STAGES,
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
    STATUS_RESOLUTION_SUBMITTED,
    STATUS_RESOLVED,
    STATUS_VERIFIED,
    can_transition,
    normalize_status,
)
from models import Complaint, DetectionItem, CitizenFeedback, db
from notifications import (
    notify_citizen,
    trigger_resolution_submitted_notification,
    trigger_citizen_feedback_notification,
)
from job_queue import enqueue_complaint_job
from routes.auth import login_required, require_role
from tasks import find_nearby_duplicate

complaints_bp = Blueprint("complaints", __name__, url_prefix="/api/complaints")

VALID_STATUSES = ALL_CANONICAL_STATUSES | {"Open", "In Progress", "Resolved", "Closed"}
VALID_SEVERITIES = {"Low", "Medium", "High", "PENDING"}
VALID_DEPARTMENTS = set(CANONICAL_DEPARTMENT_MAP.values()) | {"PENDING_TRIAGE"}
MAX_PER_PAGE = 100


def allowed_file(filename: str) -> bool:
    allowed = current_app.config.get("ALLOWED_EXTENSIONS", {"png", "jpg", "jpeg", "webp"})
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed


def get_upload_limit():
    if not current_app.config.get("RATELIMIT_ENABLED", True):
        return "1000 per hour"
    if not current_app.config.get("IS_PRODUCTION", False):
        return "120 per hour"
    return os.environ.get("RATELIMIT_UPLOAD", "30 per hour")


@complaints_bp.route("/upload", methods=["POST"])
@login_required
@limiter.limit(get_upload_limit, error_message="Upload rate limit exceeded. Please try again later.")
def upload_complaint():
    """
    Submits a new waste complaint for asynchronous AI processing.
    Validates inputs and image file, creates the complaint record in AI_PROCESSING,
    enqueues the background job, and returns the ticket immediately.
    """
    if "image" not in request.files:
        return jsonify({"error": "No image file provided (field name 'image')", "status_code": 400}), 400

    image_file = request.files["image"]
    if not image_file or image_file.filename == "":
        return jsonify({"error": "Empty filename provided.", "status_code": 400}), 400

    if not allowed_file(image_file.filename):
        return jsonify({"error": "Invalid file type. Allowed formats: PNG, JPG, JPEG, WEBP.", "status_code": 400}), 400

    # Validate coordinate inputs
    raw_lat = request.form.get("latitude")
    raw_lng = request.form.get("longitude")
    latitude = None
    longitude = None

    if raw_lat is not None and str(raw_lat).strip() != "":
        try:
            latitude = float(raw_lat)
            if not (-90.0 <= latitude <= 90.0):
                return jsonify({"error": "Latitude must be between -90.0 and 90.0 degrees.", "status_code": 400}), 400
        except ValueError:
            return jsonify({"error": "Invalid latitude value. Must be a valid float.", "status_code": 400}), 400

    if raw_lng is not None and str(raw_lng).strip() != "":
        try:
            longitude = float(raw_lng)
            if not (-180.0 <= longitude <= 180.0):
                return jsonify({"error": "Longitude must be between -180.0 and 180.0 degrees.", "status_code": 400}), 400
        except ValueError:
            return jsonify({"error": "Invalid longitude value. Must be a valid float.", "status_code": 400}), 400

    address = request.form.get("address", "").strip()
    if address and len(address) > 500:
        address = address[:500]

    safe_fname = secure_filename(image_file.filename) or "waste_upload.jpg"
    filename = f"{uuid.uuid4().hex}_{safe_fname}"
    save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    image_file.save(save_path)

    # Validate image decoding
    try:
        with Image.open(save_path) as img:
            img.verify()
    except Exception:
        if os.path.exists(save_path):
            os.remove(save_path)
        return jsonify({"error": "Uploaded file is not a valid or readable image.", "status_code": 400}), 400

    user_id = session.get("user_id")
    configured_ai_mode = current_app.config.get("AI_EXECUTION_MODE", "REAL_YOLO")

    # Create complaint record in AI_PROCESSING status
    complaint = Complaint(
        user_id=user_id,
        image_path=filename,
        address=address or "Location specified on map",
        latitude=latitude,
        longitude=longitude,
        severity_level=None,
        coverage_ratio=None,
        item_count=None,
        department=None,
        status=STATUS_AI_PROCESSING,
        processing_status=STAGE_QUEUED,
        is_duplicate=False,
        duplicate_of_id=None,
        ai_mode=configured_ai_mode,
    )
    complaint.id = str(uuid.uuid4())[:8]

    db.session.add(complaint)
    db.session.commit()

    publish_complaint_event(
        complaint.id,
        EVENT_COMPLAINT_SUBMITTED,
        {
            "status": complaint.status,
            "processing_status": complaint.processing_status,
            "stage": complaint.processing_status,
            "ai_mode": complaint.ai_mode,
            "progress_message": "Complaint submitted and queued for AI analysis",
        },
        app=current_app._get_current_object(),
    )

    # Enqueue background job (or run synchronously in tests/sync mode)
    job_id = enqueue_complaint_job(complaint.id)

    # Refresh complaint in case sync worker executed immediately
    db.session.refresh(complaint)

    res_data = complaint.to_dict()
    res_data.update({
        "success": True,
        "ticket_id": complaint.id,
        "complaint_id": complaint.id,
        "status": complaint.status,
        "processing_status": complaint.processing_status,
        "job_id": str(job_id) if job_id else None,
        "message": "Your complaint has been submitted and is being analyzed.",
    })

    return jsonify(res_data), 201


@complaints_bp.route("/check-duplicate", methods=["POST"])
@limiter.limit("30 per minute", error_message="Too many duplicate checks. Please slow down.")
def check_duplicate():
    data = request.get_json() or {}
    lat_val = data.get("latitude")
    lng_val = data.get("longitude")

    if lat_val is None or lng_val is None:
        return jsonify({"is_duplicate": False, "nearby_ticket": None})

    try:
        lat = float(lat_val)
        lng = float(lng_val)
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
            return jsonify({"error": "Coordinates out of bounds.", "status_code": 400}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid latitude or longitude values.", "status_code": 400}), 400

    duplicate = find_nearby_duplicate(lat, lng, radius_meters=50.0)
    if duplicate:
        return jsonify({
            "is_duplicate": True,
            "nearby_ticket": duplicate.to_dict(include_detections=False)
        })

    return jsonify({"is_duplicate": False, "nearby_ticket": None})


@complaints_bp.route("", methods=["GET"])
@login_required
def list_complaints():
    query = Complaint.query
    user_id = session.get("user_id")
    role = session.get("role")

    # Citizen access is strictly scoped to their own complaints
    if role == "citizen":
        query = query.filter_by(user_id=user_id)

    status = request.args.get("status")
    processing_status = request.args.get("processing_status")
    department = request.args.get("department")
    severity_level = request.args.get("severity")
    ai_mode = request.args.get("ai_mode")

    # Filter parameter validations
    if status:
        norm_status = normalize_status(status)
        if norm_status not in VALID_STATUSES and status not in VALID_STATUSES:
            return jsonify({
                "error": f"Invalid status filter '{status}'.",
                "status_code": 400
            }), 400
        query = query.filter((Complaint.status == status) | (Complaint.status == norm_status))

    if processing_status:
        upper_proc = processing_status.upper()
        if upper_proc not in ALL_PROCESSING_STAGES:
            return jsonify({
                "error": f"Invalid processing_status filter '{processing_status}'.",
                "status_code": 400
            }), 400
        query = query.filter_by(processing_status=upper_proc)

    if department:
        if department not in VALID_DEPARTMENTS:
            return jsonify({
                "error": f"Invalid department filter '{department}'.",
                "status_code": 400
            }), 400
        query = query.filter_by(department=department)

    if severity_level:
        if severity_level not in VALID_SEVERITIES:
            return jsonify({
                "error": f"Invalid severity filter '{severity_level}'.",
                "status_code": 400
            }), 400
        query = query.filter_by(severity_level=severity_level)

    if ai_mode:
        query = query.filter_by(ai_mode=ai_mode)

    search_query = request.args.get("q") or request.args.get("search")
    if search_query:
        sq = f"%{search_query.strip()}%"
        query = query.filter(
            (Complaint.id.ilike(sq)) |
            (Complaint.address.ilike(sq))
        )

    # Server-Side Pagination
    raw_page = request.args.get("page", 1)
    raw_per_page = request.args.get("per_page", 20)

    try:
        page = int(raw_page)
        per_page = int(raw_per_page)
    except (ValueError, TypeError):
        return jsonify({
            "error": "Pagination parameters 'page' and 'per_page' must be valid integers.",
            "status_code": 400
        }), 400

    if page < 1:
        return jsonify({"error": "page parameter must be greater than or equal to 1.", "status_code": 400}), 400
    if per_page < 1:
        return jsonify({"error": "per_page parameter must be greater than or equal to 1.", "status_code": 400}), 400

    per_page = min(per_page, MAX_PER_PAGE)

    total = query.count()
    pages = max(1, math.ceil(total / per_page)) if total > 0 else 1

    complaints = (
        query.order_by(Complaint.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    items = [c.to_dict(include_detections=True) for c in complaints]
    return jsonify({
        "items": items,
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
    })


@complaints_bp.route("/<ticket_id>", methods=["GET"])
@login_required
def get_complaint(ticket_id):
    safe_id = str(ticket_id).strip()
    if not safe_id or len(safe_id) > 16:
        return jsonify({"error": "Invalid ticket ID format.", "status_code": 400}), 400

    complaint = db.session.get(Complaint, safe_id)
    if not complaint:
        return jsonify({"error": "Ticket not found.", "status_code": 404}), 404

    # Authorization Check: Citizen may strictly view only their own ticket
    role = session.get("role")
    user_id = session.get("user_id")

    if role != "admin" and complaint.user_id != user_id:
        return jsonify({
            "error": "Access denied. You may only view your own complaints.",
            "status_code": 403
        }), 403

    return jsonify(complaint.to_dict())


@complaints_bp.route("/<ticket_id>/processing-status", methods=["GET"])
@login_required
def get_processing_status(ticket_id):
    """
    Lightweight endpoint returning live AI job progress and stage information.
    """
    safe_id = str(ticket_id).strip()
    if not safe_id or len(safe_id) > 16:
        return jsonify({"error": "Invalid ticket ID format.", "status_code": 400}), 400

    complaint = db.session.get(Complaint, safe_id)
    if not complaint:
        return jsonify({"error": "Ticket not found.", "status_code": 404}), 404

    role = session.get("role")
    user_id = session.get("user_id")

    if role != "admin" and complaint.user_id != user_id:
        return jsonify({
            "error": "Access denied. You may only view your own complaints.",
            "status_code": 403
        }), 403

    stage_descriptions = {
        STAGE_QUEUED: "Waiting in queue for AI processing",
        STAGE_ANALYZING_IMAGE: "Analyzing uploaded image",
        STAGE_CALCULATING_SEVERITY: "Calculating severity score",
        STAGE_CHECKING_DUPLICATES: "Checking for nearby duplicate reports",
        STAGE_ASSIGNING_DEPARTMENT: "Routing to responsible municipal department",
        STAGE_COMPLETED: "AI analysis completed",
        STAGE_FAILED: "AI analysis failed",
    }

    return jsonify({
        "ticket_id": complaint.id,
        "status": complaint.status,
        "processing_status": complaint.processing_status,
        "stage": complaint.processing_status,
        "progress": stage_descriptions.get(complaint.processing_status, complaint.processing_status),
        "ai_mode": complaint.ai_mode,
        "duration_ms": complaint.processing_duration_ms,
        "retry_count": complaint.retry_count,
        "error": complaint.processing_error,
    }), 200


@complaints_bp.route("/<ticket_id>/retry-processing", methods=["POST"])
@require_role("admin")
def retry_processing(ticket_id):
    """
    Admin-only endpoint to re-enqueue a failed complaint for AI analysis.
    Protects against simultaneous duplicate execution.
    """
    safe_id = str(ticket_id).strip()
    if not safe_id or len(safe_id) > 16:
        return jsonify({"error": "Invalid ticket ID format.", "status_code": 400}), 400

    complaint = db.session.get(Complaint, safe_id)
    if not complaint:
        return jsonify({"error": "Ticket not found.", "status_code": 404}), 404

    # Prevent concurrent processing jobs
    active_stages = {
        STAGE_ANALYZING_IMAGE,
        STAGE_CALCULATING_SEVERITY,
        STAGE_CHECKING_DUPLICATES,
        STAGE_ASSIGNING_DEPARTMENT,
    }
    if complaint.processing_status in active_stages:
        return jsonify({
            "error": f"Complaint is already actively processing in stage '{complaint.processing_status}'.",
            "status_code": 409
        }), 409

    # Re-arm complaint for processing
    complaint.status = STATUS_AI_PROCESSING
    complaint.processing_status = STAGE_QUEUED
    complaint.processing_error = None
    complaint.retry_count = (complaint.retry_count or 0) + 1
    db.session.commit()

    publish_complaint_event(
        complaint.id,
        EVENT_STAGE_CHANGED,
        {
            "status": complaint.status,
            "processing_status": complaint.processing_status,
            "stage": complaint.processing_status,
            "retry_count": complaint.retry_count,
            "progress_message": f"AI processing job re-enqueued for retry attempt {complaint.retry_count}",
        },
        app=current_app._get_current_object(),
    )

    job_id = enqueue_complaint_job(complaint.id)
    db.session.refresh(complaint)

    return jsonify({
        "success": True,
        "ticket_id": complaint.id,
        "status": complaint.status,
        "processing_status": complaint.processing_status,
        "retry_count": complaint.retry_count,
        "job_id": str(job_id) if job_id else None,
        "message": "AI processing job re-enqueued successfully.",
    }), 200


@complaints_bp.route("/admin/queue", methods=["GET"])
@require_role("admin")
def admin_processing_queue():
    """
    Admin endpoint providing visibility into queued, active, completed, and failed AI jobs.
    """
    query = Complaint.query

    proc_status = request.args.get("processing_status")
    if proc_status:
        query = query.filter_by(processing_status=proc_status.upper())

    ai_mode = request.args.get("ai_mode")
    if ai_mode:
        query = query.filter_by(ai_mode=ai_mode)

    raw_page = request.args.get("page", 1)
    raw_per_page = request.args.get("per_page", 20)

    try:
        page = max(1, int(raw_page))
        per_page = min(MAX_PER_PAGE, max(1, int(raw_per_page)))
    except (ValueError, TypeError):
        page, per_page = 1, 20

    total = query.count()
    pages = max(1, math.ceil(total / per_page)) if total > 0 else 1

    complaints = (
        query.order_by(Complaint.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    items = []
    for c in complaints:
        item = c.to_dict(include_detections=False)
        item["retryable"] = c.status in (STATUS_PROCESSING_FAILED, "FAILED") or c.processing_status == STAGE_FAILED
        items.append(item)

    return jsonify({
        "items": items,
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
    }), 200


@complaints_bp.route("/<ticket_id>/status", methods=["PATCH"])
@require_role("admin")
def update_status(ticket_id):
    safe_id = str(ticket_id).strip()
    if not safe_id or len(safe_id) > 16:
        return jsonify({"error": "Invalid ticket ID format.", "status_code": 400}), 400

    if not request.is_json or "status" not in request.json:
        return jsonify({"error": "Provide JSON body with 'status' field.", "status_code": 400}), 400

    complaint = db.session.get(Complaint, safe_id)
    if not complaint:
        return jsonify({"error": "Ticket not found.", "status_code": 404}), 404

    new_status = request.json["status"]
    norm_status = normalize_status(new_status)

    if norm_status not in VALID_STATUSES and new_status not in VALID_STATUSES:
        return jsonify({
            "error": f"Invalid status '{new_status}'.",
            "status_code": 400
        }), 400

    target_status = norm_status if norm_status in ALL_CANONICAL_STATUSES else new_status
    if not can_transition(complaint.status, target_status):
        return jsonify({
            "error": f"Illegal status transition from '{complaint.status}' to '{new_status}'.",
            "status_code": 400
        }), 400

    complaint.status = new_status if new_status in VALID_STATUSES else (norm_status or new_status)

    if "department" in request.json:
        dept = request.json["department"]
        if dept and dept not in VALID_DEPARTMENTS:
            return jsonify({
                "error": f"Invalid department '{dept}'.",
                "status_code": 400
            }), 400
        complaint.department = dept

    db.session.commit()

    publish_complaint_event(
        complaint.id,
        EVENT_STATUS_CHANGED,
        {
            "status": complaint.status,
            "processing_status": complaint.processing_status,
            "stage": complaint.processing_status,
            "department": complaint.department,
            "severity": complaint.severity_level,
            "progress_message": f"Complaint status updated to {complaint.status}",
        },
        app=current_app._get_current_object(),
    )

    recipient_email = complaint.user.email if complaint.user else None
    notification_result = notify_citizen(complaint.id, complaint.status, recipient_email=recipient_email)
    res_dict = complaint.to_dict()
    res_dict["notification"] = notification_result

    return jsonify(res_dict)


@complaints_bp.route("/<ticket_id>/resolution", methods=["POST"])
@require_role("admin")
def submit_resolution(ticket_id):
    """
    Submits field resolution evidence for an assigned or in-progress complaint.
    Strictly restricted to authorized municipal / admin personnel.
    """
    safe_id = str(ticket_id).strip()
    if not safe_id or len(safe_id) > 16:
        return jsonify({"error": "Invalid ticket ID format.", "status_code": 400}), 400

    complaint = db.session.get(Complaint, safe_id)
    if not complaint:
        return jsonify({"error": "Ticket not found.", "status_code": 404}), 404

    # Validate lifecycle transition: complaint must be in ASSIGNED or IN_PROGRESS
    if not can_transition(complaint.status, STATUS_RESOLUTION_SUBMITTED):
        return jsonify({
            "error": f"Cannot submit resolution for ticket in status '{complaint.status}'. Ticket must be in ASSIGNED or IN_PROGRESS.",
            "status_code": 400
        }), 400

    # Extract resolution note
    note = ""
    if request.is_json:
        note = (request.json.get("note") or "").strip()
    else:
        note = (request.form.get("note") or "").strip()

    # Image handling
    image_filename = None
    if "image" in request.files:
        file = request.files["image"]
        if file and file.filename:
            if not allowed_file(file.filename):
                return jsonify({"error": "Unsupported file format for resolution image.", "status_code": 400}), 400
            try:
                img = Image.open(file.stream)
                img.verify()
                file.stream.seek(0)
            except Exception:
                return jsonify({"error": "Invalid or corrupted image file.", "status_code": 400}), 400

            ext = file.filename.rsplit(".", 1)[1].lower()
            image_filename = f"resolution_{complaint.id}_{uuid.uuid4().hex[:8]}.{ext}"
            upload_path = os.path.join(current_app.config["UPLOAD_FOLDER"], image_filename)
            file.save(upload_path)

    if not note and not image_filename:
        return jsonify({"error": "A resolution note or photo evidence is required.", "status_code": 400}), 400

    complaint.resolution_note = note if note else "Field resolution completed."
    if image_filename:
        complaint.resolution_image_path = image_filename
    complaint.resolution_submitted_at = datetime.now(timezone.utc)
    complaint.status = STATUS_RESOLUTION_SUBMITTED

    db.session.commit()

    # SSE Event Dispatches
    publish_complaint_event(
        complaint.id,
        EVENT_RESOLUTION_SUBMITTED,
        {
            "ticket_id": complaint.id,
            "status": complaint.status,
            "department": complaint.department,
            "resolution_note": complaint.resolution_note,
            "resolution_image_path": complaint.resolution_image_path,
            "resolution_submitted_at": complaint.resolution_submitted_at.isoformat() if complaint.resolution_submitted_at else None,
            "progress_message": f"Resolution evidence submitted by {complaint.department or 'Field Team'}.",
        },
        app=current_app._get_current_object(),
    )
    publish_complaint_event(
        complaint.id,
        EVENT_STATUS_CHANGED,
        {
            "status": complaint.status,
            "processing_status": complaint.processing_status,
            "stage": complaint.processing_status,
            "department": complaint.department,
            "severity": complaint.severity_level,
            "progress_message": "Resolution evidence submitted for citizen review.",
        },
        app=current_app._get_current_object(),
    )

    # In-app notification to citizen owner
    try:
        trigger_resolution_submitted_notification(
            complaint,
            resolution_note=complaint.resolution_note,
            app=current_app._get_current_object(),
        )
    except Exception as exc:
        current_app.logger.warning("Failed to trigger resolution notification: %s", exc)

    return jsonify({
        "message": "Resolution evidence submitted successfully.",
        "complaint": complaint.to_dict(),
        "status_code": 200
    }), 200


@complaints_bp.route("/<ticket_id>/resolution", methods=["GET"])
@login_required
def get_resolution(ticket_id):
    """
    Retrieves field resolution evidence for a complaint.
    Accessible by Admin or the Ticket Owner Citizen.
    """
    safe_id = str(ticket_id).strip()
    if not safe_id or len(safe_id) > 16:
        return jsonify({"error": "Invalid ticket ID format.", "status_code": 400}), 400

    complaint = db.session.get(Complaint, safe_id)
    if not complaint:
        return jsonify({"error": "Ticket not found.", "status_code": 404}), 404

    role = session.get("role")
    user_id = session.get("user_id")
    if role != "admin" and complaint.user_id != user_id:
        return jsonify({
            "error": "Access denied. You may only view resolution details for your own complaints.",
            "status_code": 403
        }), 403

    return jsonify({
        "ticket_id": complaint.id,
        "status": complaint.status,
        "department": complaint.department,
        "resolution_note": complaint.resolution_note,
        "resolution_image_path": complaint.resolution_image_path,
        "resolution_submitted_at": complaint.resolution_submitted_at.isoformat() if complaint.resolution_submitted_at else None,
        "resolved_at": complaint.resolved_at.isoformat() if complaint.resolved_at else None,
        "status_code": 200,
    }), 200


@complaints_bp.route("/<ticket_id>/feedback", methods=["POST"])
@login_required
def submit_feedback(ticket_id):
    """
    Submits citizen feedback on a complaint's resolution.
    Strictly restricted to the citizen owner of the complaint.
    Result must be either 'CONFIRMED' or 'NEEDS_ATTENTION'.
    """
    safe_id = str(ticket_id).strip()
    if not safe_id or len(safe_id) > 16:
        return jsonify({"error": "Invalid ticket ID format.", "status_code": 400}), 400

    complaint = db.session.get(Complaint, safe_id)
    if not complaint:
        return jsonify({"error": "Ticket not found.", "status_code": 404}), 404

    role = session.get("role")
    user_id = session.get("user_id")

    # Only ticket owner can submit citizen feedback (prevent unauthorized citizen input)
    if role != "admin" and complaint.user_id != user_id:
        return jsonify({
            "error": "Access denied. You may only submit feedback for your own complaints.",
            "status_code": 403
        }), 403

    # Complaint must be in RESOLUTION_SUBMITTED or RESOLVED state
    if complaint.status not in (STATUS_RESOLUTION_SUBMITTED, STATUS_RESOLVED):
        return jsonify({
            "error": f"Cannot submit feedback for ticket in status '{complaint.status}'. Ticket must be in RESOLUTION_SUBMITTED.",
            "status_code": 400
        }), 400

    # Parse feedback result and comment
    if request.is_json:
        result = (request.json.get("result") or "").strip().upper()
        comment = (request.json.get("comment") or "").strip()
    else:
        result = (request.form.get("result") or "").strip().upper()
        comment = (request.form.get("comment") or "").strip()

    if result not in ("CONFIRMED", "NEEDS_ATTENTION"):
        return jsonify({
            "error": "Invalid feedback result. Must be 'CONFIRMED' or 'NEEDS_ATTENTION'.",
            "status_code": 400
        }), 400

    # Accidental duplicate prevention: throttle identical result within 60s
    recent_cutoff = datetime.now(timezone.utc) - timedelta(seconds=60)
    existing_recent = CitizenFeedback.query.filter(
        CitizenFeedback.complaint_id == complaint.id,
        CitizenFeedback.user_id == user_id,
        CitizenFeedback.result == result,
        CitizenFeedback.created_at >= recent_cutoff
    ).first()
    if existing_recent:
        return jsonify({
            "error": "Feedback was already submitted within the last 60 seconds. Duplicate submission prevented.",
            "status_code": 409
        }), 409

    # Optional feedback evidence photo
    fb_image_filename = None
    if "image" in request.files:
        file = request.files["image"]
        if file and file.filename:
            if not allowed_file(file.filename):
                return jsonify({"error": "Unsupported file format for feedback image.", "status_code": 400}), 400
            try:
                img = Image.open(file.stream)
                img.verify()
                file.stream.seek(0)
            except Exception:
                return jsonify({"error": "Invalid or corrupted image file.", "status_code": 400}), 400
            ext = file.filename.rsplit(".", 1)[1].lower()
            fb_image_filename = f"feedback_{complaint.id}_{uuid.uuid4().hex[:8]}.{ext}"
            upload_path = os.path.join(current_app.config["UPLOAD_FOLDER"], fb_image_filename)
            file.save(upload_path)

    # Create CitizenFeedback entry
    fb = CitizenFeedback(
        complaint_id=complaint.id,
        user_id=user_id,
        result=result,
        comment=comment if comment else None,
        image_path=fb_image_filename,
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(fb)

    # State machine transition
    if result == "CONFIRMED":
        complaint.status = STATUS_RESOLVED
        complaint.resolved_at = datetime.now(timezone.utc)
        event_action = EVENT_RESOLUTION_CONFIRMED
        progress_msg = "Citizen confirmed resolution. Incident closed as RESOLVED."
    else:
        complaint.status = STATUS_IN_PROGRESS
        event_action = EVENT_RESOLUTION_NEEDS_ATTENTION
        progress_msg = "Citizen reported issue still needs attention. Returned to IN_PROGRESS."

    db.session.commit()

    fb_dict = fb.to_dict()

    # Real-time SSE dispatches
    publish_complaint_event(
        complaint.id,
        EVENT_CITIZEN_FEEDBACK,
        {
            "ticket_id": complaint.id,
            "result": result,
            "comment": comment,
            "status": complaint.status,
            "feedback": fb_dict,
            "progress_message": progress_msg,
        },
        app=current_app._get_current_object(),
    )
    publish_complaint_event(
        complaint.id,
        event_action,
        {
            "ticket_id": complaint.id,
            "result": result,
            "status": complaint.status,
            "progress_message": progress_msg,
        },
        app=current_app._get_current_object(),
    )
    publish_complaint_event(
        complaint.id,
        EVENT_STATUS_CHANGED,
        {
            "status": complaint.status,
            "processing_status": complaint.processing_status,
            "stage": complaint.processing_status,
            "department": complaint.department,
            "severity": complaint.severity_level,
            "progress_message": progress_msg,
        },
        app=current_app._get_current_object(),
    )

    # Trigger admin operational notification
    try:
        trigger_citizen_feedback_notification(complaint, fb, app=current_app._get_current_object())
    except Exception as exc:
        current_app.logger.warning("Failed to trigger feedback notification: %s", exc)

    return jsonify({
        "message": "Citizen feedback recorded successfully.",
        "feedback": fb_dict,
        "complaint": complaint.to_dict(),
        "status_code": 201,
    }), 201


@complaints_bp.route("/<ticket_id>/feedback", methods=["GET"])
@login_required
def get_feedback(ticket_id):
    """
    Retrieves feedback history for a complaint.
    Accessible by Admin or the Ticket Owner Citizen.
    """
    safe_id = str(ticket_id).strip()
    if not safe_id or len(safe_id) > 16:
        return jsonify({"error": "Invalid ticket ID format.", "status_code": 400}), 400

    complaint = db.session.get(Complaint, safe_id)
    if not complaint:
        return jsonify({"error": "Ticket not found.", "status_code": 404}), 404

    role = session.get("role")
    user_id = session.get("user_id")
    if role != "admin" and complaint.user_id != user_id:
        return jsonify({
            "error": "Access denied. You may only view feedback for your own complaints.",
            "status_code": 403
        }), 403

    feedbacks = (
        CitizenFeedback.query.filter_by(complaint_id=complaint.id)
        .order_by(CitizenFeedback.created_at.desc())
        .all()
    )
    return jsonify({
        "ticket_id": complaint.id,
        "feedback": [f.to_dict() for f in feedbacks],
        "total": len(feedbacks),
        "status_code": 200,
    }), 200


@complaints_bp.route("/<ticket_id>/events", methods=["GET"])
@login_required
def complaint_events(ticket_id):
    """
    Server-Sent Events endpoint streaming real-time status and stage updates for a complaint.
    Strictly role-protected: Citizens can only stream their own complaint.
    Admins may stream any complaint.
    """
    safe_id = str(ticket_id).strip()
    if not safe_id or len(safe_id) > 16:
        return jsonify({"error": "Invalid ticket ID format.", "status_code": 400}), 400

    complaint = db.session.get(Complaint, safe_id)
    if not complaint:
        return jsonify({"error": "Ticket not found.", "status_code": 404}), 404

    role = session.get("role")
    user_id = session.get("user_id")

    if role != "admin" and complaint.user_id != user_id:
        return jsonify({
            "error": "Access denied. You may only subscribe to events for your own complaints.",
            "status_code": 403
        }), 403

    response = Response(
        subscribe_complaint_events(
            ticket_id=complaint.id,
            app=current_app._get_current_object(),
            user_role=role,
        ),
        mimetype="text/event-stream"
    )
    response.headers["Cache-Control"] = "no-cache, no-transform"
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Connection"] = "keep-alive"
    return response


@complaints_bp.route("/admin/events", methods=["GET"])
@require_role("admin")
def admin_events():
    """
    Server-Sent Events stream for administrators broadcasting all municipal complaint updates.
    """
    response = Response(
        subscribe_admin_events(
            app=current_app._get_current_object(),
        ),
        mimetype="text/event-stream"
    )
    response.headers["Cache-Control"] = "no-cache, no-transform"
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Connection"] = "keep-alive"
    return response

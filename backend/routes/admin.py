from datetime import datetime, timedelta
import os
from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import func, text

from ai_config import CANONICAL_DEPARTMENT_MAP
from lifecycle import (
    STATUS_AI_PROCESSING,
    STATUS_ASSIGNED,
    STATUS_DUPLICATE,
    STATUS_IN_PROGRESS,
    STATUS_PROCESSING_FAILED,
    STATUS_REJECTED,
    STATUS_RESOLVED,
    STATUS_SUBMITTED,
    STATUS_VERIFIED,
)
from models import Complaint, db
from routes.auth import require_role

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@admin_bp.route("/overview", methods=["GET"])
@require_role("admin")
def admin_overview():
    """
    Municipal Operations Center Overview metrics.
    Aggregates lifecycle counts, urgent attention items, and recent activity from real database records.
    """
    total = Complaint.query.count()

    raw_status = dict(
        db.session.query(Complaint.status, func.count(Complaint.id))
        .group_by(Complaint.status).all()
    )
    raw_severity = dict(
        db.session.query(Complaint.severity_level, func.count(Complaint.id))
        .group_by(Complaint.severity_level).all()
    )

    counts = {
        "total": total,
        "submitted": raw_status.get(STATUS_SUBMITTED, 0),
        "ai_processing": raw_status.get(STATUS_AI_PROCESSING, 0),
        "verified": raw_status.get(STATUS_VERIFIED, 0),
        "assigned": raw_status.get(STATUS_ASSIGNED, 0),
        "in_progress": raw_status.get(STATUS_IN_PROGRESS, 0),
        "resolved": raw_status.get(STATUS_RESOLVED, 0),
        "processing_failed": raw_status.get(STATUS_PROCESSING_FAILED, 0),
        "duplicate": raw_status.get(STATUS_DUPLICATE, 0),
        "rejected": raw_status.get(STATUS_REJECTED, 0),
        "high_severity": raw_severity.get("High", 0),
    }

    # Urgent Attention items: High severity or failed or unassigned verified tickets
    urgent_query = Complaint.query.filter(
        (Complaint.severity_level == "High") |
        (Complaint.status == STATUS_PROCESSING_FAILED) |
        (Complaint.status == STATUS_VERIFIED)
    ).filter(
        ~Complaint.status.in_([STATUS_RESOLVED, "Resolved", "Closed", STATUS_REJECTED])
    ).order_by(
        Complaint.created_at.desc()
    ).limit(10).all()

    urgent_items = [c.to_dict(include_detections=False) for c in urgent_query]

    # Recent Activity items
    recent_query = Complaint.query.order_by(Complaint.created_at.desc()).limit(10).all()
    recent_activity = [c.to_dict(include_detections=False) for c in recent_query]

    return jsonify({
        "counts": counts,
        "urgent_items": urgent_items,
        "recent_activity": recent_activity,
        "status_code": 200,
    }), 200


@admin_bp.route("/departments", methods=["GET"])
@require_role("admin")
def department_metrics():
    """
    Department-focused operational metrics:
    Total, active, resolved, and high-severity counts per canonical department.
    """
    departments = list(dict.fromkeys(CANONICAL_DEPARTMENT_MAP.values()))

    metrics = []
    for dept in departments:
        q = Complaint.query.filter_by(department=dept)
        total = q.count()
        active = q.filter(
            ~Complaint.status.in_([STATUS_RESOLVED, "Resolved", "Closed", STATUS_REJECTED])
        ).count()
        resolved = q.filter(
            Complaint.status.in_([STATUS_RESOLVED, "Resolved", "Closed"])
        ).count()
        high_sev = q.filter_by(severity_level="High").count()

        metrics.append({
            "department": dept,
            "total": total,
            "active": active,
            "resolved": resolved,
            "high_severity": high_sev,
        })

    return jsonify({
        "departments": metrics,
        "status_code": 200,
    }), 200


@admin_bp.route("/analytics", methods=["GET"])
@require_role("admin")
def admin_analytics():
    """
    Comprehensive municipal analytics with configurable time range (?days=7, 30, 90).
    """
    raw_days = request.args.get("days", 7)
    try:
        days = max(1, min(365, int(raw_days)))
    except (ValueError, TypeError):
        days = 7

    cutoff = datetime.utcnow() - timedelta(days=days)
    query = Complaint.query.filter(Complaint.created_at >= cutoff)

    # 1. Timeline Trends (daily counts)
    date_labels = []
    date_counts = []
    for i in range(days - 1, -1, -1):
        day_start = (datetime.utcnow() - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        label = day_start.strftime("%b %d")
        c_count = Complaint.query.filter(Complaint.created_at >= day_start, Complaint.created_at < day_end).count()
        date_labels.append(label)
        date_counts.append(c_count)

    # 2. Breakdown by Severity
    raw_sev = dict(
        db.session.query(Complaint.severity_level, func.count(Complaint.id))
        .filter(Complaint.created_at >= cutoff)
        .group_by(Complaint.severity_level).all()
    )
    by_severity = {
        "High": raw_sev.get("High", 0),
        "Medium": raw_sev.get("Medium", 0),
        "Low": raw_sev.get("Low", 0),
    }

    # 3. Breakdown by Department
    raw_dept = dict(
        db.session.query(Complaint.department, func.count(Complaint.id))
        .filter(Complaint.created_at >= cutoff)
        .group_by(Complaint.department).all()
    )

    # 4. Breakdown by AI Execution Mode
    raw_ai = dict(
        db.session.query(Complaint.ai_mode, func.count(Complaint.id))
        .filter(Complaint.created_at >= cutoff)
        .group_by(Complaint.ai_mode).all()
    )
    by_ai_mode = {
        "REAL_YOLO": raw_ai.get("REAL_YOLO", 0),
        "MOCK_DEMO": raw_ai.get("MOCK_DEMO", 0),
    }

    # 5. Success vs Failure
    successful = query.filter(~Complaint.status.in_([STATUS_PROCESSING_FAILED, "FAILED"])).count()
    failed = query.filter(Complaint.status.in_([STATUS_PROCESSING_FAILED, "FAILED"])).count()

    return jsonify({
        "time_range_days": days,
        "timeline": {
            "labels": date_labels,
            "counts": date_counts,
        },
        "by_severity": by_severity,
        "by_department": raw_dept,
        "by_ai_mode": by_ai_mode,
        "processing_outcomes": {
            "success": successful,
            "failed": failed,
        },
        "total_in_period": query.count(),
        "status_code": 200,
    }), 200


@admin_bp.route("/system-health", methods=["GET"])
@require_role("admin")
def system_health():
    """
    System status inspection: Database, Redis, RQ Worker, AI mode, and YOLO model availability.
    """
    # 1. Database Check
    db_status = "Healthy"
    try:
        db.session.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"Unhealthy: {str(exc)}"

    # 2. Redis & Queue Check
    redis_status = "Unavailable (Running in Local Sync Fallback)"
    queue_size = 0
    try:
        import redis
        from rq import Queue
        redis_url = current_app.config.get("REDIS_URL", "redis://localhost:6379/0")
        r = redis.from_url(redis_url, socket_connect_timeout=1)
        r.ping()
        redis_status = "Healthy"
        try:
            q = Queue("complaints", connection=r)
            queue_size = len(q)
        except Exception:
            queue_size = 0
    except Exception:
        redis_status = "Unavailable (Running in Local Sync Fallback)"
        queue_size = 0

    # 3. AI Execution Mode & Model Status
    ai_mode = current_app.config.get("AI_EXECUTION_MODE", "MOCK_DEMO")
    weights_path = current_app.config.get("WASTE_MODEL_WEIGHTS", "best.pt")
    model_exists = os.path.exists(weights_path) if weights_path else False

    model_info = {
        "execution_mode": ai_mode,
        "weights_path": weights_path,
        "weights_file_present": model_exists,
        "active_ai_type": "Production YOLOv8 Inference" if ai_mode == "REAL_YOLO" and model_exists else "Mock Demonstration Mode",
    }

    # 4. Complaints Activity
    active_count = Complaint.query.filter(
        ~Complaint.status.in_([STATUS_RESOLVED, "Resolved", "Closed", STATUS_REJECTED])
    ).count()

    return jsonify({
        "status": "Healthy" if db_status == "Healthy" else "Degraded",
        "database": db_status,
        "redis": redis_status,
        "queue": {
            "size": queue_size,
            "mode": current_app.config.get("ASYNC_MODE", "redis"),
        },
        "ai": model_info,
        "active_complaints": active_count,
        "timestamp": datetime.utcnow().isoformat(),
        "status_code": 200,
    }), 200

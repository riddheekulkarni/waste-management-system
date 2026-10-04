from flask import Blueprint, jsonify
from sqlalchemy import func

from models import Complaint, db
from routes.auth import require_role

analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")


@analytics_bp.route("/summary", methods=["GET"])
@require_role("admin")
def summary():
    total = Complaint.query.count()

    raw_severity = dict(
        db.session.query(Complaint.severity_level, func.count(Complaint.id))
        .group_by(Complaint.severity_level).all()
    )
    raw_department = dict(
        db.session.query(Complaint.department, func.count(Complaint.id))
        .group_by(Complaint.department).all()
    )
    raw_status = dict(
        db.session.query(Complaint.status, func.count(Complaint.id))
        .group_by(Complaint.status).all()
    )
    raw_ai_mode = dict(
        db.session.query(Complaint.ai_mode, func.count(Complaint.id))
        .group_by(Complaint.ai_mode).all()
    )

    by_severity = {"Low": 0, "Medium": 0, "High": 0}
    by_severity.update({k: v for k, v in raw_severity.items() if k})

    by_status = {"Open": 0, "In Progress": 0, "Resolved": 0}
    by_status.update({k: v for k, v in raw_status.items() if k})

    by_department = {
        "Sanitation Department": 0,
        "Recycling Department": 0,
        "Health & Hazmat Department": 0,
        "Public Works Department": 0,
    }
    by_department.update({k: v for k, v in raw_department.items() if k})

    by_ai_mode = {"REAL_YOLO": 0, "MOCK_DEMO": 0}
    by_ai_mode.update({k: v for k, v in raw_ai_mode.items() if k})

    return jsonify({
        "total_complaints": total,
        "by_severity": by_severity,
        "by_department": by_department,
        "by_status": by_status,
        "by_ai_mode": by_ai_mode,
        "status_code": 200
    })


@analytics_bp.route("/geo", methods=["GET"])
@require_role("admin")
def geo_analytics():
    complaints = Complaint.query.filter(
        Complaint.latitude.isnot(None),
        Complaint.longitude.isnot(None)
    ).order_by(Complaint.created_at.desc()).limit(2000).all()

    points = [{
        "ticket_id": c.id,
        "latitude": c.latitude,
        "longitude": c.longitude,
        "severity": c.severity_level,
        "department": c.department,
        "status": c.status,
        "address": c.address,
        "is_duplicate": c.is_duplicate,
        "ai_mode": c.ai_mode or "MOCK_DEMO",
    } for c in complaints]

    return jsonify({"count": len(points), "points": points, "status_code": 200})

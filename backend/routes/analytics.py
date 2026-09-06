from flask import Blueprint, jsonify, session
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

    return jsonify({
        "total_complaints": total,
        "by_severity": by_severity,
        "by_department": by_department,
        "by_status": by_status,
    })


@analytics_bp.route("/geo", methods=["GET"])
@require_role("admin")
def geo_analytics():
    complaints = Complaint.query.filter(
        Complaint.latitude.isnot(None),
        Complaint.longitude.isnot(None)
    ).all()

    points = [{
        "ticket_id": c.id,
        "latitude": c.latitude,
        "longitude": c.longitude,
        "severity": c.severity_level,
        "department": c.department,
        "status": c.status,
        "address": c.address,
        "is_duplicate": c.is_duplicate,
    } for c in complaints]

    return jsonify({"count": len(points), "points": points})


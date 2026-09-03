from flask import Blueprint, jsonify, session
from sqlalchemy import func

from models import Complaint, db

analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")


@analytics_bp.route("/summary", methods=["GET"])
def summary():
    if session.get("role") != "admin":
        return jsonify({"error": "Admin access required."}), 403

    total = Complaint.query.count()

    by_severity = dict(
        db.session.query(Complaint.severity_level, func.count(Complaint.id))
        .group_by(Complaint.severity_level).all()
    )
    by_department = dict(
        db.session.query(Complaint.department, func.count(Complaint.id))
        .group_by(Complaint.department).all()
    )
    by_status = dict(
        db.session.query(Complaint.status, func.count(Complaint.id))
        .group_by(Complaint.status).all()
    )

    return jsonify({
        "total_complaints": total,
        "by_severity": by_severity,
        "by_department": by_department,
        "by_status": by_status,
    })

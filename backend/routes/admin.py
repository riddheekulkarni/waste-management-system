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

    # ── Phase 7 Civic Intelligence Enhancements ─────────────────────────────
    from models import Notification
    now = datetime.utcnow()
    unassigned_12h = now - timedelta(hours=12)

    aging_unassigned_count = Complaint.query.filter(
        Complaint.status.in_(["SUBMITTED", "VERIFIED", "Open"]),
        Complaint.department.in_([None, "", "PENDING_TRIAGE"]),
        Complaint.created_at <= unassigned_12h,
    ).count()

    unread_operational_alerts = Notification.query.filter(
        Notification.user_id.is_(None),
        Notification.is_read.is_(False)
    ).count()

    # Active incidents
    active_incidents = Complaint.query.filter(
        ~Complaint.status.in_([STATUS_RESOLVED, "Resolved", "Closed", STATUS_REJECTED])
    ).all()
    active_high_severity = sum(1 for c in active_incidents if c.severity_level == "High")

    # Spatial summary: bucketed cells
    geolocated = [c for c in active_incidents if c.latitude is not None and c.longitude is not None]
    cells = {}
    for c in geolocated:
        b = (round(c.latitude, 2), round(c.longitude, 2))
        cells[b] = cells.get(b, 0) + 1
    top_cells = sorted([{"cell": {"lat": k[0], "lng": k[1]}, "count": v} for k, v in cells.items()], key=lambda x: x["count"], reverse=True)[:3]

    # Department distribution among active
    dept_counts = {}
    for c in active_incidents:
        dept = c.department or "PENDING_TRIAGE"
        dept_counts[dept] = dept_counts.get(dept, 0) + 1
    most_affected_depts = sorted([{"department": k, "count": v} for k, v in dept_counts.items()], key=lambda x: x["count"], reverse=True)[:3]

    civic_intelligence_summary = {
        "active_incident_count": len(active_incidents),
        "high_severity_active_count": active_high_severity,
        "aging_unassigned_count": aging_unassigned_count,
        "ai_failure_count": counts.get("processing_failed", 0),
        "unread_operational_alerts": unread_operational_alerts,
    }

    spatial_summary = {
        "top_incident_concentration_areas": top_cells,
        "most_affected_departments": most_affected_depts,
        "total_active_geolocated": len(geolocated),
    }

    recent_insights = [
        f"Active workload stands at {len(active_incidents)} unresolved reports ({active_high_severity} high-severity).",
        f"Department '{most_affected_depts[0]['department']}' has highest pending queue ({most_affected_depts[0]['count']} incidents)." if most_affected_depts else "Workload evenly distributed.",
        f"{unread_operational_alerts} unread operational alerts require attention." if unread_operational_alerts > 0 else "All operational alerts acknowledged.",
    ]

    return jsonify({
        "counts": counts,
        "urgent_items": urgent_items,
        "recent_activity": recent_activity,
        "civic_intelligence_summary": civic_intelligence_summary,
        "spatial_summary": spatial_summary,
        "recent_insights": recent_insights,
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


# ===========================================================================
# PHASE 7 — LIVE CIVIC INTELLIGENCE LAYER ENDPOINTS
# ===========================================================================

def _build_map_query(args):
    """Helper to apply server-side geospatial and operational filters."""
    query = Complaint.query.filter(
        Complaint.latitude.isnot(None),
        Complaint.longitude.isnot(None)
    )

    # 1. Date window filter
    raw_days = args.get("days")
    if raw_days:
        try:
            days = max(1, min(365, int(raw_days)))
            cutoff = datetime.utcnow() - timedelta(days=days)
            query = query.filter(Complaint.created_at >= cutoff)
        except (ValueError, TypeError):
            pass

    # 2. Severity filter
    sev = args.get("severity")
    if sev and sev in ("High", "Medium", "Low"):
        query = query.filter(Complaint.severity_level == sev)

    # 3. Status filter
    st = args.get("status")
    if st:
        query = query.filter(Complaint.status == st)

    # 4. Department filter
    dept = args.get("department")
    if dept:
        query = query.filter(Complaint.department == dept)

    # 5. AI mode filter
    mode = args.get("ai_mode")
    if mode in ("REAL_YOLO", "MOCK_DEMO"):
        query = query.filter(Complaint.ai_mode == mode)

    # 6. Waste category filter (joining detection items)
    cat = args.get("category")
    if cat:
        from models import DetectionItem
        query = query.join(Complaint.detections).filter(DetectionItem.cls == cat)

    return query


@admin_bp.route("/map", methods=["GET"])
@require_role("admin")
def admin_map_incidents():
    """
    Live Civic Intelligence Map: Query geolocated complaint incidents with multi-filtering.
    Supports server-side filtering by days, severity, status, department, ai_mode, and waste category.
    """
    query = _build_map_query(request.args)
    complaints = query.order_by(Complaint.created_at.desc()).limit(1000).all()

    points = []
    for c in complaints:
        cats = sorted(list(set(d.cls for d in c.detections if d.cls))) if c.detections else []
        points.append({
            "ticket_id": c.id,
            "latitude": c.latitude,
            "longitude": c.longitude,
            "severity": c.severity_level or "PENDING",
            "department": c.department or "PENDING_TRIAGE",
            "status": c.status,
            "address": c.address or "Street Pin",
            "ai_mode": c.ai_mode or "MOCK_DEMO",
            "processing_status": c.processing_status or "QUEUED",
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "categories": cats,
            "item_count": c.item_count or 0,
            "coverage_ratio": round(c.coverage_ratio, 4) if c.coverage_ratio is not None else 0.0,
            "is_duplicate": bool(c.is_duplicate),
            "duplicate_of_id": c.duplicate_of_id,
        })

    return jsonify({
        "count": len(points),
        "points": points,
        "status_code": 200,
    }), 200


@admin_bp.route("/map/aggregate", methods=["GET"])
@admin_bp.route("/geospatial/aggregate", methods=["GET"])
@require_role("admin")
def admin_map_aggregate():
    """
    Geospatial Aggregation: Aggregate observed incidents into geographic cells (Incident Concentration).
    No PostGIS requirement: uses lightweight coordinate bucketing.
    """
    raw_step = request.args.get("cell_size", "0.01")
    try:
        step = max(0.001, min(0.1, float(raw_step)))
    except (ValueError, TypeError):
        step = 0.01

    query = _build_map_query(request.args)
    complaints = query.all()

    cells_map = {}
    for c in complaints:
        lat_bucket = round(round(c.latitude / step) * step, 4)
        lng_bucket = round(round(c.longitude / step) * step, 4)
        key = (lat_bucket, lng_bucket)

        if key not in cells_map:
            cells_map[key] = {
                "cell": {"lat": lat_bucket, "lng": lng_bucket},
                "incident_count": 0,
                "high_severity": 0,
                "resolved": 0,
                "active": 0,
                "departments": {},
                "categories": {},
                "sample_tickets": [],
            }

        cell_data = cells_map[key]
        cell_data["incident_count"] += 1
        if c.severity_level == "High":
            cell_data["high_severity"] += 1

        is_resolved = c.status in (STATUS_RESOLVED, "Resolved", "Closed")
        if is_resolved:
            cell_data["resolved"] += 1
        else:
            cell_data["active"] += 1

        dept = c.department or "PENDING_TRIAGE"
        cell_data["departments"][dept] = cell_data["departments"].get(dept, 0) + 1

        if c.detections:
            for d in c.detections:
                if d.cls:
                    cell_data["categories"][d.cls] = cell_data["categories"].get(d.cls, 0) + 1

        if len(cell_data["sample_tickets"]) < 3:
            cell_data["sample_tickets"].append(c.id)

    sorted_cells = sorted(cells_map.values(), key=lambda x: x["incident_count"], reverse=True)

    return jsonify({
        "cell_size_deg": step,
        "total_cells": len(sorted_cells),
        "total_incidents": len(complaints),
        "cells": sorted_cells,
        "layer_label": "Historical Incident Density",
        "status_code": 200,
    }), 200


@admin_bp.route("/geospatial", methods=["GET"])
@require_role("admin")
def admin_geospatial_summary():
    """
    High-level geospatial intelligence summary:
    Concentration hotspots, bounding box, and recurring report concentration areas.
    """
    geolocated = Complaint.query.filter(
        Complaint.latitude.isnot(None),
        Complaint.longitude.isnot(None)
    ).all()
    unlocated_count = Complaint.query.filter(
        (Complaint.latitude.is_(None)) | (Complaint.longitude.is_(None))
    ).count()

    # Recurring report clusters (haversine <= 50m, >= 2 reports)
    clusters = []
    visited = set()

    for i, c1 in enumerate(geolocated):
        if c1.id in visited:
            continue
        group = [c1]
        for c2 in geolocated[i+1:]:
            if c2.id in visited:
                continue
            dist = Complaint.haversine_distance(c1.latitude, c1.longitude, c2.latitude, c2.longitude)
            if dist <= 50.0:
                group.append(c2)

        if len(group) >= 2:
            for item in group:
                visited.add(item.id)
            avg_lat = sum(g.latitude for g in group) / len(group)
            avg_lng = sum(g.longitude for g in group) / len(group)
            clusters.append({
                "center": {"lat": round(avg_lat, 5), "lng": round(avg_lng, 5)},
                "address": group[0].address or "Repeated Incident Area",
                "report_count": len(group),
                "ticket_ids": [g.id for g in group],
                "active_count": sum(1 for g in group if g.status not in (STATUS_RESOLVED, "Resolved", "Closed")),
                "resolved_count": sum(1 for g in group if g.status in (STATUS_RESOLVED, "Resolved", "Closed")),
                "departments": list(set(g.department for g in group if g.department)),
                "label": "Recurring Report Concentration",
            })

    clusters.sort(key=lambda x: x["report_count"], reverse=True)

    return jsonify({
        "total_geolocated": len(geolocated),
        "total_unlocated": unlocated_count,
        "recurring_areas": clusters[:10],
        "status_code": 200,
    }), 200


@admin_bp.route("/insights", methods=["GET"])
@require_role("admin")
def admin_operational_insights():
    """
    Descriptive, evidence-based Municipal Operational Insights.
    Calculates workload, AI operations, civic trends (vs previous period),
    resolution performance milestones, and operational age monitoring.
    """
    raw_days = request.args.get("days", 7)
    try:
        days = max(1, min(365, int(raw_days)))
    except (ValueError, TypeError):
        days = 7

    now = datetime.utcnow()
    current_cutoff = now - timedelta(days=days)
    prev_cutoff = now - timedelta(days=2 * days)

    # Current vs Previous Period queries
    curr_complaints = Complaint.query.filter(Complaint.created_at >= current_cutoff).all()
    prev_complaints = Complaint.query.filter(
        Complaint.created_at >= prev_cutoff,
        Complaint.created_at < current_cutoff
    ).all()

    # 1. Workload Insights
    all_active = Complaint.query.filter(
        ~Complaint.status.in_([STATUS_RESOLVED, "Resolved", "Closed", STATUS_REJECTED])
    ).all()
    high_sev_unresolved = [c for c in all_active if c.severity_level == "High"]

    dept_active_counts = {}
    for c in all_active:
        dept = c.department or "PENDING_TRIAGE"
        dept_active_counts[dept] = dept_active_counts.get(dept, 0) + 1

    highest_workload_dept = max(dept_active_counts.items(), key=lambda x: x[1]) if dept_active_counts else ("None", 0)

    # 2. Operational Age Threshold Monitoring
    unassigned_12h_cutoff = now - timedelta(hours=12)
    high_sev_6h_cutoff = now - timedelta(hours=6)
    new_24h_cutoff = now - timedelta(hours=24)

    aging_unassigned = [
        c.id for c in all_active
        if (c.status in ("SUBMITTED", "VERIFIED", "Open") and (not c.department or c.department == "PENDING_TRIAGE") and c.created_at and c.created_at <= unassigned_12h_cutoff)
    ]
    aging_high_severity = [
        c.id for c in high_sev_unresolved
        if c.created_at and c.created_at <= high_sev_6h_cutoff
    ]
    aging_new_reports = [
        c.id for c in all_active
        if c.created_at and c.created_at <= new_24h_cutoff
    ]

    age_monitoring = {
        "label": "Operational Age Threshold",
        "thresholds": {
            "unassigned_hours": 12,
            "high_severity_hours": 6,
            "new_report_hours": 24,
        },
        "aging_unassigned_count": len(aging_unassigned),
        "aging_unassigned_tickets": aging_unassigned[:5],
        "aging_high_severity_count": len(aging_high_severity),
        "aging_high_severity_tickets": aging_high_severity[:5],
        "aging_new_reports_count": len(aging_new_reports),
    }

    # 3. Resolution Performance Milestones
    # Milestone 1: SUBMITTED -> VERIFIED duration
    verified_durations_min = []
    for c in curr_complaints:
        if c.processing_completed_at and c.created_at and c.processing_completed_at >= c.created_at:
            dur_min = (c.processing_completed_at - c.created_at).total_seconds() / 60.0
            verified_durations_min.append(dur_min)

    if verified_durations_min:
        avg_v = sum(verified_durations_min) / len(verified_durations_min)
        verified_durations_min.sort()
        med_v = verified_durations_min[len(verified_durations_min) // 2]
        perf_submitted_verified = {
            "average_minutes": round(avg_v, 2),
            "median_minutes": round(med_v, 2),
            "completed_cases": len(verified_durations_min),
            "status": "Available",
        }
    else:
        perf_submitted_verified = {
            "average_minutes": None,
            "median_minutes": None,
            "completed_cases": 0,
            "status": "Insufficient data",
        }

    # 4. AI Operations
    processed_in_period = [c for c in curr_complaints if c.processing_status in ("COMPLETED", "FAILED")]
    failed_in_period = [c for c in curr_complaints if c.processing_status == "FAILED" or c.status == STATUS_PROCESSING_FAILED]
    success_rate = (
        round(((len(processed_in_period) - len(failed_in_period)) / len(processed_in_period)) * 100, 1)
        if processed_in_period else None
    )
    total_retries = sum(c.retry_count for c in curr_complaints if c.retry_count)
    real_yolo_count = sum(1 for c in curr_complaints if c.ai_mode == "REAL_YOLO")
    mock_demo_count = sum(1 for c in curr_complaints if c.ai_mode != "REAL_YOLO")

    # 5. Civic Trends (Period vs Previous Equivalent Period)
    curr_vol = len(curr_complaints)
    prev_vol = len(prev_complaints)
    vol_delta_pct = round(((curr_vol - prev_vol) / prev_vol) * 100, 1) if prev_vol > 0 else (100.0 if curr_vol > 0 else 0.0)

    curr_high = sum(1 for c in curr_complaints if c.severity_level == "High")
    prev_high = sum(1 for c in prev_complaints if c.severity_level == "High")
    high_delta_pct = round(((curr_high - prev_high) / prev_high) * 100, 1) if prev_high > 0 else (100.0 if curr_high > 0 else 0.0)

    curr_res = sum(1 for c in curr_complaints if c.status in (STATUS_RESOLVED, "Resolved", "Closed"))
    prev_res = sum(1 for c in prev_complaints if c.status in (STATUS_RESOLVED, "Resolved", "Closed"))
    res_delta_pct = round(((curr_res - prev_res) / prev_res) * 100, 1) if prev_res > 0 else (100.0 if curr_res > 0 else 0.0)

    curr_res_rate = round((curr_res / curr_vol) * 100, 1) if curr_vol > 0 else 0.0
    prev_res_rate = round((prev_res / prev_vol) * 100, 1) if prev_vol > 0 else 0.0
    rate_delta_pct = round(curr_res_rate - prev_res_rate, 1)

    trends_data = {
        "volume": {"current": curr_vol, "previous": prev_vol, "delta_pct": vol_delta_pct},
        "incident_volume": {"current": curr_vol, "previous": prev_vol, "delta_pct": vol_delta_pct},
        "high_severity": {"current": curr_high, "previous": prev_high, "delta_pct": high_delta_pct},
        "resolved": {"current": curr_res, "previous": prev_res, "delta_pct": res_delta_pct},
        "resolution_rate": {
            "current": curr_res_rate,
            "previous": prev_res_rate,
            "delta_pct": rate_delta_pct,
            "current_pct": curr_res_rate,
            "previous_pct": prev_res_rate,
        },
    }

    # 6. Recurring Report Concentrations (Spatial clusters <= 50m)
    geolocated = [c for c in curr_complaints if c.latitude is not None and c.longitude is not None]
    visited = set()
    clusters = []
    for i, c1 in enumerate(geolocated):
        if c1.id in visited:
            continue
        members = [c1]
        visited.add(c1.id)
        for j, c2 in enumerate(geolocated):
            if c2.id in visited:
                continue
            dist = Complaint.haversine_distance(c1.latitude, c1.longitude, c2.latitude, c2.longitude)
            if dist <= 50.0:
                members.append(c2)
                visited.add(c2.id)

        if len(members) >= 2:
            depts = sorted(list(set(m.department for m in members if m.department)))
            act_cnt = sum(1 for m in members if m.status not in (STATUS_RESOLVED, "Resolved", "Closed"))
            res_cnt = len(members) - act_cnt
            clusters.append({
                "area_label": f"Cluster near {members[0].address or 'Reported Area'}",
                "lat": members[0].latitude,
                "lng": members[0].longitude,
                "report_count": len(members),
                "active": act_cnt,
                "resolved": res_cnt,
                "departments": depts,
            })
    clusters.sort(key=lambda x: x["report_count"], reverse=True)

    perf_submitted_verified_extended = {
        **perf_submitted_verified,
        "avg_formatted": f"{perf_submitted_verified['average_minutes']} min" if perf_submitted_verified["average_minutes"] is not None else "Insufficient data",
        "median_formatted": f"{perf_submitted_verified['median_minutes']} min" if perf_submitted_verified["median_minutes"] is not None else "Insufficient data",
        "cases_count": perf_submitted_verified["completed_cases"],
    }

    return jsonify({
        "time_range_days": days,
        "workload": {
            "unresolved_reports": len(all_active),
            "high_severity_unresolved": len(high_sev_unresolved),
            "highest_active_department": highest_workload_dept[0],
            "highest_department_active_count": highest_workload_dept[1],
            "unassigned_beyond_threshold": len(aging_unassigned),
            "high_severity_active_beyond_threshold": len(aging_high_severity),
            "active_beyond_threshold": len(aging_new_reports),
        },
        "age_monitoring": age_monitoring,
        "resolution_performance": {
            "submitted_to_verified": perf_submitted_verified_extended,
            "overall_resolution_rate_pct": curr_res_rate,
        },
        "ai_operations": {
            "success_rate_pct": success_rate,
            "failed_count": len(failed_in_period),
            "failed": len(failed_in_period),
            "retry_count": total_retries,
            "retries": total_retries,
            "real_yolo_usage": real_yolo_count,
            "mock_demo_usage": mock_demo_count,
        },
        "civic_trends": trends_data,
        "trends": trends_data,
        "repeated_incidents": {
            "label": "Recurring Report Concentration",
            "concentrations": clusters,
            "total_concentrations": len(clusters),
        },
        "status_code": 200,
    }), 200


# ---------------------------------------------------------------------------
# Administrative Notification Center Endpoints
# ---------------------------------------------------------------------------

@admin_bp.route("/notifications", methods=["GET"])
@require_role("admin")
def admin_notifications_list():
    """
    Admin Notification Center: Retrieve operational alerts and unread counts.
    Evaluates operational age rules dynamically to surface any newly aging tickets.
    """
    from notifications import get_admin_notifications, evaluate_aging_report_rules
    # Evaluate aging rules defensively
    try:
        evaluate_aging_report_rules(app=current_app._get_current_object())
    except Exception as exc:
        pass

    cat = request.args.get("category")
    unread_only = request.args.get("unread_only", "").lower() in ("true", "1", "yes")
    limit = min(100, max(1, int(request.args.get("limit", 50))))

    data = get_admin_notifications(category=cat, unread_only=unread_only, limit=limit)
    return jsonify({
        **data,
        "status_code": 200,
    }), 200


@admin_bp.route("/notifications/<int:notification_id>/read", methods=["PATCH"])
@require_role("admin")
def admin_notification_mark_read(notification_id):
    """
    Mark an administrative operational alert as read.
    """
    from notifications import mark_notification_read
    from models import Notification

    notif = mark_notification_read(notification_id, user_id=None)
    if not notif:
        return jsonify({"error": "Notification not found.", "status_code": 404}), 404

    unread_count = Notification.query.filter(
        Notification.user_id.is_(None),
        Notification.is_read.is_(False)
    ).count()

    return jsonify({
        "notification": notif.to_dict(),
        "unread_count": unread_count,
        "status_code": 200,
    }), 200


@admin_bp.route("/notifications/read-all", methods=["POST"])
@require_role("admin")
def admin_notifications_read_all():
    """
    Mark all administrative operational alerts as read.
    """
    from notifications import mark_all_notifications_read
    marked = mark_all_notifications_read(user_id=None)
    return jsonify({
        "marked_read": marked,
        "unread_count": 0,
        "status_code": 200,
    }), 200


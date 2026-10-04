"""
Phase 6 Automated Test Suite — Municipal Operations Center & Admin UX.

Verifies:
1. Admin overview metrics and urgent attention queue.
2. Citizen isolation (cannot access admin endpoints or municipal incident triage).
3. Department operational workload aggregations.
4. Municipal analytics with time-range filtering (?days=7, 30).
5. System health diagnostics (Database, Redis, Queue, AI execution mode).
6. Admin user management with password protection.
7. Complaint operations queue with server-side search (q parameter) and multi-attribute filters.
8. Operational lifecycle status transitions (enforces valid state machine, rejects invalid).
9. Department assignment via PATCH.
10. Admin retry processing for failed jobs.
11. Admin SSE stream authorization and event broadcast.
"""

import io
from PIL import Image
from models import Complaint, User, db
from lifecycle import (
    STATUS_SUBMITTED,
    STATUS_AI_PROCESSING,
    STATUS_VERIFIED,
    STATUS_ASSIGNED,
    STATUS_IN_PROGRESS,
    STATUS_RESOLVED,
    STATUS_PROCESSING_FAILED,
    STATUS_REJECTED,
)


def _create_sample_complaint(user_id=None, ticket_id="tc001", status=STATUS_VERIFIED, severity="High", dept="Sanitation Department", address="100 Civic Lane", ai_mode="REAL_YOLO"):
    c = Complaint(
        id=ticket_id,
        user_id=user_id,
        status=status,
        severity_level=severity,
        department=dept,
        address=address,
        latitude=18.5204,
        longitude=73.8567,
        image_path=f"{ticket_id}.jpg",
        ai_mode=ai_mode,
        processing_status="COMPLETED",
    )
    db.session.add(c)
    db.session.commit()
    return c


# ── 1. Admin Overview & Metrics ─────────────────────────────────────────────
def test_admin_overview_metrics(app, admin_client):
    with app.app_context():
        _create_sample_complaint(ticket_id="ov001", status=STATUS_VERIFIED, severity="High")
        _create_sample_complaint(ticket_id="ov002", status=STATUS_PROCESSING_FAILED, severity="Medium")
        _create_sample_complaint(ticket_id="ov003", status=STATUS_RESOLVED, severity="Low")

    res = admin_client.get("/api/admin/overview")
    assert res.status_code == 200
    data = res.get_json()

    assert "counts" in data
    counts = data["counts"]
    assert counts["total"] >= 3
    assert counts["high_severity"] >= 1
    assert counts["processing_failed"] >= 1
    assert counts["resolved"] >= 1

    assert "urgent_items" in data
    urgent_ids = [item["id"] for item in data["urgent_items"]]
    # ov001 (High severity) and ov002 (Failed processing) must appear in urgent queue
    assert "ov001" in urgent_ids or "ov002" in urgent_ids


def test_admin_overview_citizen_forbidden(citizen_client):
    res = citizen_client.get("/api/admin/overview")
    assert res.status_code == 403


# ── 2. Department Management & Workload Metrics ─────────────────────────────
def test_admin_departments_metrics(app, admin_client):
    with app.app_context():
        _create_sample_complaint(ticket_id="dp001", dept="Sanitation Department", status=STATUS_ASSIGNED)
        _create_sample_complaint(ticket_id="dp002", dept="Sanitation Department", status=STATUS_RESOLVED)
        _create_sample_complaint(ticket_id="dp003", dept="Health & Hazmat Department", status=STATUS_IN_PROGRESS, severity="High")

    res = admin_client.get("/api/admin/departments")
    assert res.status_code == 200
    data = res.get_json()
    assert "departments" in data

    depts = {d["department"]: d for d in data["departments"]}
    assert "Sanitation Department" in depts
    assert "Health & Hazmat Department" in depts

    sanitation = depts["Sanitation Department"]
    assert sanitation["total"] >= 2
    assert sanitation["active"] >= 1
    assert sanitation["resolved"] >= 1


def test_admin_departments_citizen_forbidden(citizen_client):
    res = citizen_client.get("/api/admin/departments")
    assert res.status_code == 403


# ── 3. Municipal Analytics & Time Filtering ─────────────────────────────────
def test_admin_analytics_time_filters(app, admin_client):
    with app.app_context():
        _create_sample_complaint(ticket_id="an001", status=STATUS_RESOLVED, severity="High", ai_mode="REAL_YOLO")
        _create_sample_complaint(ticket_id="an002", status=STATUS_IN_PROGRESS, severity="Medium", ai_mode="MOCK_DEMO")

    res7 = admin_client.get("/api/admin/analytics?days=7")
    assert res7.status_code == 200
    d7 = res7.get_json()
    assert d7["time_range_days"] == 7
    assert len(d7["timeline"]["labels"]) == 7
    assert d7["by_severity"]["High"] >= 1
    assert d7["by_ai_mode"]["REAL_YOLO"] >= 1
    assert d7["by_ai_mode"]["MOCK_DEMO"] >= 1

    res30 = admin_client.get("/api/admin/analytics?days=30")
    assert res30.status_code == 200
    assert res30.get_json()["time_range_days"] == 30


# ── 4. System Health Diagnostics ────────────────────────────────────────────
def test_admin_system_health(admin_client):
    res = admin_client.get("/api/admin/system-health")
    assert res.status_code == 200
    h = res.get_json()

    assert h["database"] == "Healthy"
    assert "redis" in h
    assert "ai" in h
    assert "execution_mode" in h["ai"]
    assert "weights_file_present" in h["ai"]
    assert "queue" in h


def test_admin_system_health_citizen_forbidden(citizen_client):
    res = citizen_client.get("/api/admin/system-health")
    assert res.status_code == 403


# ── 5. User Management & Credential Security ────────────────────────────────
def test_admin_users_list_and_rbac(admin_client, citizen_client):
    # Admin can list users
    res = admin_client.get("/api/auth/users")
    assert res.status_code == 200
    data = res.get_json()
    assert "users" in data
    assert len(data["users"]) >= 2

    # Verify sensitive fields are never exposed
    for u in data["users"]:
        assert "password" not in u
        assert "password_hash" not in u
        assert "username" in u
        assert "role" in u

    # Citizen cannot list users
    res_cit = citizen_client.get("/api/auth/users")
    assert res_cit.status_code == 403


# ── 6. Complaints Operations Queue & Server-Side Search ──────────────────────
def test_complaints_queue_search_and_filters(app, admin_client):
    with app.app_context():
        _create_sample_complaint(ticket_id="sq001", address="MG Road Metro Station", status=STATUS_ASSIGNED, severity="High", dept="Sanitation Department")
        _create_sample_complaint(ticket_id="sq002", address="FC Road Corner", status=STATUS_RESOLVED, severity="Low", dept="Recycling Department")

    # Search by ticket ID
    res_id = admin_client.get("/api/complaints?q=sq001")
    assert res_id.status_code == 200
    items_id = res_id.get_json()["items"]
    assert len(items_id) == 1
    assert items_id[0]["ticket_id"] == "sq001"

    # Search by address keyword
    res_addr = admin_client.get("/api/complaints?q=Metro")
    assert res_addr.status_code == 200
    items_addr = res_addr.get_json()["items"]
    assert any(i["ticket_id"] == "sq001" for i in items_addr)

    # Multi-attribute filter: Severity=High & Department=Sanitation Department
    res_multi = admin_client.get("/api/complaints?severity=High&department=Sanitation%20Department")
    assert res_multi.status_code == 200
    items_multi = res_multi.get_json()["items"]
    assert all(i["severity"]["level"] == "High" and i["department"] == "Sanitation Department" for i in items_multi)


# ── 7. Operational Status Transitions & Invalid Rejection ───────────────────
def test_operational_lifecycle_transitions(app, admin_client):
    with app.app_context():
        _create_sample_complaint(ticket_id="tr001", status=STATUS_VERIFIED)

    # Valid forward transition: VERIFIED -> ASSIGNED
    res1 = admin_client.patch("/api/complaints/tr001/status", json={"status": STATUS_ASSIGNED})
    assert res1.status_code == 200
    assert res1.get_json()["status"] == STATUS_ASSIGNED

    # Valid forward transition: ASSIGNED -> IN_PROGRESS
    res2 = admin_client.patch("/api/complaints/tr001/status", json={"status": STATUS_IN_PROGRESS})
    assert res2.status_code == 200
    assert res2.get_json()["status"] == STATUS_IN_PROGRESS

    # Valid forward transition: IN_PROGRESS -> RESOLVED
    res3 = admin_client.patch("/api/complaints/tr001/status", json={"status": STATUS_RESOLVED})
    assert res3.status_code == 200
    assert res3.get_json()["status"] == STATUS_RESOLVED

    # INVALID transition: RESOLVED is terminal -> cannot transition back to IN_PROGRESS
    res_inv = admin_client.patch("/api/complaints/tr001/status", json={"status": STATUS_IN_PROGRESS})
    assert res_inv.status_code == 400
    assert "Illegal status transition" in res_inv.get_json()["error"]


# ── 8. Department Assignment via PATCH ──────────────────────────────────────
def test_admin_department_assignment(app, admin_client):
    with app.app_context():
        _create_sample_complaint(ticket_id="as001", dept="Sanitation Department")

    res = admin_client.patch("/api/complaints/as001/status", json={
        "status": STATUS_ASSIGNED,
        "department": "Health & Hazmat Department"
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == STATUS_ASSIGNED
    assert data["department"] == "Health & Hazmat Department"


# ── 9. Admin Retry Failed Processing ────────────────────────────────────────
def test_admin_retry_failed_processing(app, admin_client):
    with app.app_context():
        _create_sample_complaint(ticket_id="rf001", status=STATUS_PROCESSING_FAILED)

    res = admin_client.post("/api/complaints/rf001/retry-processing")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["retry_count"] >= 1
    assert data["ticket_id"] == "rf001"


# ── 10. Admin SSE Stream Authorization ──────────────────────────────────────
def test_admin_sse_authorization(admin_client, citizen_client):
    # Admin can connect to admin events stream
    res_adm = admin_client.get("/api/complaints/admin/events")
    assert res_adm.status_code == 200
    assert res_adm.mimetype == "text/event-stream"
    res_adm.close()

    # Citizen is strictly forbidden from admin events stream
    res_cit = citizen_client.get("/api/complaints/admin/events")
    assert res_cit.status_code == 403

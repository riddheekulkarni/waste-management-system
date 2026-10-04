import json
from datetime import datetime, timedelta, timezone
import pytest
from models import Complaint, DetectionItem, Notification, User, db
from notifications import (
    CATEGORY_AI_PROCESSING_FAILED,
    CATEGORY_DUPLICATE_DETECTED,
    CATEGORY_NEW_HIGH_SEVERITY,
    CATEGORY_STATUS_CHANGED,
    CATEGORY_UNASSIGNED_REPORT,
    create_notification,
    evaluate_aging_report_rules,
    get_admin_notifications,
    get_user_notifications,
    mark_all_notifications_read,
    mark_notification_read,
    trigger_ai_failure_rule,
    trigger_duplicate_rule,
    trigger_high_severity_rule,
)


def login(client, identifier, password):
    return client.post("/api/auth/login", json={"identifier": identifier, "password": password})


# ── Pillar 1 & 2: Geospatial & Map Tests ────────────────────────────────────

def test_admin_map_empty_and_unlocated_handling(app, admin_client):
    with app.app_context():
        # Create one complaint with no coordinates
        c = Complaint(
            id="noloc001",
            status="SUBMITTED",
            severity_level="Low",
            department="Sanitation Department",
            latitude=None,
            longitude=None,
        )
        db.session.add(c)
        db.session.commit()

    res = admin_client.get("/api/admin/map")
    assert res.status_code == 200
    data = res.get_json()
    assert data["count"] == 0
    assert len(data["points"]) == 0


def test_admin_map_points_and_server_side_filtering(app, admin_client):
    with app.app_context():
        c1 = Complaint(
            id="map0001",
            latitude=18.5204,
            longitude=73.8567,
            severity_level="High",
            status="VERIFIED",
            department="Sanitation Department",
            ai_mode="REAL_YOLO",
        )
        c2 = Complaint(
            id="map0002",
            latitude=18.5210,
            longitude=73.8570,
            severity_level="Low",
            status="RESOLVED",
            department="Recycling Department",
            ai_mode="MOCK_DEMO",
        )
        c3 = Complaint(
            id="map0003",
            latitude=18.5300,
            longitude=73.8600,
            severity_level="High",
            status="IN_PROGRESS",
            department="Recycling Department",
            ai_mode="REAL_YOLO",
        )
        db.session.add_all([c1, c2, c3])

        # Add detection items for waste category filtering
        d1 = DetectionItem(complaint_id="map0001", cls="plastic_bottle", confidence=0.88)
        d2 = DetectionItem(complaint_id="map0002", cls="organic_waste", confidence=0.92)
        db.session.add_all([d1, d2])
        db.session.commit()

    # 1. Fetch all
    res = admin_client.get("/api/admin/map")
    assert res.status_code == 200
    data = res.get_json()
    assert data["count"] == 3

    # 2. Filter by severity
    res_high = admin_client.get("/api/admin/map?severity=High")
    data_high = res_high.get_json()
    assert data_high["count"] == 2
    assert all(p["severity"] == "High" for p in data_high["points"])

    # 3. Filter by department
    res_san = admin_client.get("/api/admin/map?department=Sanitation Department")
    data_san = res_san.get_json()
    assert data_san["count"] == 1
    assert data_san["points"][0]["ticket_id"] == "map0001"

    # 4. Filter by AI mode
    res_mode = admin_client.get("/api/admin/map?ai_mode=REAL_YOLO")
    data_mode = res_mode.get_json()
    assert data_mode["count"] == 2

    # 5. Filter by category
    res_cat = admin_client.get("/api/admin/map?category=plastic_bottle")
    data_cat = res_cat.get_json()
    assert data_cat["count"] == 1
    assert data_cat["points"][0]["ticket_id"] == "map0001"
    assert "plastic_bottle" in data_cat["points"][0]["categories"]


def test_admin_map_aggregation_bucketing(app, admin_client):
    with app.app_context():
        # Points very close together (within 0.01 deg cell)
        c1 = Complaint(id="agg001", latitude=18.5201, longitude=73.8501, severity_level="High", status="IN_PROGRESS", department="Sanitation Department")
        c2 = Complaint(id="agg002", latitude=18.5204, longitude=73.8503, severity_level="Low", status="RESOLVED", department="Sanitation Department")
        c3 = Complaint(id="agg003", latitude=18.5208, longitude=73.8505, severity_level="High", status="VERIFIED", department="Recycling Department")
        # Point in a distinct cell far away
        c4 = Complaint(id="agg004", latitude=18.6000, longitude=73.9500, severity_level="Medium", status="RESOLVED", department="Public Works Department")
        db.session.add_all([c1, c2, c3, c4])
        db.session.commit()

    res = admin_client.get("/api/admin/map/aggregate?cell_size=0.01")
    assert res.status_code == 200
    data = res.get_json()
    assert data["total_incidents"] == 4
    assert data["total_cells"] == 2

    # First cell should have 3 incidents
    top_cell = data["cells"][0]
    assert top_cell["incident_count"] == 3
    assert top_cell["high_severity"] == 2
    assert top_cell["resolved"] == 1
    assert top_cell["active"] == 2
    assert top_cell["departments"]["Sanitation Department"] == 2


def test_admin_geospatial_recurring_clusters(app, admin_client):
    with app.app_context():
        # c1 and c2 are 15 meters apart (< 50m)
        c1 = Complaint(id="rec001", latitude=18.52000, longitude=73.85000, status="IN_PROGRESS", address="Main Street Corner")
        c2 = Complaint(id="rec002", latitude=18.52010, longitude=73.85005, status="RESOLVED", address="Main Street Corner")
        # c3 is far away (> 50m)
        c3 = Complaint(id="rec003", latitude=18.55000, longitude=73.90000, status="VERIFIED", address="Distant Outpost")
        db.session.add_all([c1, c2, c3])
        db.session.commit()

    res = admin_client.get("/api/admin/geospatial")
    assert res.status_code == 200
    data = res.get_json()
    assert data["total_geolocated"] == 3
    assert len(data["recurring_areas"]) == 1
    cluster = data["recurring_areas"][0]
    assert cluster["report_count"] == 2
    assert cluster["label"] == "Recurring Report Concentration"
    assert "rec001" in cluster["ticket_ids"]
    assert "rec002" in cluster["ticket_ids"]


# ── Pillar 3: Operational Notifications & Rules Tests ───────────────────────

def test_notification_creation_and_idempotent_deduplication(app):
    with app.app_context():
        # 1. Create first notification
        n1 = create_notification(
            category=CATEGORY_NEW_HIGH_SEVERITY,
            title="High Severity Alert #test01",
            message="Test high severity incident detected.",
            ticket_id="test01",
            user_id=None,
            severity="High",
            department="Sanitation Department",
            deduplicate=True,
        )
        assert n1 is not None
        assert n1.id is not None
        assert n1.is_read is False

        # 2. Re-trigger identical notification (idempotency check)
        n2 = create_notification(
            category=CATEGORY_NEW_HIGH_SEVERITY,
            title="High Severity Alert #test01",
            message="Test high severity incident detected.",
            ticket_id="test01",
            user_id=None,
            severity="High",
            department="Sanitation Department",
            deduplicate=True,
        )
        assert n2.id == n1.id
        assert Notification.query.filter_by(ticket_id="test01").count() == 1


def test_admin_notification_endpoints(app, admin_client):
    with app.app_context():
        n1 = create_notification(
            category=CATEGORY_NEW_HIGH_SEVERITY,
            title="High Severity Alert #adm01",
            message="High severity issue.",
            ticket_id="adm01",
            user_id=None,
        )
        n2 = create_notification(
            category=CATEGORY_AI_PROCESSING_FAILED,
            title="AI Failed #adm02",
            message="Model error.",
            ticket_id="adm02",
            user_id=None,
        )
        db.session.commit()
        n1_id = n1.id

    # 1. List notifications
    res = admin_client.get("/api/admin/notifications")
    assert res.status_code == 200
    data = res.get_json()
    assert data["unread_count"] >= 2
    assert len(data["notifications"]) >= 2

    # 2. Mark one as read
    res_patch = admin_client.patch(f"/api/admin/notifications/{n1_id}/read")
    assert res_patch.status_code == 200
    patch_data = res_patch.get_json()
    assert patch_data["notification"]["is_read"] is True

    # 3. Read all
    res_all = admin_client.post("/api/admin/notifications/read-all")
    assert res_all.status_code == 200
    assert res_all.get_json()["unread_count"] == 0


def test_citizen_notifications_isolation_and_security(app, client):
    with app.app_context():
        # Register Citizen 1
        u1 = User(username="citizen_one", email="one@civic.org", role="citizen")
        u1.set_password("pass123")
        u2 = User(username="citizen_two", email="two@civic.org", role="citizen")
        u2.set_password("pass123")
        db.session.add_all([u1, u2])
        db.session.commit()

        n_one = create_notification(
            category=CATEGORY_STATUS_CHANGED,
            title="Report #one01 In Progress",
            message="Your report is being actioned.",
            ticket_id="one01",
            user_id=u1.id,
            deduplicate=False,
        )
        n_two = create_notification(
            category=CATEGORY_STATUS_CHANGED,
            title="Report #two01 Verified",
            message="Your report was verified.",
            ticket_id="two01",
            user_id=u2.id,
            deduplicate=False,
        )
        db.session.commit()
        n_one_id = n_one.id
        n_two_id = n_two.id

    # Citizen 1 logs in
    login(client, "citizen_one", "pass123")

    # Citizen 1 lists her notifications
    res = client.get("/api/notifications")
    assert res.status_code == 200
    data = res.get_json()
    assert len(data["notifications"]) == 1
    assert data["notifications"][0]["ticket_id"] == "one01"

    # Citizen 1 tries to mark Citizen 2's notification as read -> must fail 404
    res_hack = client.patch(f"/api/notifications/{n_two_id}/read")
    assert res_hack.status_code == 404

    # Citizen 1 marks her own notification read
    res_ok = client.patch(f"/api/notifications/{n_one_id}/read")
    assert res_ok.status_code == 200
    assert res_ok.get_json()["notification"]["is_read"] is True


def test_operational_alert_rules_triggers(app):
    with app.app_context():
        c = Complaint(
            id="rule001",
            severity_level="High",
            department="Sanitation Department",
            address="123 Civic Way",
            status="VERIFIED",
        )
        db.session.add(c)
        db.session.commit()

        # High severity rule
        notif = trigger_high_severity_rule(c)
        assert notif is not None
        assert notif.category == CATEGORY_NEW_HIGH_SEVERITY
        assert notif.ticket_id == "rule001"

        # AI failure rule
        notif_fail = trigger_ai_failure_rule(c, error_msg="Model inference timeout")
        assert notif_fail is not None
        assert notif_fail.category == CATEGORY_AI_PROCESSING_FAILED

        # Duplicate rule
        notif_dup = trigger_duplicate_rule(c, duplicate_of_id="parent01")
        assert notif_dup is not None
        assert notif_dup.category == CATEGORY_DUPLICATE_DETECTED


def test_aging_report_operational_rules(app):
    with app.app_context():
        old_time = datetime.utcnow() - timedelta(hours=14)
        c_aging = Complaint(
            id="age0001",
            status="SUBMITTED",
            department=None,
            severity_level="Low",
            created_at=old_time,
        )
        db.session.add(c_aging)
        db.session.commit()

        alerts = evaluate_aging_report_rules(unassigned_threshold_hours=12)
        assert len(alerts) >= 1
        assert any(a.ticket_id == "age0001" and a.category == CATEGORY_UNASSIGNED_REPORT for a in alerts)


# ── Pillar 4: Operational Insights Tests ────────────────────────────────────

def test_admin_operational_insights(app, admin_client):
    with app.app_context():
        now = datetime.utcnow()
        # Incident in current 7 days
        c1 = Complaint(
            id="ins001",
            created_at=now - timedelta(days=2),
            processing_completed_at=now - timedelta(days=2) + timedelta(minutes=5),
            severity_level="High",
            status="IN_PROGRESS",
            department="Sanitation Department",
            ai_mode="REAL_YOLO",
            processing_status="COMPLETED",
        )
        # Resolved incident
        c2 = Complaint(
            id="ins002",
            created_at=now - timedelta(days=3),
            processing_completed_at=now - timedelta(days=3) + timedelta(minutes=10),
            severity_level="Low",
            status="RESOLVED",
            department="Recycling Department",
            ai_mode="MOCK_DEMO",
            processing_status="COMPLETED",
        )
        # Incident in previous 7-day period (10 days ago)
        c3 = Complaint(
            id="ins003",
            created_at=now - timedelta(days=10),
            severity_level="Low",
            status="RESOLVED",
            department="Sanitation Department",
            ai_mode="MOCK_DEMO",
            processing_status="COMPLETED",
        )
        db.session.add_all([c1, c2, c3])
        db.session.commit()

    res = admin_client.get("/api/admin/insights?days=7")
    assert res.status_code == 200
    data = res.get_json()

    # Workload
    assert data["workload"]["unresolved_reports"] >= 1
    assert data["workload"]["highest_active_department"] == "Sanitation Department"

    # AI operations
    assert data["ai_operations"]["success_rate_pct"] == 100.0
    assert data["ai_operations"]["real_yolo_usage"] >= 1

    # Civic trends comparison
    trends = data["civic_trends"]
    assert trends["incident_volume"]["current"] == 2
    assert trends["incident_volume"]["previous"] == 1
    assert trends["incident_volume"]["delta_pct"] == 100.0

    # Resolution performance milestone
    perf = data["resolution_performance"]["submitted_to_verified"]
    assert perf["status"] == "Available"
    assert perf["completed_cases"] == 2
    assert perf["average_minutes"] == 7.5


def test_admin_insights_insufficient_data_handling(app, admin_client):
    res = admin_client.get("/api/admin/insights?days=7")
    assert res.status_code == 200
    data = res.get_json()
    perf = data["resolution_performance"]["submitted_to_verified"]
    assert perf["status"] == "Insufficient data"
    assert perf["average_minutes"] is None


def test_admin_overview_enhancement(app, admin_client):
    res = admin_client.get("/api/admin/overview")
    assert res.status_code == 200
    data = res.get_json()

    # Backwards compatibility
    assert "counts" in data
    assert "urgent_items" in data
    assert "recent_activity" in data

    # Phase 7 additions
    assert "civic_intelligence_summary" in data
    assert "spatial_summary" in data
    assert "recent_insights" in data
    assert "active_incident_count" in data["civic_intelligence_summary"]


# ── RBAC Security Tests ─────────────────────────────────────────────────────

def test_citizen_forbidden_from_admin_endpoints(app, citizen_client):
    for path in [
        "/api/admin/map",
        "/api/admin/map/aggregate",
        "/api/admin/geospatial",
        "/api/admin/insights",
        "/api/admin/notifications",
    ]:
        res = citizen_client.get(path)
        assert res.status_code in (403, 302)


def test_unauthenticated_forbidden_from_notifications(client):
    res = client.get("/api/notifications")
    assert res.status_code in (401, 302)


def test_admin_map_time_window_filtering(app, admin_client):
    with app.app_context():
        now = datetime.utcnow()
        c_recent = Complaint(id="time001", latitude=18.52, longitude=73.85, created_at=now - timedelta(days=2))
        c_old = Complaint(id="time002", latitude=18.53, longitude=73.86, created_at=now - timedelta(days=25))
        db.session.add_all([c_recent, c_old])
        db.session.commit()

    res_7 = admin_client.get("/api/admin/map?days=7")
    data_7 = res_7.get_json()
    assert data_7["count"] == 1
    assert data_7["points"][0]["ticket_id"] == "time001"

    res_30 = admin_client.get("/api/admin/map?days=30")
    data_30 = res_30.get_json()
    assert data_30["count"] == 2


def test_citizen_read_all_notifications(app, client):
    with app.app_context():
        u = User(username="citizen_reader", email="reader@civic.org", role="citizen")
        u.set_password("pass123")
        db.session.add(u)
        db.session.commit()

        n1 = create_notification("STATUS_CHANGED", "Alert 1", "Msg 1", user_id=u.id, deduplicate=False)
        n2 = create_notification("STATUS_CHANGED", "Alert 2", "Msg 2", user_id=u.id, deduplicate=False)
        db.session.commit()

    login(client, "citizen_reader", "pass123")
    res_list = client.get("/api/notifications?unread_only=true")
    assert res_list.get_json()["unread_count"] == 2

    res_read = client.post("/api/notifications/read-all")
    assert res_read.status_code == 200
    assert res_read.get_json()["marked_read"] == 2

    res_after = client.get("/api/notifications?unread_only=true")
    assert res_after.get_json()["unread_count"] == 0


def test_admin_notifications_category_filter(app, admin_client):
    with app.app_context():
        create_notification("NEW_HIGH_SEVERITY", "High Sev", "Details", ticket_id="cat01")
        create_notification("AI_PROCESSING_FAILED", "AI Err", "Details", ticket_id="cat02")
        db.session.commit()

    res_high = admin_client.get("/api/admin/notifications?category=NEW_HIGH_SEVERITY")
    data_high = res_high.get_json()
    assert all(n["category"] == "NEW_HIGH_SEVERITY" for n in data_high["notifications"])


def test_complaint_status_transition_triggers_in_app_notification(app, admin_client):
    target_user_id = None
    with app.app_context():
        u = User(username="target_citizen", email="target@civic.org", role="citizen")
        u.set_password("pass123")
        db.session.add(u)
        db.session.commit()
        target_user_id = u.id

        c = Complaint(
            id="trans001",
            user_id=target_user_id,
            status="VERIFIED",
            department="Sanitation Department",
            severity_level="High",
        )
        db.session.add(c)
        db.session.commit()

    # Admin updates status to IN_PROGRESS
    res = admin_client.patch("/api/complaints/trans001/status", json={"status": "IN_PROGRESS"})
    assert res.status_code == 200

    # Verify citizen in-app notification was generated
    with app.app_context():
        notif = Notification.query.filter_by(ticket_id="trans001", user_id=target_user_id).first()
        assert notif is not None
        assert "IN_PROGRESS" in notif.title or "In Progress" in notif.title or "in progress" in notif.message.lower()



def test_sse_notification_event_distribution(app):
    from events import _memory_subscribers, _memory_lock, publish_notification_event
    import queue

    test_q = queue.Queue(maxsize=10)
    with _memory_lock:
        if "admin:events" not in _memory_subscribers:
            _memory_subscribers["admin:events"] = []
        _memory_subscribers["admin:events"].append(test_q)

    try:
        sample_notif = {
            "id": 999,
            "category": "NEW_HIGH_SEVERITY",
            "title": "SSE High Severity Alert",
            "ticket_id": "sse001",
        }
        publish_notification_event(sample_notif, app=app)

        received = test_q.get(timeout=2.0)
        assert received["event"] == "notification_created"
        assert received["notification"]["ticket_id"] == "sse001"
    finally:
        with _memory_lock:
            if test_q in _memory_subscribers.get("admin:events", []):
                _memory_subscribers["admin:events"].remove(test_q)


def test_notification_deduplication_different_categories(app):
    with app.app_context():
        n1 = create_notification(CATEGORY_NEW_HIGH_SEVERITY, "High", "Msg", ticket_id="dup001")
        n2 = create_notification(CATEGORY_AI_PROCESSING_FAILED, "Failed", "Msg", ticket_id="dup001")
        assert n1.id != n2.id
        assert Notification.query.filter_by(ticket_id="dup001").count() == 2


def test_admin_notifications_read_all_empty(app, admin_client):
    res = admin_client.post("/api/admin/notifications/read-all")
    assert res.status_code == 200
    assert res.get_json()["marked_read"] == 0
    assert res.get_json()["unread_count"] == 0


def test_geospatial_summary_empty_database(app, admin_client):
    res = admin_client.get("/api/admin/geospatial")
    assert res.status_code == 200
    data = res.get_json()
    assert data["total_geolocated"] == 0
    assert data["total_unlocated"] == 0
    assert data["recurring_areas"] == []


def test_admin_map_multi_filter_combination(app, admin_client):
    with app.app_context():
        c1 = Complaint(id="comb01", latitude=18.52, longitude=73.85, severity_level="High", department="Sanitation Department", status="IN_PROGRESS")
        c2 = Complaint(id="comb02", latitude=18.53, longitude=73.86, severity_level="High", department="Recycling Department", status="IN_PROGRESS")
        c3 = Complaint(id="comb03", latitude=18.54, longitude=73.87, severity_level="Low", department="Sanitation Department", status="IN_PROGRESS")
        db.session.add_all([c1, c2, c3])
        db.session.commit()

    res = admin_client.get("/api/admin/map?severity=High&department=Sanitation Department")
    assert res.status_code == 200
    data = res.get_json()
    assert data["count"] == 1
    assert data["points"][0]["ticket_id"] == "comb01"


def test_citizen_notification_not_found(app, client):
    with app.app_context():
        u = User(username="citizen_empty", email="empty@civic.org", role="citizen")
        u.set_password("pass123")
        db.session.add(u)
        db.session.commit()

    login(client, "citizen_empty", "pass123")
    res = client.patch("/api/notifications/99999/read")
    assert res.status_code == 404


def test_insights_trends_zero_previous_period(app, admin_client):
    with app.app_context():
        now = datetime.utcnow()
        c = Complaint(id="zero01", created_at=now - timedelta(days=1), severity_level="Medium", status="VERIFIED")
        db.session.add(c)
        db.session.commit()

    res = admin_client.get("/api/admin/insights?days=7")
    assert res.status_code == 200
    trends = res.get_json()["civic_trends"]
    assert trends["incident_volume"]["current"] == 1
    assert trends["incident_volume"]["previous"] == 0
    assert trends["incident_volume"]["delta_pct"] == 100.0


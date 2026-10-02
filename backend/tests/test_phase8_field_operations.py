import io
import json
import os
from datetime import datetime, timezone, timedelta
import pytest
from PIL import Image

from models import Complaint, CitizenFeedback, Notification, User, db
from lifecycle import (
    STATUS_ASSIGNED,
    STATUS_IN_PROGRESS,
    STATUS_RESOLUTION_SUBMITTED,
    STATUS_RESOLVED,
    STATUS_SUBMITTED,
    STATUS_AI_PROCESSING,
)
from notifications import (
    CATEGORY_RESOLUTION_SUBMITTED,
    CATEGORY_RESOLUTION_CONFIRMED,
    CATEGORY_RESOLUTION_NEEDS_ATTENTION,
)


def create_dummy_image():
    """Generates a minimal valid in-memory JPEG image for upload testing."""
    file_bytes = io.BytesIO()
    img = Image.new("RGB", (64, 64), color="green")
    img.save(file_bytes, format="JPEG")
    file_bytes.seek(0)
    return file_bytes


def create_test_complaint(app, ticket_id="ECC-8001", user_id=None, status=STATUS_ASSIGNED, department="Sanitation Department"):
    with app.app_context():
        c = Complaint(
            id=ticket_id,
            user_id=user_id,
            status=status,
            severity_level="High",
            department=department,
            address="123 Elm St",
            image_path="test_elm.jpg",
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(c)
        db.session.commit()
        return c.id


# ── Test Suite ──────────────────────────────────────────────────────────────

def test_resolution_submission_authorization(app, client, citizen_client, admin_client):
    """Only authorized municipal/admin personnel can submit resolution evidence."""
    with app.app_context():
        citizen = User.query.filter_by(username="testcitizen").first()
        ticket_id = create_test_complaint(app, ticket_id="ECC-8010", user_id=citizen.id, status=STATUS_ASSIGNED)

    # 1. Unauthenticated -> 401
    res = client.post(f"/api/complaints/{ticket_id}/resolution", json={"note": "Cleaned up"})
    assert res.status_code == 401

    # 2. Citizen user -> 403
    res_cit = citizen_client.post(f"/api/complaints/{ticket_id}/resolution", json={"note": "I tried to fix it"})
    assert res_cit.status_code == 403

    # 3. Admin user -> 200
    res_adm = admin_client.post(f"/api/complaints/{ticket_id}/resolution", json={"note": "Municipal sanitation crew completed clearing and sanitization."})
    assert res_adm.status_code == 200
    data = res_adm.get_json()
    assert data["complaint"]["status"] == STATUS_RESOLUTION_SUBMITTED
    assert data["complaint"]["resolution"]["note"] == "Municipal sanitation crew completed clearing and sanitization."


def test_resolution_invalid_lifecycle_transition(app, admin_client):
    """Resolution cannot be submitted if ticket is not ASSIGNED or IN_PROGRESS."""
    with app.app_context():
        citizen = User.query.filter_by(username="testcitizen").first()
        # Ticket in SUBMITTED state cannot jump straight to RESOLUTION_SUBMITTED
        ticket_id = create_test_complaint(app, ticket_id="ECC-8011", user_id=citizen.id, status=STATUS_SUBMITTED)

    res = admin_client.post(f"/api/complaints/{ticket_id}/resolution", json={"note": "Done"})
    assert res.status_code == 400
    assert "Cannot submit resolution" in res.get_json()["error"]


def test_resolution_with_photo_upload_and_notification(app, admin_client):
    """Resolution evidence supports photo upload and notifies the citizen owner."""
    with app.app_context():
        citizen = User.query.filter_by(username="testcitizen").first()
        ticket_id = create_test_complaint(app, ticket_id="ECC-8012", user_id=citizen.id, status=STATUS_IN_PROGRESS)

    img_data = create_dummy_image()
    res = admin_client.post(
        f"/api/complaints/{ticket_id}/resolution",
        data={
            "note": "Refuse collected and area pressure washed.",
            "image": (img_data, "after_cleanup.jpg"),
        },
        content_type="multipart/form-data",
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["complaint"]["status"] == STATUS_RESOLUTION_SUBMITTED
    assert body["complaint"]["resolution"]["image_path"].startswith("resolution_ECC-8012_")

    with app.app_context():
        # Verify in-app notification sent to citizen
        citizen = User.query.filter_by(username="testcitizen").first()
        notif = Notification.query.filter_by(ticket_id="ECC-8012", user_id=citizen.id, category=CATEGORY_RESOLUTION_SUBMITTED).first()
        assert notif is not None
        assert "submitted resolution evidence" in notif.message


def test_get_resolution_evidence_authorization(app, client, citizen_client, admin_client):
    """Citizen owner and admin can view resolution; unauthenticated and other citizens cannot."""
    with app.app_context():
        owner = User.query.filter_by(username="testcitizen").first()
        other = User(username="othercitizen", email="other@test.com", role="citizen")
        other.set_password("pass123")
        db.session.add(other)
        db.session.commit()
        other_id = other.id

        ticket_id = create_test_complaint(app, ticket_id="ECC-8013", user_id=owner.id, status=STATUS_ASSIGNED)

    # Submit resolution as admin
    admin_client.post(f"/api/complaints/{ticket_id}/resolution", json={"note": "Debris removed"})

    # 1. Unauthenticated -> 401
    assert client.get(f"/api/complaints/{ticket_id}/resolution").status_code == 401

    # 2. Owner citizen -> 200
    res_owner = citizen_client.get(f"/api/complaints/{ticket_id}/resolution")
    assert res_owner.status_code == 200
    assert res_owner.get_json()["resolution_note"] == "Debris removed"

    # 3. Non-owner citizen -> 403
    other_client = app.test_client()
    other_client.post("/api/auth/login", json={"identifier": "othercitizen", "password": "pass123"})
    res_other = other_client.get(f"/api/complaints/{ticket_id}/resolution")
    assert res_other.status_code == 403

    # 4. Admin -> 200
    res_admin = admin_client.get(f"/api/complaints/{ticket_id}/resolution")
    assert res_admin.status_code == 200


def test_citizen_feedback_confirmed_workflow(app, citizen_client):
    """Citizen confirms resolution -> status transitions to RESOLVED and creates admin alert."""
    with app.app_context():
        citizen = User.query.filter_by(username="testcitizen").first()
        ticket_id = create_test_complaint(app, ticket_id="ECC-8014", user_id=citizen.id, status=STATUS_RESOLUTION_SUBMITTED)

    res = citizen_client.post(f"/api/complaints/{ticket_id}/feedback", json={
        "result": "CONFIRMED",
        "comment": "Site looks completely spotless now, thank you!",
    })
    assert res.status_code == 201
    data = res.get_json()
    assert data["feedback"]["result"] == "CONFIRMED"
    assert data["complaint"]["status"] == STATUS_RESOLVED

    with app.app_context():
        c = db.session.get(Complaint, ticket_id)
        assert c.status == STATUS_RESOLVED
        assert c.resolved_at is not None

        # Verify admin operational notification generated
        notif = Notification.query.filter_by(ticket_id=ticket_id, category=CATEGORY_RESOLUTION_CONFIRMED).first()
        assert notif is not None
        assert notif.user_id is None  # Admin broadcast


def test_citizen_feedback_needs_attention_workflow(app, citizen_client):
    """Citizen reports NEEDS_ATTENTION -> status returns to IN_PROGRESS and creates alert."""
    with app.app_context():
        citizen = User.query.filter_by(username="testcitizen").first()
        ticket_id = create_test_complaint(app, ticket_id="ECC-8015", user_id=citizen.id, status=STATUS_RESOLUTION_SUBMITTED)

    img_data = create_dummy_image()
    res = citizen_client.post(
        f"/api/complaints/{ticket_id}/feedback",
        data={
            "result": "NEEDS_ATTENTION",
            "comment": "Some broken glass was left behind near the drain.",
            "image": (img_data, "glass_left.jpg"),
        },
        content_type="multipart/form-data",
    )
    assert res.status_code == 201
    data = res.get_json()
    assert data["feedback"]["result"] == "NEEDS_ATTENTION"
    assert data["complaint"]["status"] == STATUS_IN_PROGRESS

    with app.app_context():
        c = db.session.get(Complaint, ticket_id)
        assert c.status == STATUS_IN_PROGRESS

        notif = Notification.query.filter_by(ticket_id=ticket_id, category=CATEGORY_RESOLUTION_NEEDS_ATTENTION).first()
        assert notif is not None
        assert "still needs attention" in notif.message


def test_citizen_feedback_ownership_protection(app):
    """Citizens cannot submit feedback on complaints they do not own."""
    with app.app_context():
        owner = User(username="legitowner", email="owner@test.com", role="citizen")
        owner.set_password("pass123")
        attacker = User(username="attacker", email="attacker@test.com", role="citizen")
        attacker.set_password("pass123")
        db.session.add_all([owner, attacker])
        db.session.commit()

        ticket_id = create_test_complaint(app, ticket_id="ECC-8016", user_id=owner.id, status=STATUS_RESOLUTION_SUBMITTED)

    attacker_client = app.test_client()
    attacker_client.post("/api/auth/login", json={"identifier": "attacker", "password": "pass123"})

    res = attacker_client.post(f"/api/complaints/{ticket_id}/feedback", json={
        "result": "CONFIRMED",
    })
    assert res.status_code == 403
    assert "Access denied" in res.get_json()["error"]


def test_citizen_feedback_duplicate_prevention(app, citizen_client):
    """Accidental rapid duplicate submissions within 60 seconds are throttled (409)."""
    with app.app_context():
        citizen = User.query.filter_by(username="testcitizen").first()
        ticket_id = create_test_complaint(app, ticket_id="ECC-8017", user_id=citizen.id, status=STATUS_RESOLUTION_SUBMITTED)

    # First submission
    res1 = citizen_client.post(f"/api/complaints/{ticket_id}/feedback", json={"result": "CONFIRMED"})
    assert res1.status_code == 201

    # Second immediate submission with same result
    res2 = citizen_client.post(f"/api/complaints/{ticket_id}/feedback", json={"result": "CONFIRMED"})
    assert res2.status_code == 409
    assert "Duplicate submission prevented" in res2.get_json()["error"]


def test_citizen_feedback_invalid_result_and_invalid_status(app, citizen_client):
    """Rejects invalid feedback results and submissions when complaint is not in resolution review."""
    with app.app_context():
        citizen = User.query.filter_by(username="testcitizen").first()
        ticket_id = create_test_complaint(app, ticket_id="ECC-8018", user_id=citizen.id, status=STATUS_RESOLUTION_SUBMITTED)

    # Invalid result string
    res_bad = citizen_client.post(f"/api/complaints/{ticket_id}/feedback", json={"result": "RATING_FIVE_STARS"})
    assert res_bad.status_code == 400
    assert "CONFIRMED" in res_bad.get_json()["error"]

    # Complaint not in resolution state
    with app.app_context():
        c = db.session.get(Complaint, ticket_id)
        c.status = STATUS_ASSIGNED
        db.session.commit()

    res_state = citizen_client.post(f"/api/complaints/{ticket_id}/feedback", json={"result": "CONFIRMED"})
    assert res_state.status_code == 400
    assert "must be in RESOLUTION_SUBMITTED" in res_state.get_json()["error"]


def test_get_feedback_history(app, citizen_client, admin_client):
    """Feedbacks can be listed by owner citizen and admin."""
    with app.app_context():
        citizen = User.query.filter_by(username="testcitizen").first()
        ticket_id = create_test_complaint(app, ticket_id="ECC-8019", user_id=citizen.id, status=STATUS_RESOLUTION_SUBMITTED)

    citizen_client.post(f"/api/complaints/{ticket_id}/feedback", json={"result": "NEEDS_ATTENTION", "comment": "First try not clean"})

    # Citizen owner gets feedback list
    res_cit = citizen_client.get(f"/api/complaints/{ticket_id}/feedback")
    assert res_cit.status_code == 200
    data_cit = res_cit.get_json()
    assert data_cit["total"] == 1
    assert data_cit["feedback"][0]["result"] == "NEEDS_ATTENTION"

    # Admin gets feedback list
    res_adm = admin_client.get(f"/api/complaints/{ticket_id}/feedback")
    assert res_adm.status_code == 200
    assert res_adm.get_json()["total"] == 1


def test_admin_feedback_queue_and_filters(app, citizen_client, admin_client):
    """Admin feedback queue lists items with filters and pagination."""
    with app.app_context():
        citizen = User.query.filter_by(username="testcitizen").first()
        t1 = create_test_complaint(app, ticket_id="ECC-8020", user_id=citizen.id, status=STATUS_RESOLUTION_SUBMITTED, department="Sanitation Department")
        t2 = create_test_complaint(app, ticket_id="ECC-8021", user_id=citizen.id, status=STATUS_RESOLUTION_SUBMITTED, department="Public Works")

    citizen_client.post(f"/api/complaints/{t1}/feedback", json={"result": "CONFIRMED", "comment": "Good job"})
    citizen_client.post(f"/api/complaints/{t2}/feedback", json={"result": "NEEDS_ATTENTION", "comment": "Pothole filled poorly"})

    # Admin list all
    res_all = admin_client.get("/api/admin/feedback")
    assert res_all.status_code == 200
    body_all = res_all.get_json()
    assert body_all["total"] >= 2

    # Filter by result
    res_needs = admin_client.get("/api/admin/feedback?result=NEEDS_ATTENTION")
    assert res_needs.status_code == 200
    body_needs = res_needs.get_json()
    assert all(item["result"] == "NEEDS_ATTENTION" for item in body_needs["feedback"])

    # Filter by department
    res_dept = admin_client.get("/api/admin/feedback?department=Public Works")
    assert res_dept.status_code == 200
    body_dept = res_dept.get_json()
    assert all(item["department"] == "Public Works" for item in body_dept["feedback"])


def test_admin_feedback_queue_role_protection(app, citizen_client):
    """Non-admin citizens cannot view the admin feedback queue."""
    res = citizen_client.get("/api/admin/feedback")
    assert res.status_code == 403


def test_operational_insights_field_operations_metrics(app, citizen_client, admin_client):
    """Operational insights endpoint includes field operations metrics."""
    with app.app_context():
        citizen = User.query.filter_by(username="testcitizen").first()
        t1 = create_test_complaint(app, ticket_id="ECC-8022", user_id=citizen.id, status=STATUS_IN_PROGRESS)

    # Admin submits resolution
    admin_client.post(f"/api/complaints/{t1}/resolution", json={"note": "Cleaned up"})
    # Citizen confirms
    citizen_client.post(f"/api/complaints/{t1}/feedback", json={"result": "CONFIRMED"})

    res = admin_client.get("/api/admin/insights?days=7")
    assert res.status_code == 200
    data = res.get_json()
    assert "field_operations" in data
    field_ops = data["field_operations"]
    assert field_ops["total_resolution_submissions"] >= 1
    assert field_ops["citizen_confirmations"] >= 1
    assert "feedback_response_rate_pct" in field_ops


def test_secure_image_access_resolution_and_feedback(app, admin_client, citizen_client):
    """Resolution and feedback images cannot be accessed by unauthorized citizens or public."""
    with app.app_context():
        citizen = User.query.filter_by(username="testcitizen").first()
        other = User(username="othercit2", email="other2@test.com", role="citizen")
        other.set_password("pass123")
        db.session.add(other)
        db.session.commit()

        t = create_test_complaint(app, ticket_id="ECC-8023", user_id=citizen.id, status=STATUS_IN_PROGRESS)

    # 1. Admin uploads resolution image
    img1 = create_dummy_image()
    res1 = admin_client.post(
        f"/api/complaints/{t}/resolution",
        data={"note": "Done", "image": (img1, "res.jpg")},
        content_type="multipart/form-data",
    )
    assert res1.status_code == 200
    res_filename = res1.get_json()["complaint"]["resolution"]["image_path"]

    # 2. Citizen owner uploads feedback image
    img2 = create_dummy_image()
    res2 = citizen_client.post(
        f"/api/complaints/{t}/feedback",
        data={"result": "NEEDS_ATTENTION", "comment": "Left debris", "image": (img2, "fb.jpg")},
        content_type="multipart/form-data",
    )
    assert res2.status_code == 201
    fb_filename = res2.get_json()["feedback"]["image_path"]

    # 3. Unauthenticated -> 401
    guest_client = app.test_client()
    assert guest_client.get(f"/uploads/{res_filename}").status_code == 401
    assert guest_client.get(f"/uploads/{fb_filename}").status_code == 401

    # 4. Another citizen -> 403
    other_client = app.test_client()
    other_client.post("/api/auth/login", json={"identifier": "othercit2", "password": "pass123"})
    assert other_client.get(f"/uploads/{res_filename}").status_code == 403
    assert other_client.get(f"/uploads/{fb_filename}").status_code == 403

    # 5. Owner citizen -> 200
    assert citizen_client.get(f"/uploads/{res_filename}").status_code == 200
    assert citizen_client.get(f"/uploads/{fb_filename}").status_code == 200

    # 6. Admin -> 200
    assert admin_client.get(f"/uploads/{res_filename}").status_code == 200
    assert admin_client.get(f"/uploads/{fb_filename}").status_code == 200

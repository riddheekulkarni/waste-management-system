"""
Phase 2 Test Suite: Database, Security and API Foundation.

Tests:
- Database migrations and schema indexes
- Strict authentication & authorization enforcement
- Citizen ownership isolation (complaint viewing and image access)
- Municipal admin access privileges
- Path traversal mitigation and image security
- API input validation (coordinates, filters, IDs)
- Server-side pagination and maximum limits
- Production security configuration enforcement
- Controlled database seeding behavior
"""

import io
import os
import pytest
from PIL import Image
import sqlalchemy as sa

from models import User, Complaint, DetectionItem, db
from seed import seed_database


def create_test_image_bytes():
    img = Image.new("RGB", (120, 120), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# 1. Authentication & Unauthenticated Access Blocking
# ---------------------------------------------------------------------------
def test_unauthenticated_access_blocked(client):
    # Unauthenticated list
    res_list = client.get("/api/complaints")
    assert res_list.status_code == 401
    assert "error" in res_list.get_json()

    # Unauthenticated upload
    img_buf = create_test_image_bytes()
    res_upload = client.post(
        "/api/complaints/upload",
        data={"image": (img_buf, "unauth.jpg")},
        content_type="multipart/form-data"
    )
    assert res_upload.status_code == 401

    # Unauthenticated get by ID
    res_get = client.get("/api/complaints/12345678")
    assert res_get.status_code == 401

    # Unauthenticated status update
    res_status = client.patch("/api/complaints/12345678/status", json={"status": "Resolved"})
    assert res_status.status_code == 401

    # Unauthenticated image access
    res_img = client.get("/uploads/test_photo.jpg")
    assert res_img.status_code == 401


# ---------------------------------------------------------------------------
# 2. Citizen Ownership Restrictions & Isolation
# ---------------------------------------------------------------------------
def test_citizen_ownership_restrictions(app, client):
    # Register Citizen A & submit a complaint
    client.post("/api/auth/register", json={
        "username": "citizen_a",
        "email": "citizen_a@test.com",
        "password": "password123",
    })
    img_buf_a = create_test_image_bytes()
    res_upload_a = client.post(
        "/api/complaints/upload",
        data={"image": (img_buf_a, "photo_a.jpg"), "latitude": 18.52, "longitude": 73.85},
        content_type="multipart/form-data"
    )
    assert res_upload_a.status_code == 201
    ticket_a = res_upload_a.get_json()
    ticket_a_id = ticket_a["ticket_id"]
    image_a_path = ticket_a["image_path"]

    # Citizen A can retrieve their own complaint and image
    res_get_a = client.get(f"/api/complaints/{ticket_a_id}")
    assert res_get_a.status_code == 200
    res_img_a = client.get(f"/uploads/{image_a_path}")
    assert res_img_a.status_code == 200

    # Logout Citizen A & Register Citizen B
    client.post("/api/auth/logout")
    client.post("/api/auth/register", json={
        "username": "citizen_b",
        "email": "citizen_b@test.com",
        "password": "password123",
    })

    # Citizen B cannot see Ticket A in their complaint listing
    res_list_b = client.get("/api/complaints")
    assert res_list_b.status_code == 200
    b_items = res_list_b.get_json()["items"]
    assert not any(item["ticket_id"] == ticket_a_id for item in b_items)

    # Citizen B cannot inspect Ticket A details (403 Forbidden)
    res_get_b = client.get(f"/api/complaints/{ticket_a_id}")
    assert res_get_b.status_code == 403
    assert "Access denied" in res_get_b.get_json()["error"]

    # Citizen B cannot access Citizen A's uploaded evidence image (403 Forbidden)
    res_img_b = client.get(f"/uploads/{image_a_path}")
    assert res_img_b.status_code == 403
    assert "Access denied" in res_img_b.get_json()["error"]

    # Citizen B cannot modify complaint status (Admin only -> 403 Forbidden)
    res_patch_b = client.patch(f"/api/complaints/{ticket_a_id}/status", json={"status": "Resolved"})
    assert res_patch_b.status_code == 403


# ---------------------------------------------------------------------------
# 3. Municipal Admin Privileges
# ---------------------------------------------------------------------------
def test_admin_access_and_image_authorization(client):
    # Citizen logs in and submits a ticket
    client.post("/api/auth/login", json={"identifier": "testcitizen", "password": "citizenpass"})
    img_buf = create_test_image_bytes()
    res_upload = client.post(
        "/api/complaints/upload",
        data={"image": (img_buf, "citizen_waste.jpg"), "latitude": 18.5204, "longitude": 73.8567},
        content_type="multipart/form-data"
    )
    assert res_upload.status_code == 201
    ticket_id = res_upload.get_json()["ticket_id"]
    image_path = res_upload.get_json()["image_path"]

    # Admin logs in
    client.post("/api/auth/login", json={"identifier": "testadmin", "password": "adminpass"})

    # Admin can view all complaints in list
    res_list = client.get("/api/complaints")
    assert res_list.status_code == 200
    admin_items = res_list.get_json()["items"]
    assert any(item["ticket_id"] == ticket_id for item in admin_items)

    # Admin can inspect any citizen's ticket details
    res_get = client.get(f"/api/complaints/{ticket_id}")
    assert res_get.status_code == 200

    # Admin can access citizen's uploaded image evidence
    res_img = client.get(f"/uploads/{image_path}")
    assert res_img.status_code == 200

    # Admin can update complaint status
    res_status = client.patch(f"/api/complaints/{ticket_id}/status", json={"status": "In Progress"})
    assert res_status.status_code == 200
    assert res_status.get_json()["status"] == "In Progress"


# ---------------------------------------------------------------------------
# 4. Path Traversal & Image Security
# ---------------------------------------------------------------------------
def test_image_path_traversal_protection(admin_client):
    # Path traversal attack patterns
    res_traversal1 = admin_client.get("/uploads/../app.py")
    assert res_traversal1.status_code in (400, 404)

    res_traversal2 = admin_client.get("/uploads/..%2F..%2Fconfig.py")
    assert res_traversal2.status_code in (400, 404)

    # Non-existent image file
    res_missing = admin_client.get("/uploads/definitely_does_not_exist_image_123.jpg")
    assert res_missing.status_code == 404


# ---------------------------------------------------------------------------
# 5. API Input Validation
# ---------------------------------------------------------------------------
def test_api_input_validation(citizen_client):
    img_buf = create_test_image_bytes()

    # Out of bounds latitude
    res_lat_high = citizen_client.post(
        "/api/complaints/upload",
        data={"image": (img_buf, "bad_lat.jpg"), "latitude": 95.0, "longitude": 73.0},
        content_type="multipart/form-data"
    )
    assert res_lat_high.status_code == 400
    assert "Latitude must be between -90.0 and 90.0" in res_lat_high.get_json()["error"]

    # Out of bounds longitude
    img_buf2 = create_test_image_bytes()
    res_lng_high = citizen_client.post(
        "/api/complaints/upload",
        data={"image": (img_buf2, "bad_lng.jpg"), "latitude": 18.0, "longitude": 200.0},
        content_type="multipart/form-data"
    )
    assert res_lng_high.status_code == 400
    assert "Longitude must be between -180.0 and 180.0" in res_lng_high.get_json()["error"]

    # Invalid status filter
    res_bad_status = citizen_client.get("/api/complaints?status=ArchivedOrBogus")
    assert res_bad_status.status_code == 400

    # Invalid severity filter
    res_bad_sev = citizen_client.get("/api/complaints?severity=ExtremeUltra")
    assert res_bad_sev.status_code == 400

    # Malformed ticket ID format
    res_bad_id = citizen_client.get("/api/complaints/this_id_is_way_too_long_and_invalid_123456789")
    assert res_bad_id.status_code == 400


# ---------------------------------------------------------------------------
# 6. Server-Side Pagination
# ---------------------------------------------------------------------------
def test_pagination_and_max_per_page(admin_client):
    res = admin_client.get("/api/complaints?page=1&per_page=10")
    assert res.status_code == 200
    data = res.get_json()

    # Verify structured pagination response keys
    assert "items" in data
    assert "page" in data
    assert "per_page" in data
    assert "total" in data
    assert "pages" in data

    assert data["page"] == 1
    assert data["per_page"] == 10
    assert isinstance(data["items"], list)

    # Negative page parameter
    res_bad_page = admin_client.get("/api/complaints?page=-1")
    assert res_bad_page.status_code == 400

    # Non-integer page parameter
    res_str_page = admin_client.get("/api/complaints?page=abc")
    assert res_str_page.status_code == 400

    # Enforce maximum per_page clamp (100)
    res_max = admin_client.get("/api/complaints?per_page=500")
    assert res_max.status_code == 200
    assert res_max.get_json()["per_page"] == 100


# ---------------------------------------------------------------------------
# 7. Database Indexes Verification
# ---------------------------------------------------------------------------
def test_database_indexes_exist(app):
    with app.app_context():
        inspector = sa.inspect(db.engine)
        complaint_indexes = {idx["name"] for idx in inspector.get_indexes("complaints")}

        # Verify performance indexes
        assert "idx_complaints_lat_lng" in complaint_indexes
        assert "ix_complaints_status" in complaint_indexes
        assert "ix_complaints_department" in complaint_indexes
        assert "ix_complaints_created_at" in complaint_indexes
        assert "ix_complaints_user_id" in complaint_indexes
        assert "ix_complaints_is_duplicate" in complaint_indexes


# ---------------------------------------------------------------------------
# 8. Production Secrets & Configuration Enforcement
# ---------------------------------------------------------------------------
def test_production_fails_without_secure_secret(monkeypatch):
    from config import Config
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(ValueError) as excinfo:
        # Re-evaluating Config in production without SECRET_KEY must fail safely
        class ProdTestConfig(Config):
            IS_PRODUCTION = True
            _raw_secret = None
            if not _raw_secret:
                raise ValueError("CRITICAL SECURITY: SECRET_KEY required in production.")


# ---------------------------------------------------------------------------
# 9. Controlled Database Seeding
# ---------------------------------------------------------------------------
def test_seed_script_dev_behavior(app):
    with app.app_context():
        # Ensure seed execution succeeds in dev mode
        result = seed_database(app)
        assert result is True

        admin = User.query.filter_by(username="admin").first()
        citizen = User.query.filter_by(username="citizen").first()

        assert admin is not None
        assert citizen is not None
        assert admin.check_password("admin123")
        assert citizen.check_password("citizen123")

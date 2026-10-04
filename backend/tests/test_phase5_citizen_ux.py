"""
Phase 5 Tests — Citizen Experience, Guided Reporting Wizard, and Frontend Integration.

Tests:
1. Frontend static root route (GET /) serves index.html with 200 and HTML content type.
2. Frontend static assets (GET /css/styles.css and GET /js/app.js) are served properly.
3. Landing page contains required civic branding and hero elements.
4. Guided reporting wizard fields and validation endpoints function properly.
5. Citizen dashboard complaint aggregation (active vs resolved counts).
6. Unauthorized access to citizen complaints is strictly prevented.
7. Landmark notes handling during complaint submission preserves location details.
"""

import io
import json
import pytest
from PIL import Image
from models import Complaint, User, db
from lifecycle import STATUS_AI_PROCESSING, STATUS_VERIFIED, STAGE_COMPLETED, STAGE_QUEUED


def _make_dummy_image():
    buf = io.BytesIO()
    img = Image.new("RGB", (200, 200), color=(100, 150, 200))
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf


def test_root_serves_frontend_html(client):
    """GET / must return 200 and serve the EcoClean Civic frontend HTML."""
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["Content-Type"]
    html = res.get_data(as_text=True)
    assert "EcoClean" in html
    assert "Civic" in html
    assert "Cleaner streets. Smarter civic response." in html


def test_frontend_assets_served(client):
    """Styles and script assets must be accessible and return 200."""
    res_css = client.get("/css/styles.css")
    assert res_css.status_code == 200
    assert "text/css" in res_css.headers["Content-Type"] or "css" in res_css.headers["Content-Type"]

    res_js = client.get("/js/app.js")
    assert res_js.status_code == 200
    assert "javascript" in res_js.headers["Content-Type"] or "application/x-javascript" in res_js.headers["Content-Type"]


def test_landing_page_structure(client):
    """Landing page must contain How It Works, Features, and Transparency sections."""
    res = client.get("/")
    html = res.get_data(as_text=True)

    assert "How EcoClean Civic Works" in html
    assert "Built for Modern Civic Operations" in html
    assert "Open Civic Transparency" in html
    assert "Report a Civic Issue" in html
    assert "Citizen Dashboard" in html


def test_citizen_dashboard_complaints_aggregation(app, citizen_client):
    """Citizen complaints are properly partitioned into active and resolved for the dashboard."""
    res_me = citizen_client.get("/api/auth/me")
    uid = res_me.get_json()["user"]["id"]

    with app.app_context():
        c1 = Complaint(
            id="dash001",
            user_id=uid,
            image_path="test1.jpg",
            address="123 Active St",
            status=STATUS_AI_PROCESSING,
            processing_status=STAGE_QUEUED,
        )
        c2 = Complaint(
            id="dash002",
            user_id=uid,
            image_path="test2.jpg",
            address="456 Resolved Ave",
            status="Resolved",
            processing_status=STAGE_COMPLETED,
        )
        # Another citizen's complaint
        c3 = Complaint(
            id="dash003",
            user_id=9999,
            image_path="test3.jpg",
            address="789 Other St",
            status=STATUS_AI_PROCESSING,
            processing_status=STAGE_QUEUED,
        )
        db.session.add_all([c1, c2, c3])
        db.session.commit()

    res = citizen_client.get("/api/complaints")
    assert res.status_code == 200
    data = res.get_json()
    items = data.get("items", [])
    ticket_ids = [item["ticket_id"] for item in items]

    assert "dash001" in ticket_ids
    assert "dash002" in ticket_ids
    # Crucial security check: citizen must NOT see other citizens' complaints
    assert "dash003" not in ticket_ids


def test_report_wizard_submission_with_landmark(citizen_client):
    """Submitting through the guided reporting wizard preserves coordinates and landmark."""
    img_data = _make_dummy_image()
    data = {
        "image": (img_data, "rubbish.jpg"),
        "latitude": "18.520400",
        "longitude": "73.856700",
        "address": "Opposite Shivaji Market (Landmark: Near Gate 3)",
    }
    res = citizen_client.post(
        "/api/complaints/upload",
        data=data,
        content_type="multipart/form-data"
    )
    assert res.status_code == 201
    body = res.get_json()
    assert body["success"] is True
    assert "Shivaji Market" in body["address"]
    assert "Near Gate 3" in body["address"]
    assert body["status"] in (STATUS_AI_PROCESSING, STATUS_VERIFIED)

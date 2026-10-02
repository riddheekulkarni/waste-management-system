"""
Phase 3 End-to-End Manual Verification Script.
"""

import os
import sys
import time
from io import BytesIO
from unittest.mock import patch
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from lifecycle import (
    STAGE_COMPLETED,
    STAGE_FAILED,
    STATUS_AI_PROCESSING,
    STATUS_DUPLICATE,
    STATUS_PROCESSING_FAILED,
    STATUS_VERIFIED,
)
from models import Complaint, DetectionItem, User, db
from tasks import process_complaint_job


def run_verification():
    app = create_app()
    client = app.test_client()

    print("\n--- 1. Citizen Registration and Login ---")
    client.post("/api/auth/register", json={"username": "p3_verifier", "email": "p3_ver@civic.gov", "password": "password123"})
    r_login = client.post("/api/auth/login", json={"identifier": "p3_verifier", "password": "password123"})
    assert r_login.status_code == 200
    print("✅ Authenticated as citizen")

    print("\n--- 2. Async Complaint Submission ---")
    img = Image.new("RGB", (160, 160), color="green")
    buf = BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    with patch("routes.complaints.enqueue_complaint_job") as mock_q:
        mock_q.return_value = "mock-job-p3"
        t0 = time.time()
        r = client.post(
            "/api/complaints/upload",
            data={
                "image": (buf, "waste_p3.jpg"),
                "latitude": "18.5300",
                "longitude": "73.8500",
                "address": "Pune East Station",
            },
            content_type="multipart/form-data"
        )
        latency = (time.time() - t0) * 1000
        assert r.status_code == 201
        d = r.get_json()
        ticket_id = d["ticket_id"]
        assert d["status"] == STATUS_AI_PROCESSING
        print(f"✅ Fast API response ({latency:.1f}ms): Ticket #{ticket_id}, Status: {d['status']}, Stage: {d['processing_status']}")

    print("\n--- 3. Lightweight Processing Status API Check ---")
    r_stat = client.get(f"/api/complaints/{ticket_id}/processing-status")
    assert r_stat.status_code == 200
    stat_data = r_stat.get_json()
    assert stat_data["status"] == STATUS_AI_PROCESSING
    print(f"✅ GET /processing-status: stage={stat_data['stage']}, progress=\"{stat_data['progress']}\"")

    print("\n--- 4. Worker Processing Pipeline ---")
    success = process_complaint_job(ticket_id, app=app)
    assert success is True
    with app.app_context():
        c = db.session.get(Complaint, ticket_id)
        assert c.status == STATUS_VERIFIED
        assert c.processing_status == STAGE_COMPLETED
        assert c.severity_level in ("Low", "Medium", "High")
        assert c.department is not None
        assert len(c.detections) > 0
        assert c.processing_duration_ms > 0
        print(f"✅ Verified ticket #{ticket_id}: Status={c.status}, Severity={c.severity_level}, Dept={c.department}, Detections={len(c.detections)}, Duration={c.processing_duration_ms}ms")

    print("\n--- 5. Proximity Duplicate Detection ---")
    img2 = Image.new("RGB", (160, 160), color="blue")
    buf2 = BytesIO()
    img2.save(buf2, format="JPEG")
    buf2.seek(0)
    with patch("routes.complaints.enqueue_complaint_job") as mock_q:
        mock_q.return_value = "mock-job-dup"
        r2 = client.post(
            "/api/complaints/upload",
            data={
                "image": (buf2, "waste_dup.jpg"),
                "latitude": "18.53002",
                "longitude": "73.85001",
            },
            content_type="multipart/form-data"
        )
        ticket_dup = r2.get_json()["ticket_id"]

    process_complaint_job(ticket_dup, app=app)
    with app.app_context():
        c_dup = db.session.get(Complaint, ticket_dup)
        assert c_dup.status == STATUS_DUPLICATE
        assert c_dup.is_duplicate is True
        assert c_dup.duplicate_of_id == ticket_id
        print(f"✅ Duplicate detection: Ticket #{ticket_dup} linked to #{ticket_id} (Status={c_dup.status})")

    print("\n--- 6. Simulated Processing Failure ---")
    with app.app_context():
        c_fail = Complaint(id="f_man01", image_path="missing_file_xyz.jpg", status=STATUS_AI_PROCESSING, processing_status="QUEUED")
        db.session.add(c_fail)
        db.session.commit()

    success_fail = process_complaint_job("f_man01", app=app)
    assert success_fail is False
    with app.app_context():
        c_fail = db.session.get(Complaint, "f_man01")
        assert c_fail.status == STATUS_PROCESSING_FAILED
        assert c_fail.processing_status == STAGE_FAILED
        assert "found" in c_fail.processing_error.lower()
        print(f"✅ Failure isolated: Status={c_fail.status}, Error=\"{c_fail.processing_error}\"")

    print("\n--- 7. Admin Retry Verification ---")
    client_admin = app.test_client()
    with app.app_context():
        admin = User.query.filter_by(role="admin").first()
        if not admin:
            admin = User(username="admin_p3", email="admin_p3@civic.gov", role="admin")
            admin.set_password("AdminPass123!")
            db.session.add(admin)
            db.session.commit()
        admin_uname = admin.username
        admin.set_password("AdminPass123!")
        db.session.commit()

    client_admin.post("/api/auth/login", json={"identifier": admin_uname, "password": "AdminPass123!"})

    with patch("routes.complaints.enqueue_complaint_job") as mock_q:
        mock_q.return_value = "mock-job-retry"
        r_retry = client_admin.post("/api/complaints/f_man01/retry-processing")
        assert r_retry.status_code == 200
        d_retry = r_retry.get_json()
        assert d_retry["retry_count"] == 1
        assert d_retry["status"] == STATUS_AI_PROCESSING
        print(f"✅ Retry endpoint: Ticket #{d_retry['ticket_id']}, Retried={d_retry['retry_count']}, Status={d_retry['status']}")

    print("\n--- 8. Admin Queue Visibility ---")
    r_queue = client_admin.get("/api/complaints/admin/queue?processing_status=FAILED")
    assert r_queue.status_code == 200
    q_data = r_queue.get_json()
    print(f"✅ Admin queue view: Total failed jobs={q_data['total']}, Page={q_data['page']}")

    print("\n🎉 ALL PHASE 3 END-TO-END MANUAL VERIFICATIONS COMPLETED SUCCESSFULLY!\n")


if __name__ == "__main__":
    run_verification()

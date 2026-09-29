"""
Tests for the notification engine and the status-update route's
citizen-email lookup behaviour.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from notifications import notify_citizen, _build_message


# ---------------------------------------------------------------------------
# Unit tests — notification engine
# ---------------------------------------------------------------------------

class TestBuildMessage:
    def test_known_status_resolved(self):
        subject, body = _build_message("abc123", "Resolved")
        assert "abc123" in subject
        assert "Resolved" in subject
        assert "resolved" in body.lower()

    def test_known_status_in_progress(self):
        subject, body = _build_message("xyz999", "In Progress")
        assert "In Progress" in subject
        assert "municipal team" in body

    def test_unknown_status_fallback(self):
        subject, body = _build_message("t001", "Pending Review")
        assert "Pending Review" in subject
        assert "updated to" in body


class TestNotifyCitizen:
    def test_log_only_no_email_returns_not_delivered(self):
        """When no recipient_email is given, delivered must be False."""
        result = notify_citizen("t001", "Resolved", recipient_email=None)
        assert result["delivered"] is False
        assert result["ticket_id"] == "t001"
        assert result["new_status"] == "Resolved"

    def test_log_only_with_email_not_delivered_without_backend(self, monkeypatch):
        """With NOTIFY_BACKEND=log (default), delivered is still False even
        with a valid email — no real delivery occurs."""
        monkeypatch.setenv("NOTIFY_BACKEND", "log")
        result = notify_citizen("t002", "In Progress", recipient_email="user@example.com")
        assert result["delivered"] is False
        assert "log" in result["backend"]

    def test_smtp_missing_credentials_returns_not_delivered(self, monkeypatch):
        """SMTP backend with no credentials falls back to log-only gracefully."""
        monkeypatch.setenv("NOTIFY_BACKEND", "smtp")
        monkeypatch.delenv("SMTP_USER", raising=False)
        monkeypatch.delenv("SMTP_PASSWORD", raising=False)
        result = notify_citizen("t003", "Resolved", recipient_email="user@example.com")
        assert result["delivered"] is False

    def test_sendgrid_missing_api_key_returns_not_delivered(self, monkeypatch):
        """SendGrid backend with no API key falls back to log-only gracefully."""
        monkeypatch.setenv("NOTIFY_BACKEND", "sendgrid")
        monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
        result = notify_citizen("t004", "Resolved", recipient_email="user@example.com")
        assert result["delivered"] is False


# ---------------------------------------------------------------------------
# Integration test — status update route resolves citizen email from DB
# ---------------------------------------------------------------------------

def test_status_update_notification_includes_recipient(app):
    """
    Verify that PATCH /api/complaints/<id>/status returns a notification dict
    that contains the citizen's real email address as recipient when the
    complaint was submitted by a logged-in citizen.

    Two separate test clients are used so that the citizen session and the
    admin session don't overwrite each other in the server-side session store.
    """
    import io
    from PIL import Image

    citizen_client = app.test_client()
    admin_client = app.test_client()

    # Authenticate each client independently
    citizen_client.post("/api/auth/login", json={"identifier": "testcitizen", "password": "citizenpass"})
    admin_client.post("/api/auth/login", json={"identifier": "testadmin", "password": "adminpass"})

    # Upload a complaint as the test citizen
    img = Image.new("RGB", (100, 100), color="green")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    upload_res = citizen_client.post(
        "/api/complaints/upload",
        data={"image": (buf, "green.jpg"), "address": "Test Street"},
        content_type="multipart/form-data",
    )
    assert upload_res.status_code == 201
    ticket_id = upload_res.get_json()["ticket_id"]

    # Admin changes the status
    patch_res = admin_client.patch(
        f"/api/complaints/{ticket_id}/status",
        json={"status": "Resolved"},
    )
    assert patch_res.status_code == 200
    data = patch_res.get_json()

    assert "notification" in data
    notif = data["notification"]
    # The citizen's email should have been resolved and passed to the notifier
    assert notif["recipient"] == "citizen@test.com"
    assert notif["ticket_id"] == ticket_id
    assert notif["new_status"] == "Resolved"


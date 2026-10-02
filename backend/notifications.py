"""
Notification dispatch engine.

Handles sending status-update notifications to citizens when their complaint
ticket changes state (Open → In Progress → Resolved).

Delivery backends (choose one via environment variables):
──────────────────────────────────────────────────────────
SMTP / Gmail
  NOTIFY_BACKEND=smtp
  SMTP_HOST=smtp.gmail.com
  SMTP_PORT=587
  SMTP_USER=your-app@gmail.com
  SMTP_PASSWORD=<gmail-app-password>
  SMTP_FROM=EcoClean Civic <your-app@gmail.com>

SendGrid
  NOTIFY_BACKEND=sendgrid
  SENDGRID_API_KEY=SG.xxxx
  SMTP_FROM=no-reply@yourdomain.com

Log-only (default — no credentials needed)
  NOTIFY_BACKEND=log   (or leave NOTIFY_BACKEND unset)

When no backend is configured the function logs the notification and returns
delivered=False so the admin dashboard reflects the honest delivery state.
"""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger("ecoclean.notifications")
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Message templates
# ---------------------------------------------------------------------------

_STATUS_LABELS = {
    "Open": "has been received and is open",
    "In Progress": "is now being actioned by the municipal team",
    "Resolved": "has been resolved — thank you for helping keep your city clean!",
}


def _build_message(ticket_id: str, new_status: str) -> tuple[str, str]:
    """Return (subject, plain-text body) for the given status transition."""
    label = _STATUS_LABELS.get(new_status, f"has been updated to '{new_status}'")
    subject = f"[EcoClean] Ticket #{ticket_id} — {new_status}"
    body = (
        f"Hello,\n\n"
        f"Your waste complaint (Ticket #{ticket_id}) {label}.\n\n"
        f"You can track your ticket status at any time by logging into the EcoClean portal.\n\n"
        f"Thank you for contributing to a cleaner city.\n\n"
        f"— EcoClean Civic Waste Management Team"
    )
    return subject, body


# ---------------------------------------------------------------------------
# Backend implementations
# ---------------------------------------------------------------------------

def _send_smtp(recipient_email: str, subject: str, body: str) -> bool:
    """Send via SMTP (Gmail / any SMTP relay). Returns True on success."""
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", 587))
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    sender = os.environ.get("SMTP_FROM", user)

    if not user or not password:
        logger.warning(
            "SMTP backend selected but SMTP_USER / SMTP_PASSWORD not set. "
            "Falling back to log-only mode."
        )
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient_email
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(user, password)
            server.sendmail(sender, [recipient_email], msg.as_string())
        logger.info("SMTP: email delivered to %s", recipient_email)
        return True
    except Exception as exc:
        logger.error("SMTP delivery failed for %s: %s", recipient_email, exc)
        return False


def _send_sendgrid(recipient_email: str, subject: str, body: str) -> bool:
    """Send via SendGrid Web API. Returns True on success."""
    try:
        import urllib.request
        import json as _json

        api_key = os.environ.get("SENDGRID_API_KEY", "")
        sender = os.environ.get("SMTP_FROM", "no-reply@ecoclean.gov")

        if not api_key:
            logger.warning("SENDGRID_API_KEY not set. Falling back to log-only mode.")
            return False

        payload = _json.dumps({
            "personalizations": [{"to": [{"email": recipient_email}]}],
            "from": {"email": sender},
            "subject": subject,
            "content": [{"type": "text/plain", "value": body}],
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.sendgrid.com/v3/mail/send",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            success = resp.status in (200, 202)
            if success:
                logger.info("SendGrid: email delivered to %s", recipient_email)
            return success
    except Exception as exc:
        logger.error("SendGrid delivery failed for %s: %s", recipient_email, exc)
        return False


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Notification Categories (Pillar 3 & 4)
# ---------------------------------------------------------------------------

CATEGORY_NEW_HIGH_SEVERITY = "NEW_HIGH_SEVERITY"
CATEGORY_AI_PROCESSING_FAILED = "AI_PROCESSING_FAILED"
CATEGORY_DUPLICATE_DETECTED = "DUPLICATE_DETECTED"
CATEGORY_UNASSIGNED_REPORT = "UNASSIGNED_REPORT"
CATEGORY_SLA_WARNING = "SLA_WARNING"
CATEGORY_STATUS_CHANGED = "STATUS_CHANGED"
CATEGORY_SYSTEM_ALERT = "SYSTEM_ALERT"
CATEGORY_RESOLUTION_SUBMITTED = "RESOLUTION_SUBMITTED"
CATEGORY_CITIZEN_FEEDBACK_RECEIVED = "CITIZEN_FEEDBACK_RECEIVED"
CATEGORY_RESOLUTION_CONFIRMED = "RESOLUTION_CONFIRMED"
CATEGORY_RESOLUTION_NEEDS_ATTENTION = "RESOLUTION_NEEDS_ATTENTION"


def create_notification(
    category: str,
    title: str,
    message: str,
    ticket_id: Optional[str] = None,
    user_id: Optional[int] = None,
    severity: Optional[str] = None,
    department: Optional[str] = None,
    deduplicate: bool = True,
    app = None,
):
    """
    Create a persistent in-app notification with idempotent deduplication and real-time SSE dispatch.
    
    If user_id is None, it is an administrative operational alert.
    If user_id is set, it is scoped to that specific citizen.
    """
    from models import Notification, db
    from events import publish_notification_event

    # 1. Idempotency Check (Prevent alert spam)
    if deduplicate and ticket_id:
        existing = Notification.query.filter_by(
            ticket_id=ticket_id,
            category=category,
            user_id=user_id,
        ).first()
        if existing:
            # If already exists, avoid duplicate alert
            return existing

    notification = Notification(
        category=category,
        title=title,
        message=message,
        ticket_id=ticket_id,
        user_id=user_id,
        severity=severity,
        department=department,
        is_read=False,
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(notification)
    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error("Failed to commit notification: %s", exc)
        return None

    # Real-time SSE dispatch
    try:
        publish_notification_event(notification.to_dict(), app=app)
    except Exception as exc:
        logger.debug("SSE notification event publish failed: %s", exc)

    return notification


def trigger_high_severity_rule(complaint, app=None):
    """
    Operational Alert: High-severity incident detected.
    """
    title = f"High Severity Alert: #{complaint.id}"
    message = (
        f"A high-severity waste incident was verified at {complaint.address or 'reported location'}. "
        f"Department triage assigned to {complaint.department or 'Sanitation'}."
    )
    return create_notification(
        category=CATEGORY_NEW_HIGH_SEVERITY,
        title=title,
        message=message,
        ticket_id=complaint.id,
        user_id=None,  # Admin broadcast
        severity="High",
        department=complaint.department,
        deduplicate=True,
        app=app,
    )


def trigger_ai_failure_rule(complaint, error_msg=None, app=None):
    """
    Operational Alert: Automated AI vision processing encountered a failure.
    """
    title = f"AI Processing Failed: #{complaint.id}"
    err_text = error_msg or complaint.processing_error or "Inference pipeline failed."
    message = f"AI triage job failed for ticket #{complaint.id}. Reason: {err_text}. Manual inspection or retry required."
    return create_notification(
        category=CATEGORY_AI_PROCESSING_FAILED,
        title=title,
        message=message,
        ticket_id=complaint.id,
        user_id=None,  # Admin broadcast
        severity=complaint.severity_level,
        department=complaint.department,
        deduplicate=True,
        app=app,
    )


def trigger_duplicate_rule(complaint, duplicate_of_id, app=None):
    """
    Operational Alert: Geographically proximate duplicate report identified.
    """
    title = f"Duplicate Report Flagged: #{complaint.id}"
    message = (
        f"Complaint #{complaint.id} was identified as a spatial duplicate of existing report #{duplicate_of_id} "
        f"at {complaint.address or 'same coordinates'}."
    )
    return create_notification(
        category=CATEGORY_DUPLICATE_DETECTED,
        title=title,
        message=message,
        ticket_id=complaint.id,
        user_id=None,  # Admin broadcast
        severity=complaint.severity_level,
        department=complaint.department,
        deduplicate=True,
        app=app,
    )


def trigger_resolution_submitted_notification(complaint, resolution_note="", app=None):
    """
    Send in-app notification to citizen owner that field resolution evidence has been submitted.
    """
    if not complaint.user_id:
        return None
    note_snippet = f": '{resolution_note}'" if resolution_note else ""
    return create_notification(
        category=CATEGORY_RESOLUTION_SUBMITTED,
        title=f"Resolution Submitted: #{complaint.id}",
        message=f"The assigned department submitted resolution evidence for #{complaint.id}{note_snippet}. Please review and confirm or flag if it needs attention.",
        ticket_id=complaint.id,
        user_id=complaint.user_id,
        severity=complaint.severity_level,
        department=complaint.department,
        deduplicate=True,
        app=app,
    )


def trigger_citizen_feedback_notification(complaint, feedback, app=None):
    """
    Send operational alert to admin dispatcher when citizen submits feedback on resolution.
    """
    if feedback.result == "CONFIRMED":
        cat = CATEGORY_RESOLUTION_CONFIRMED
        title = f"Resolution Confirmed: #{complaint.id}"
        msg = f"Citizen confirmed resolution for Ticket #{complaint.id}. Issue is now marked as RESOLVED."
    else:
        cat = CATEGORY_RESOLUTION_NEEDS_ATTENTION
        title = f"Needs Attention: #{complaint.id}"
        comment_text = f" Citizen note: '{feedback.comment}'." if feedback.comment else ""
        msg = f"Citizen reported that Ticket #{complaint.id} still needs attention.{comment_text} Status returned to IN_PROGRESS."

    return create_notification(
        category=cat,
        title=title,
        message=msg,
        ticket_id=complaint.id,
        user_id=None,  # Admin broadcast
        severity=complaint.severity_level,
        department=complaint.department,
        deduplicate=False,
        app=app,
    )


def evaluate_aging_report_rules(
    app=None,
    unassigned_threshold_hours: int = 12,
    high_sev_threshold_hours: int = 6,
):
    """
    Evaluate operational age thresholds for active tickets and surface idempotent alerts.
    """
    from models import Complaint, db
    now = datetime.utcnow()
    created_alerts = []

    # 1. Unassigned reports exceeding threshold
    unassigned_cutoff = now - timedelta(hours=unassigned_threshold_hours)
    aging_unassigned = Complaint.query.filter(
        Complaint.status.in_(["SUBMITTED", "VERIFIED", "Open"]),
        (Complaint.department.is_(None) | Complaint.department.in_(["", "PENDING_TRIAGE"])),
        Complaint.created_at <= unassigned_cutoff,
    ).all()

    for c in aging_unassigned:
        title = f"Operational Age Threshold: Unassigned #{c.id}"
        msg = f"Report #{c.id} has remained unassigned for over {unassigned_threshold_hours}h. Triage dispatch required."
        notif = create_notification(
            category=CATEGORY_UNASSIGNED_REPORT,
            title=title,
            message=msg,
            ticket_id=c.id,
            user_id=None,
            severity=c.severity_level,
            department=c.department,
            deduplicate=True,
            app=app,
        )
        if notif:
            created_alerts.append(notif)

    # 2. High severity active exceeding threshold
    high_sev_cutoff = now - timedelta(hours=high_sev_threshold_hours)
    aging_high_sev = Complaint.query.filter(
        Complaint.severity_level == "High",
        ~Complaint.status.in_(["RESOLVED", "Resolved", "Closed", "REJECTED"]),
        Complaint.created_at <= high_sev_cutoff,
    ).all()

    for c in aging_high_sev:
        title = f"Operational Age Threshold: High Severity #{c.id}"
        msg = f"High-severity incident #{c.id} has remained unresolved for over {high_sev_threshold_hours}h."
        notif = create_notification(
            category=CATEGORY_SLA_WARNING,
            title=title,
            message=msg,
            ticket_id=c.id,
            user_id=None,
            severity="High",
            department=c.department,
            deduplicate=True,
            app=app,
        )
        if notif:
            created_alerts.append(notif)

    return created_alerts


# ---------------------------------------------------------------------------
# Notification Queries and Mutators
# ---------------------------------------------------------------------------

def get_admin_notifications(category: Optional[str] = None, unread_only: bool = False, limit: int = 50):
    from models import Notification
    q = Notification.query.filter(Notification.user_id.is_(None))
    if category:
        q = q.filter_by(category=category)
    if unread_only:
        q = q.filter_by(is_read=False)
    
    total = q.count()
    unread_count = Notification.query.filter(
        Notification.user_id.is_(None),
        Notification.is_read.is_(False)
    ).count()

    items = q.order_by(Notification.created_at.desc()).limit(limit).all()
    return {
        "notifications": [n.to_dict() for n in items],
        "unread_count": unread_count,
        "total": total,
    }


def get_user_notifications(user_id: int, unread_only: bool = False, limit: int = 50):
    from models import Notification
    q = Notification.query.filter_by(user_id=user_id)
    if unread_only:
        q = q.filter_by(is_read=False)

    total = q.count()
    unread_count = Notification.query.filter_by(user_id=user_id, is_read=False).count()

    items = q.order_by(Notification.created_at.desc()).limit(limit).all()
    return {
        "notifications": [n.to_dict() for n in items],
        "unread_count": unread_count,
        "total": total,
    }


def mark_notification_read(notification_id: int, user_id: Optional[int] = None):
    from models import Notification, db
    q = Notification.query.filter_by(id=notification_id)
    if user_id is not None:
        q = q.filter_by(user_id=user_id)
    else:
        # Admin marking admin operational notification
        q = q.filter(Notification.user_id.is_(None))

    notif = q.first()
    if not notif:
        return None

    notif.is_read = True
    db.session.commit()
    return notif


def mark_all_notifications_read(user_id: Optional[int] = None):
    from models import Notification, db
    q = Notification.query.filter_by(is_read=False)
    if user_id is not None:
        q = q.filter_by(user_id=user_id)
    else:
        q = q.filter(Notification.user_id.is_(None))

    count = q.update({"is_read": True})
    db.session.commit()
    return count


def notify_citizen(
    ticket_id: str,
    new_status: str,
    recipient_email: Optional[str] = None,
) -> dict:
    """
    Trigger a status-change notification for a complaint ticket.
    Updates external email/log, and creates an in-app citizen notification.
    """
    subject, body = _build_message(ticket_id, new_status)
    backend = os.environ.get("NOTIFY_BACKEND", "log").lower()

    delivered = False
    delivery_note = "log-only (no backend configured)"

    if recipient_email:
        if backend == "smtp":
            delivered = _send_smtp(recipient_email, subject, body)
            delivery_note = "smtp"
        elif backend == "sendgrid":
            delivered = _send_sendgrid(recipient_email, subject, body)
            delivery_note = "sendgrid"
        else:
            delivery_note = "log-only (NOTIFY_BACKEND not set)"
    else:
        delivery_note = "no recipient email — log-only"

    msg = (
        f"[{delivery_note}] Ticket #{ticket_id} → '{new_status}'"
        + (f" | to: {recipient_email}" if recipient_email else "")
    )
    logger.info(msg)

    # In-app citizen notification
    try:
        from models import Complaint
        complaint = Complaint.query.filter_by(id=ticket_id).first()
        if complaint and complaint.user_id:
            label = _STATUS_LABELS.get(new_status, f"status is now {new_status}")
            create_notification(
                category=CATEGORY_STATUS_CHANGED,
                title=f"Report #{ticket_id} {new_status}",
                message=f"Your report #{ticket_id} {label}.",
                ticket_id=ticket_id,
                user_id=complaint.user_id,
                severity=complaint.severity_level,
                department=complaint.department,
                deduplicate=False,
            )
    except Exception as exc:
        logger.debug("In-app citizen status notification creation skipped: %s", exc)

    return {
        "ticket_id": ticket_id,
        "new_status": new_status,
        "recipient": recipient_email or "unknown",
        "backend": delivery_note,
        "delivered": delivered,
        "message": msg,
    }


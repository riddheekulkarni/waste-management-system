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

def notify_citizen(
    ticket_id: str,
    new_status: str,
    recipient_email: Optional[str] = None,
) -> dict:
    """
    Trigger a status-change notification for a complaint ticket.

    Args:
        ticket_id:        Short ticket ID (e.g. "a1b2c3d4").
        new_status:       New complaint status string ("Open", "In Progress", "Resolved").
        recipient_email:  Citizen's email address.  When None the notification
                          is logged but not delivered (delivered=False).

    Returns:
        A dict with keys: ticket_id, new_status, recipient, delivered, message.
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

    return {
        "ticket_id": ticket_id,
        "new_status": new_status,
        "recipient": recipient_email or "unknown",
        "backend": delivery_note,
        "delivered": delivered,
        "message": msg,
    }

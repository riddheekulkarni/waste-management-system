"""
Notification dispatch engine.
Handles sending status update notifications to citizens (via log, email, or SMS).
"""

import logging

logger = logging.getLogger("ecoclean.notifications")
logger.setLevel(logging.INFO)


def notify_citizen(ticket_id: str, new_status: str, recipient_info: str = None) -> dict:
    """
    Trigger notification when a complaint ticket status changes.
    Can be configured to integrate with Twilio (SMS), SendGrid (Email), or FCM (Push).
    """
    msg = f"Notification Sent: Complaint Ticket #{ticket_id} status updated to '{new_status}'."
    logger.info(msg)

    return {
        "ticket_id": ticket_id,
        "new_status": new_status,
        "recipient": recipient_info or "Citizen",
        "delivered": True,
        "message": msg,
    }

from flask import Blueprint, jsonify, request, session
from routes.auth import login_required
from notifications import (
    get_user_notifications,
    mark_notification_read,
    mark_all_notifications_read,
)
from models import Notification

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


@notifications_bp.route("", methods=["GET"])
@login_required
def list_notifications():
    """
    List citizen-scoped notifications for authenticated user.
    """
    user_id = session.get("user_id")
    unread_only = request.args.get("unread_only", "").lower() in ("true", "1", "yes")
    limit = min(100, max(1, int(request.args.get("limit", 50))))

    data = get_user_notifications(user_id=user_id, unread_only=unread_only, limit=limit)
    return jsonify({
        **data,
        "status_code": 200,
    }), 200


@notifications_bp.route("/<int:notification_id>/read", methods=["PATCH"])
@login_required
def mark_read(notification_id):
    """
    Mark a citizen notification as read. Strictly scopes to authenticated user.
    """
    user_id = session.get("user_id")
    notif = mark_notification_read(notification_id, user_id=user_id)
    if not notif:
        return jsonify({
            "error": "Notification not found or access denied.",
            "status_code": 404,
        }), 404

    unread_count = Notification.query.filter_by(user_id=user_id, is_read=False).count()
    return jsonify({
        "notification": notif.to_dict(),
        "unread_count": unread_count,
        "status_code": 200,
    }), 200


@notifications_bp.route("/read-all", methods=["POST"])
@login_required
def read_all():
    """
    Mark all unread notifications for authenticated citizen as read.
    """
    user_id = session.get("user_id")
    marked_count = mark_all_notifications_read(user_id=user_id)
    return jsonify({
        "marked_read": marked_count,
        "unread_count": 0,
        "status_code": 200,
    }), 200

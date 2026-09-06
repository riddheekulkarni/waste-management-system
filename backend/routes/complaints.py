import os
import uuid
from flask import Blueprint, current_app, jsonify, request, session
from werkzeug.utils import secure_filename

from detection import WasteDetector
from models import Complaint, DetectionItem, db
from notifications import notify_citizen
from routes.auth import require_role
from routing import determine_department
from severity import compute_severity

complaints_bp = Blueprint("complaints", __name__, url_prefix="/api/complaints")

_detector = None


def get_detector() -> WasteDetector:
    """Lazily build the detector once, using the weights path from config."""
    global _detector
    if _detector is None:
        _detector = WasteDetector(weights_path=current_app.config.get("WASTE_MODEL_WEIGHTS"))
    return _detector


def allowed_file(filename: str) -> bool:
    allowed = current_app.config.get("ALLOWED_EXTENSIONS", {"png", "jpg", "jpeg", "webp"})
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed


def find_nearby_duplicate(lat: float, lng: float, radius_meters: float = 50.0):
    """Find recent open complaint within radius_meters."""
    if lat is None or lng is None:
        return None

    open_complaints = Complaint.query.filter(
        Complaint.status != "Resolved",
        Complaint.latitude.isnot(None),
        Complaint.longitude.isnot(None)
    ).all()

    for c in open_complaints:
        dist = Complaint.haversine_distance(lat, lng, c.latitude, c.longitude)
        if dist <= radius_meters:
            return c
    return None


@complaints_bp.route("/upload", methods=["POST"])
def upload_complaint():
    if "image" not in request.files:
        return jsonify({"error": "No image file provided (field name 'image')"}), 400

    image_file = request.files["image"]
    if image_file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    if not allowed_file(image_file.filename):
        return jsonify({"error": "Invalid file type. Allowed formats: PNG, JPG, JPEG, WEBP, GIF."}), 400

    safe_fname = secure_filename(image_file.filename) or "waste_upload.jpg"
    filename = f"{uuid.uuid4().hex}_{safe_fname}"
    save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    image_file.save(save_path)

    detector = get_detector()
    if not detector.validate_image(save_path):
        if os.path.exists(save_path):
            os.remove(save_path)
        return jsonify({"error": "Uploaded file is not a valid or readable image."}), 400

    latitude = request.form.get("latitude", type=float)
    longitude = request.form.get("longitude", type=float)
    address = request.form.get("address", type=str)

    user_id = session.get("user_id")

    detections, image_size = detector.detect(save_path)
    severity = compute_severity(detections, image_size)
    department = determine_department(detections)

    # Duplicate complaint check
    duplicate_ticket = find_nearby_duplicate(latitude, longitude, radius_meters=50.0)
    is_duplicate = duplicate_ticket is not None
    duplicate_of_id = duplicate_ticket.id if duplicate_ticket else None

    complaint = Complaint(
        user_id=user_id,
        image_path=filename,
        address=address,
        latitude=latitude,
        longitude=longitude,
        severity_level=severity["level"],
        coverage_ratio=severity["coverage_ratio"],
        item_count=severity["item_count"],
        department=department,
        status="Open",
        is_duplicate=is_duplicate,
        duplicate_of_id=duplicate_of_id,
    )
    complaint.id = str(uuid.uuid4())[:8]

    for d in detections:
        complaint.detections.append(DetectionItem(
            cls=d.cls, confidence=d.confidence,
            x1=d.box[0], y1=d.box[1], x2=d.box[2], y2=d.box[3],
        ))

    db.session.add(complaint)
    db.session.commit()

    res_data = complaint.to_dict()
    if is_duplicate:
        res_data["duplicate_warning"] = (
            f"Note: An existing complaint (Ticket #{duplicate_of_id}) was reported nearby. "
            "Your ticket has been linked to prevent redundant municipal dispatches."
        )

    return jsonify(res_data), 201


@complaints_bp.route("/check-duplicate", methods=["POST"])
def check_duplicate():
    data = request.get_json() or {}
    lat = data.get("latitude")
    lng = data.get("longitude")

    if lat is None or lng is None:
        return jsonify({"is_duplicate": False, "nearby_ticket": None})

    duplicate = find_nearby_duplicate(float(lat), float(lng), radius_meters=50.0)
    if duplicate:
        return jsonify({
            "is_duplicate": True,
            "nearby_ticket": duplicate.to_dict(include_detections=False)
        })

    return jsonify({"is_duplicate": False, "nearby_ticket": None})


@complaints_bp.route("", methods=["GET"])
def list_complaints():
    query = Complaint.query

    status = request.args.get("status")
    department = request.args.get("department")
    severity_level = request.args.get("severity")
    only_mine = request.args.get("my_complaints")

    if only_mine and session.get("user_id"):
        query = query.filter_by(user_id=session.get("user_id"))

    if status:
        query = query.filter_by(status=status)
    if department:
        query = query.filter_by(department=department)
    if severity_level:
        query = query.filter_by(severity_level=severity_level)

    complaints = query.order_by(Complaint.created_at.desc()).all()
    return jsonify([c.to_dict(include_detections=True) for c in complaints])


@complaints_bp.route("/<ticket_id>", methods=["GET"])
def get_complaint(ticket_id):
    complaint = db.session.get(Complaint, ticket_id)
    if not complaint:
        return jsonify({"error": "Ticket not found"}), 404
    return jsonify(complaint.to_dict())


@complaints_bp.route("/<ticket_id>/status", methods=["PATCH"])
@require_role("admin")
def update_status(ticket_id):
    if not request.is_json or "status" not in request.json:
        return jsonify({"error": "Provide JSON body: {'status': '...'}"}), 400

    complaint = db.session.get(Complaint, ticket_id)
    if not complaint:
        return jsonify({"error": "Ticket not found"}), 404

    new_status = request.json["status"]
    if new_status not in ("Open", "In Progress", "Resolved"):
        return jsonify({"error": "status must be Open, In Progress, or Resolved"}), 400

    complaint.status = new_status
    db.session.commit()

    # Trigger notification
    notification_result = notify_citizen(complaint.id, new_status)
    res_dict = complaint.to_dict()
    res_dict["notification"] = notification_result

    return jsonify(res_dict)



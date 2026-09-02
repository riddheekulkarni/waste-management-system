import os
import uuid

from flask import Blueprint, current_app, jsonify, request, session

from detection import WasteDetector
from models import Complaint, DetectionItem, db
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


@complaints_bp.route("/upload", methods=["POST"])
def upload_complaint():
    if "image" not in request.files:
        return jsonify({"error": "No image file provided (field name 'image')"}), 400

    image_file = request.files["image"]
    if image_file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    filename = f"{uuid.uuid4().hex}_{image_file.filename}"
    save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    image_file.save(save_path)

    latitude = request.form.get("latitude", type=float)
    longitude = request.form.get("longitude", type=float)
    address = request.form.get("address", type=str)

    user_id = session.get("user_id")

    detector = get_detector()
    detections, image_size = detector.detect(save_path)
    severity = compute_severity(detections, image_size)
    department = determine_department(detections)

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
    )
    complaint.id = str(uuid.uuid4())[:8]

    for d in detections:
        complaint.detections.append(DetectionItem(
            cls=d.cls, confidence=d.confidence,
            x1=d.box[0], y1=d.box[1], x2=d.box[2], y2=d.box[3],
        ))

    db.session.add(complaint)
    db.session.commit()

    return jsonify(complaint.to_dict()), 201


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
    complaint = Complaint.query.get(ticket_id)
    if not complaint:
        return jsonify({"error": "Ticket not found"}), 404
    return jsonify(complaint.to_dict())


@complaints_bp.route("/<ticket_id>/status", methods=["PATCH"])
def update_status(ticket_id):
    # Role guard — only admins may change ticket status
    if session.get("role") != "admin":
        return jsonify({"error": "Admin access required to update ticket status."}), 403

    if not request.is_json or "status" not in request.json:
        return jsonify({"error": "Provide JSON body: {'status': '...'}"}), 400

    complaint = Complaint.query.get(ticket_id)
    if not complaint:
        return jsonify({"error": "Ticket not found"}), 404

    new_status = request.json["status"]
    if new_status not in ("Open", "In Progress", "Resolved"):
        return jsonify({"error": "status must be Open, In Progress, or Resolved"}), 400

    complaint.status = new_status
    db.session.commit()
    return jsonify(complaint.to_dict())


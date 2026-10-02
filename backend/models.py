import math
import os
import uuid
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="citizen")  # "citizen" or "admin"
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    complaints = db.relationship("Complaint", backref="user", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Complaint(db.Model):
    __tablename__ = "complaints"

    id = db.Column(db.String(8), primary_key=True, default=lambda: str(uuid.uuid4())[:8])
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    image_path = db.Column(db.String(255))
    address = db.Column(db.Text, nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    severity_level = db.Column(db.String(10))       # Low / Medium / High
    coverage_ratio = db.Column(db.Float)             # 0.0 - 1.0
    item_count = db.Column(db.Integer)

    department = db.Column(db.String(64), index=True)
    status = db.Column(db.String(32), default="AI_PROCESSING", index=True)

    is_duplicate = db.Column(db.Boolean, default=False, index=True)
    duplicate_of_id = db.Column(db.String(8), nullable=True)

    ai_mode = db.Column(db.String(20), default="MOCK_DEMO")  # "REAL_YOLO" or "MOCK_DEMO"

    # ── Phase 3 Async Processing Metadata ────────────────────────────────────
    processing_status = db.Column(db.String(32), default="QUEUED", index=True)
    processing_started_at = db.Column(db.DateTime, nullable=True)
    processing_completed_at = db.Column(db.DateTime, nullable=True)
    processing_duration_ms = db.Column(db.Integer, nullable=True)
    processing_error = db.Column(db.String(255), nullable=True)
    model_name = db.Column(db.String(64), nullable=True)
    model_version = db.Column(db.String(32), nullable=True)
    retry_count = db.Column(db.Integer, default=0, nullable=False)

    __table_args__ = (
        db.Index("idx_complaints_lat_lng", "latitude", "longitude"),
        db.Index("idx_complaints_proc_status", "processing_status"),
    )

    detections = db.relationship(
        "DetectionItem", backref="complaint", cascade="all, delete-orphan"
    )

    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate great circle distance between two points in meters."""
        if any(v is None for v in (lat1, lon1, lat2, lon2)):
            return float("inf")
        r = 6371000.0  # Earth's radius in meters
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
        return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    def to_dict(self, include_detections=True):
        detected_classes = sorted(list(set(d.cls for d in self.detections))) if self.detections else []
        mode = self.ai_mode or "MOCK_DEMO"
        mode_label = "REAL AI / YOLOv8" if mode == "REAL_YOLO" else "DEMO / MOCK DETECTION"

        data = {
            "id": self.id,
            "ticket_id": self.id,
            "user_id": self.user_id,
            "submitted_by": self.user.username if self.user else "Citizen (Guest)",
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "image_path": self.image_path,
            "address": self.address or "Location specified on map",
            "latitude": self.latitude,
            "longitude": self.longitude,
            "severity": {
                "level": self.severity_level or "PENDING",
                "coverage_ratio": round(self.coverage_ratio, 4) if self.coverage_ratio is not None else 0.0,
                "item_count": self.item_count or 0,
                "detected_classes": detected_classes,
            },
            "department": self.department or "PENDING_TRIAGE",
            "status": self.status,
            "is_duplicate": bool(self.is_duplicate),
            "duplicate_of_id": self.duplicate_of_id,
            "ai_mode": mode,
            "ai_mode_label": mode_label,
            # Phase 3 asynchronous processing metadata
            "processing_status": self.processing_status or "QUEUED",
            "processing_started_at": self.processing_started_at.isoformat() if self.processing_started_at else None,
            "processing_completed_at": self.processing_completed_at.isoformat() if self.processing_completed_at else None,
            "processing_duration_ms": self.processing_duration_ms,
            "processing_error": self.processing_error,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "retry_count": self.retry_count,
        }
        annotated_name = f"annotated_{self.image_path}"
        annotated_path = os.path.join(os.path.dirname(__file__), "uploads", annotated_name)
        data["annotated_image_path"] = annotated_name if os.path.exists(annotated_path) else None

        if include_detections:
            data["detections"] = [d.to_dict() for d in self.detections]
        return data



class DetectionItem(db.Model):
    __tablename__ = "detection_items"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    complaint_id = db.Column(db.String(8), db.ForeignKey("complaints.id"), nullable=False, index=True)

    cls = db.Column(db.String(50), index=True)
    confidence = db.Column(db.Float)
    x1 = db.Column(db.Float)
    y1 = db.Column(db.Float)
    x2 = db.Column(db.Float)
    y2 = db.Column(db.Float)

    def to_dict(self):
        return {
            "class": self.cls,
            "confidence": self.confidence,
            "box": [self.x1, self.y1, self.x2, self.y2],
        }


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
            "created_at": self.created_at.isoformat(),
        }


class Complaint(db.Model):
    __tablename__ = "complaints"

    id = db.Column(db.String(8), primary_key=True, default=lambda: str(uuid.uuid4())[:8])
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    image_path = db.Column(db.String(255))
    address = db.Column(db.Text, nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    severity_level = db.Column(db.String(10))       # Low / Medium / High
    coverage_ratio = db.Column(db.Float)             # 0.0 - 1.0
    item_count = db.Column(db.Integer)

    department = db.Column(db.String(64))
    status = db.Column(db.String(20), default="Open")  # Open / In Progress / Resolved

    detections = db.relationship(
        "DetectionItem", backref="complaint", cascade="all, delete-orphan"
    )

    def to_dict(self, include_detections=True):
        data = {
            "ticket_id": self.id,
            "user_id": self.user_id,
            "submitted_by": self.user.username if self.user else "Citizen (Guest)",
            "created_at": self.created_at.isoformat(),
            "image_path": self.image_path,
            "address": self.address or "Location specified on map",
            "latitude": self.latitude,
            "longitude": self.longitude,
            "severity": {
                "level": self.severity_level,
                "coverage_ratio": round(self.coverage_ratio, 4) if self.coverage_ratio is not None else None,
                "item_count": self.item_count,
            },
            "department": self.department,
            "status": self.status,
        }
        if include_detections:
            data["detections"] = [d.to_dict() for d in self.detections]
        return data


class DetectionItem(db.Model):
    __tablename__ = "detection_items"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    complaint_id = db.Column(db.String(8), db.ForeignKey("complaints.id"), nullable=False)

    cls = db.Column(db.String(50))
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


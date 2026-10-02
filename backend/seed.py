"""
Controlled database seeding script for EcoClean Civic development & demo environments.

WARNING:
This script is intended strictly for local development and testing.
DO NOT RUN IN PRODUCTION. Never use default or demo credentials in production.

Usage:
    python backend/seed.py
    flask seed-db
"""

import os
import sys

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import User, Complaint, DetectionItem, db


def seed_database(app=None):
    if app is None:
        app = create_app()

    with app.app_context():
        # Safeguard: Refuse to seed if FLASK_ENV is production unless explicitly forced
        if app.config.get("IS_PRODUCTION") and not os.environ.get("ALLOW_PRODUCTION_SEED"):
            print("❌ ABORTED: Refusing to seed database in production environment.")
            print("Set ALLOW_PRODUCTION_SEED=true only if you explicitly intend to create these users.")
            return False

        print("🌱 Seeding demo database accounts for EcoClean Civic...")

        admin_pass = os.environ.get("DEMO_ADMIN_PASSWORD", "admin123")
        citizen_pass = os.environ.get("DEMO_CITIZEN_PASSWORD", "citizen123")

        created_count = 0

        admin = User.query.filter_by(username="admin").first()
        if not admin:
            admin = User(
                username="admin",
                email="admin@civic.gov",
                role="admin",
            )
            admin.set_password(admin_pass)
            db.session.add(admin)
            created_count += 1
            print(f"  ✅ Created demo admin user: admin@civic.gov (password: {admin_pass})")
        else:
            print("  ℹ️  Demo admin user already exists.")

        citizen = User.query.filter_by(username="citizen").first()
        if not citizen:
            citizen = User(
                username="citizen",
                email="citizen@civic.gov",
                role="citizen",
            )
            citizen.set_password(citizen_pass)
            db.session.add(citizen)
            created_count += 1
            print(f"  ✅ Created demo citizen user: citizen@civic.gov (password: {citizen_pass})")
        else:
            print("  ℹ️  Demo citizen user already exists.")

        db.session.commit()

        # Seed sample complaints if table is empty
        if Complaint.query.count() == 0:
            from datetime import datetime, timedelta, timezone
            from models import Notification

            now = datetime.now(timezone.utc)
            sample_complaints = [
                Complaint(
                    id="ECC1001",
                    user_id=citizen.id,
                    address="Shivajinagar Bus Station, Pune",
                    latitude=18.5314,
                    longitude=73.8446,
                    severity_level="High",
                    coverage_ratio=0.45,
                    item_count=6,
                    department="Sanitation Department",
                    status="IN_PROGRESS",
                    ai_mode="REAL_YOLO",
                    processing_status="COMPLETED",
                    created_at=now - timedelta(hours=8),
                    processing_started_at=now - timedelta(hours=7, minutes=59),
                    processing_completed_at=now - timedelta(hours=7, minutes=58),
                ),
                Complaint(
                    id="ECC1002",
                    user_id=citizen.id,
                    address="FC Road Market, Pune",
                    latitude=18.5246,
                    longitude=73.8415,
                    severity_level="Medium",
                    coverage_ratio=0.22,
                    item_count=4,
                    department="Recycling Department",
                    status="VERIFIED",
                    ai_mode="REAL_YOLO",
                    processing_status="COMPLETED",
                    created_at=now - timedelta(hours=14),
                    processing_started_at=now - timedelta(hours=13, minutes=59),
                    processing_completed_at=now - timedelta(hours=13, minutes=58),
                ),
                Complaint(
                    id="ECC1003",
                    user_id=citizen.id,
                    address="Kothrud Industrial Area, Pune",
                    latitude=18.5074,
                    longitude=73.8077,
                    severity_level="High",
                    coverage_ratio=0.55,
                    item_count=8,
                    department="Health & Hazmat Department",
                    status="VERIFIED",
                    ai_mode="MOCK_DEMO",
                    processing_status="COMPLETED",
                    created_at=now - timedelta(hours=18),
                    processing_started_at=now - timedelta(hours=17, minutes=59),
                    processing_completed_at=now - timedelta(hours=17, minutes=58),
                ),
                Complaint(
                    id="ECC1004",
                    user_id=citizen.id,
                    address="JM Road Corner, Pune",
                    latitude=18.5204,
                    longitude=73.8567,
                    severity_level="Low",
                    coverage_ratio=0.10,
                    item_count=2,
                    department="Public Works Department",
                    status="RESOLVED",
                    ai_mode="REAL_YOLO",
                    processing_status="COMPLETED",
                    created_at=now - timedelta(days=2),
                    processing_started_at=now - timedelta(days=2, minutes=-1),
                    processing_completed_at=now - timedelta(days=2, minutes=-2),
                ),
                Complaint(
                    id="ECC1005",
                    user_id=citizen.id,
                    address="Deccan Gymkhana, Pune",
                    latitude=18.5173,
                    longitude=73.8418,
                    severity_level="High",
                    coverage_ratio=0.38,
                    item_count=5,
                    department=None,
                    status="VERIFIED",
                    ai_mode="REAL_YOLO",
                    processing_status="COMPLETED",
                    created_at=now - timedelta(hours=16),
                ),
                Complaint(
                    id="ECC1006",
                    user_id=citizen.id,
                    address="JM Road Corner (Recurring), Pune",
                    latitude=18.5205,
                    longitude=73.8568,
                    severity_level="Medium",
                    coverage_ratio=0.25,
                    item_count=3,
                    department="Sanitation Department",
                    status="IN_PROGRESS",
                    ai_mode="REAL_YOLO",
                    processing_status="COMPLETED",
                    created_at=now - timedelta(hours=4),
                ),
            ]

            for c in sample_complaints:
                db.session.add(c)
                det = DetectionItem(
                    complaint_id=c.id,
                    cls="plastic_bottle",
                    confidence=0.88,
                    x1=10,
                    y1=10,
                    x2=100,
                    y2=100,
                )
                db.session.add(det)

            # Sample notifications
            sample_notifs = [
                Notification(
                    category="NEW_HIGH_SEVERITY",
                    title="Critical Hazmat Incident Reported",
                    message="High-severity hazardous waste detected at Kothrud Industrial Area (Ticket #ECC1003).",
                    ticket_id="ECC1003",
                    severity="High",
                    department="Health & Hazmat Department",
                    is_read=False,
                    created_at=now - timedelta(hours=17),
                ),
                Notification(
                    category="UNASSIGNED_REPORT",
                    title="Operational Age Warning: Unassigned Ticket",
                    message="Ticket #ECC1005 at Deccan Gymkhana has been verified for 16h without department allocation.",
                    ticket_id="ECC1005",
                    severity="High",
                    is_read=False,
                    created_at=now - timedelta(hours=4),
                ),
                Notification(
                    user_id=citizen.id,
                    category="STATUS_CHANGED",
                    title="Report #ECC1001 Verified & In Progress",
                    message="Your report for Shivajinagar Bus Station has been verified and assigned to the Sanitation Department.",
                    ticket_id="ECC1001",
                    severity="High",
                    department="Sanitation Department",
                    is_read=False,
                    created_at=now - timedelta(hours=7),
                ),
            ]
            for n in sample_notifs:
                db.session.add(n)

            db.session.commit()
            print("  ✅ Seeded 6 realistic demonstration complaints and 3 operational notifications.")

        print(f"✨ Seeding complete. {created_count} new demo user(s) created.")
        print("⚠️  REMINDER: These demo credentials must not be deployed to public or production servers.\n")
        return True


if __name__ == "__main__":
    seed_database()

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
        print(f"✨ Seeding complete. {created_count} new demo user(s) created.")
        print("⚠️  REMINDER: These demo credentials must not be deployed to public or production servers.\n")
        return True


if __name__ == "__main__":
    seed_database()

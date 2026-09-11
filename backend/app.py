import logging
import os
import sqlite3

from flask import Flask, send_from_directory

from config import Config
from models import User, db
from routes.analytics import analytics_bp
from routes.auth import auth_bp
from routes.complaints import complaints_bp

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

logger = logging.getLogger(__name__)


def ensure_sqlite_schema(app):
    """Upgrade existing SQLite databases with newly added complaint columns."""
    bind = db.session.get_bind()
    if bind is None or not str(bind.url).startswith("sqlite"):
        return

    db_path = bind.url.database
    if not db_path or not os.path.exists(db_path):
        return

    try:
        conn = sqlite3.connect(db_path)
        columns = [row[1] for row in conn.execute("PRAGMA table_info(complaints)")]

        if "is_duplicate" not in columns:
            conn.execute("ALTER TABLE complaints ADD COLUMN is_duplicate BOOLEAN DEFAULT 0")
        if "duplicate_of_id" not in columns:
            conn.execute("ALTER TABLE complaints ADD COLUMN duplicate_of_id VARCHAR(8)")

        conn.commit()
    except sqlite3.Error as exc:
        logger.warning("Schema migration skipped for SQLite database %s: %s", db_path, exc)
    finally:
        conn.close()


def seed_default_users():
    """Ensure default Admin and Citizen accounts exist for testing."""
    if not User.query.filter_by(role="admin").first():
        admin = User(username="admin", email="admin@civic.gov", role="admin")
        admin.set_password("admin123")
        db.session.add(admin)

    if not User.query.filter_by(role="citizen").first():
        citizen = User(username="citizen", email="citizen@civic.gov", role="citizen")
        citizen.set_password("citizen123")
        db.session.add(citizen)

    db.session.commit()


def create_app():
    app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
    app.config.from_object(Config)
    app.secret_key = os.environ.get("SECRET_KEY", "eco-clean-civic-secret-key-2026")

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    with app.app_context():
        db.create_all()
        ensure_sqlite_schema(app)
        seed_default_users()

    app.register_blueprint(auth_bp)
    app.register_blueprint(complaints_bp)
    app.register_blueprint(analytics_bp)

    # Log which detection mode is active so operators can confirm at startup
    _weights = app.config.get("WASTE_MODEL_WEIGHTS") or ""
    if _weights and os.path.exists(_weights):
        logger.info("🤖 WasteDetector: REAL mode — weights: %s", _weights)
    else:
        logger.info(
            "⚠️  WasteDetector: MOCK mode (no valid WASTE_MODEL_WEIGHTS). "
            "Set WASTE_MODEL_WEIGHTS=/path/to/best.pt to enable real inference."
        )

    @app.route("/")
    def index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5050)


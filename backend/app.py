import logging
import math
import os

from flask import Flask, jsonify, request, send_from_directory, session

from config import Config
from extensions import limiter, migrate
from models import Complaint, User, db
from routes.analytics import analytics_bp
from routes.auth import auth_bp
from routes.complaints import complaints_bp

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
    app.config.from_object(Config)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    migrate.init_app(
        app,
        db,
        directory=os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations"),
    )

    with app.app_context():
        # In non-production testing or initial dev environments, create missing tables safely
        if not app.config.get("IS_PRODUCTION"):
            db.create_all()

    # ── Rate Limiter ───────────────────────────────────────────────────────
    limiter.enabled = app.config.get("RATELIMIT_ENABLED", True)
    limiter.storage_uri = app.config.get("RATELIMIT_STORAGE_URL", "memory://")
    limiter.default_limits = [app.config.get("RATELIMIT_DEFAULT", "200 per day;50 per hour")]
    limiter.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(complaints_bp)
    app.register_blueprint(analytics_bp)

    # ── CLI Commands ───────────────────────────────────────────────────────
    @app.cli.command("seed-db")
    def seed_db_command():
        """Seed development database with demo accounts."""
        from seed import seed_database
        seed_database(app)

    # ── Error Handlers for API Consistency ─────────────────────────────────
    for status_code in (400, 401, 403, 404, 413, 429, 500):
        def _make_handler(code):
            def handler(err):
                if request.path.startswith("/api/") or request.path.startswith("/uploads/"):
                    message = getattr(err, "description", str(err))
                    return jsonify({"error": message, "status_code": code}), code
                return err
            return handler

        app.register_error_handler(status_code, _make_handler(status_code))

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

    # ── Secured Image Serving Route (Task 5 & 6) ───────────────────────────
    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename):
        # 1. Path traversal mitigation: only allow pure basenames
        safe_name = os.path.basename(filename)
        if not safe_name or safe_name != filename or ".." in filename:
            return jsonify({"error": "Invalid or unsafe filename requested.", "status_code": 400}), 400

        # 2. Authentication & Authorization Enforcement (checked before filesystem probe)
        user_id = session.get("user_id")
        role = session.get("role")

        if not user_id:
            return jsonify({
                "error": "Authentication required to access complaint image evidence.",
                "status_code": 401
            }), 401

        target_path = os.path.join(app.config["UPLOAD_FOLDER"], safe_name)
        if not os.path.exists(target_path):
            return jsonify({"error": "Requested image file not found.", "status_code": 404}), 404

        # Municipal admins can view all complaint images
        if role == "admin":
            return send_from_directory(app.config["UPLOAD_FOLDER"], safe_name)

        # Citizens may strictly access only images belonging to their own complaints
        clean_name = safe_name[len("annotated_"):] if safe_name.startswith("annotated_") else safe_name
        complaint = Complaint.query.filter_by(image_path=clean_name).first()
        if not complaint or complaint.user_id != user_id:
            return jsonify({
                "error": "Access denied. You may only view images from your own complaints.",
                "status_code": 403
            }), 403

        return send_from_directory(app.config["UPLOAD_FOLDER"], safe_name)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5050)

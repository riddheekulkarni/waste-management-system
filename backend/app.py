import os

from flask import Flask, send_from_directory

from config import Config
from models import User, db
from routes.analytics import analytics_bp
from routes.auth import auth_bp
from routes.complaints import complaints_bp

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")


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
        seed_default_users()

    app.register_blueprint(auth_bp)
    app.register_blueprint(complaints_bp)
    app.register_blueprint(analytics_bp)

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


"""
Application configuration.

All tuneable values are read from environment variables so the same image
runs in dev (SQLite, debug) and production (PostgreSQL, Gunicorn) without
any code changes.  See .env.example for the full list of supported variables.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:
    pass


class Config:
    # ── Security ──────────────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get("SECRET_KEY", "eco-clean-civic-secret-key-2026")
    # Session cookie is HTTP-only and not sent over plain HTTP in production.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"

    # ── Database ──────────────────────────────────────────────────────────────
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(BASE_DIR, "waste_management.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Recycle DB connections every 5 minutes to avoid stale-connection errors
    # on PostgreSQL (especially after container restarts).
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }

    # ── File Uploads ──────────────────────────────────────────────────────────
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    # Hard limit: 16 MB per request.  Flask rejects larger payloads with 413
    # before any application code runs — protects against memory exhaustion.
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_UPLOAD_MB", 16)) * 1024 * 1024
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

    # ── Waste Detection ───────────────────────────────────────────────────────
    # Set WASTE_MODEL_WEIGHTS to the absolute path of a trained best.pt file.
    # If unset, auto-checks project root, backend folder, and models/ folder.
    # Falls back to mock-detection mode if no weights are found.
    _candidate_weights = [
        os.environ.get("WASTE_MODEL_WEIGHTS"),
        os.path.join(PROJECT_ROOT, "best.pt"),
        os.path.join(BASE_DIR, "best.pt"),
        os.path.join(PROJECT_ROOT, "models", "best.pt"),
    ]
    WASTE_MODEL_WEIGHTS = next((w for w in _candidate_weights if w and os.path.exists(w)), None)

    # ── Rate Limiting (flask-limiter) ─────────────────────────────────────────
    # Toggled to False in tests via app.config["RATELIMIT_ENABLED"] = False.
    RATELIMIT_ENABLED = os.environ.get("RATELIMIT_ENABLED", "true").lower() != "false"
    RATELIMIT_STORAGE_URL = os.environ.get("RATELIMIT_STORAGE_URL", "memory://")
    # Default global limit — protects all routes.
    RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "200 per day;50 per hour")

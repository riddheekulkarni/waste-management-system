"""
Application configuration.

All tuneable values are read from environment variables so the same image
runs in dev (SQLite, debug) and production (PostgreSQL, Gunicorn) without
any code changes.  See .env.example for the full list of supported variables.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


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
    # Leave blank (or unset) to run in mock-detection mode (safe for demos).
    WASTE_MODEL_WEIGHTS = os.environ.get("WASTE_MODEL_WEIGHTS") or None

    # ── Rate Limiting (flask-limiter) ─────────────────────────────────────────
    # Toggled to False in tests via app.config["RATELIMIT_ENABLED"] = False.
    RATELIMIT_ENABLED = os.environ.get("RATELIMIT_ENABLED", "true").lower() != "false"
    RATELIMIT_STORAGE_URL = os.environ.get("RATELIMIT_STORAGE_URL", "memory://")
    # Default global limit — protects all routes.
    RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "200 per day;50 per hour")

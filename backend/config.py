"""
Application configuration.

All tuneable values are read from environment variables so the same image
runs in dev (SQLite, debug) and production (PostgreSQL, Gunicorn) without
any code changes.  See .env.example for the full list of supported variables.
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:
    pass


class Config:
    # ── Environment ───────────────────────────────────────────────────────────
    FLASK_ENV = os.environ.get("FLASK_ENV", "development").lower()
    IS_PRODUCTION = FLASK_ENV == "production"

    # ── Security ──────────────────────────────────────────────────────────────
    _raw_secret = os.environ.get("SECRET_KEY")
    if IS_PRODUCTION:
        if not _raw_secret or _raw_secret in ("eco-clean-civic-secret-key-2026", "secret", "change-me"):
            raise ValueError(
                "CRITICAL SECURITY CONFIGURATION ERROR: SECRET_KEY environment variable "
                "must be explicitly set to a cryptographically random secret in production."
            )
        SECRET_KEY = _raw_secret
    else:
        SECRET_KEY = _raw_secret or "eco-clean-civic-dev-fallback-key-2026"

    # Session cookie is HTTP-only and not sent over plain HTTP in production.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = IS_PRODUCTION

    # ── Database ──────────────────────────────────────────────────────────────
    _raw_db_url = os.environ.get("DATABASE_URL")
    if IS_PRODUCTION and not _raw_db_url:
        raise ValueError(
            "CRITICAL CONFIGURATION ERROR: DATABASE_URL environment variable "
            "must be explicitly provided in production mode (e.g. PostgreSQL connection string)."
        )

    # Normalize potential postgres:// to postgresql:// for SQLAlchemy 1.4+
    if _raw_db_url and _raw_db_url.startswith("postgres://"):
        _raw_db_url = _raw_db_url.replace("postgres://", "postgresql://", 1)

    # Normalize relative SQLite paths so database resolution is consistent regardless of working directory
    if _raw_db_url and _raw_db_url.startswith("sqlite:///"):
        _db_path = _raw_db_url[len("sqlite:///"):]
        if not os.path.isabs(_db_path) and _db_path != ":memory:":
            _raw_db_url = "sqlite:///" + os.path.abspath(os.path.join(BASE_DIR, _db_path)).replace("\\", "/")

    SQLALCHEMY_DATABASE_URI = _raw_db_url or (
        "sqlite:///" + os.path.join(BASE_DIR, "waste_management.db").replace("\\", "/")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }

    # ── File Uploads ──────────────────────────────────────────────────────────
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_UPLOAD_MB", 16)) * 1024 * 1024
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

    # ── Waste & Infrastructure Detection Weights ──────────────────────────────
    _candidate_weights = [
        os.environ.get("WASTE_MODEL_WEIGHTS"),
        os.path.join(PROJECT_ROOT, "best.pt"),
        os.path.join(BASE_DIR, "best.pt"),
        os.path.join(PROJECT_ROOT, "models", "best.pt"),
    ]
    WASTE_MODEL_WEIGHTS = next((w for w in _candidate_weights if w and os.path.exists(w)), None)
    YOLO_METRICS_DIR = os.environ.get("YOLO_METRICS_DIR") or os.path.join(
        PROJECT_ROOT, "runs", "waste_yolov8s"
    )

    _candidate_pothole_weights = [
        os.environ.get("POTHOLE_MODEL_WEIGHTS"),
        os.path.join(PROJECT_ROOT, "pothole_model.pt"),
        os.path.join(BASE_DIR, "pothole_model.pt"),
        os.path.join(PROJECT_ROOT, "models", "pothole_model.pt"),
    ]
    POTHOLE_MODEL_WEIGHTS = next((p for p in _candidate_pothole_weights if p and os.path.exists(p)), None)

    # ── AI Pipeline Execution Mode ──────────────────────────────────────────
    AI_EXECUTION_MODE = os.environ.get("AI_EXECUTION_MODE", "REAL_YOLO")

    # ── Background Worker & Job Queue (RQ + Redis) ──────────────────────────
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    ASYNC_MODE = os.environ.get("ASYNC_MODE", "redis").lower()
    JOB_TIMEOUT = int(os.environ.get("JOB_TIMEOUT", 180))

    # ── Rate Limiting (flask-limiter) ─────────────────────────────────────────
    RATELIMIT_ENABLED = os.environ.get("RATELIMIT_ENABLED", "true").lower() != "false"
    RATELIMIT_STORAGE_URL = os.environ.get("RATELIMIT_STORAGE_URL", "memory://")
    RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "200 per day;50 per hour")

    # ── Notifications ─────────────────────────────────────────────────────────
    NOTIFY_BACKEND = os.environ.get("NOTIFY_BACKEND", "log").lower()
    SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_FROM = os.environ.get("SMTP_FROM", "")
    SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")

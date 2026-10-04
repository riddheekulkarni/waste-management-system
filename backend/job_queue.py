"""
Queue and Worker Dispatch Abstraction for EcoClean Civic.

Provides:
- Redis Queue (RQ) integration for asynchronous worker processing.
- Synchronous fallback / test mode (ASYNC_MODE="sync" or TESTING=True)
  allowing deterministic, Redis-free test execution.
- Graceful degradation for local development when Redis service is not running.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import redis
    from rq import Queue
    RQ_AVAILABLE = True
except ImportError:
    RQ_AVAILABLE = False


def enqueue_complaint_job(complaint_id: str, app=None) -> str:
    """
    Enqueues a complaint for background AI processing.

    In production/redis mode: Enqueues job on Redis Queue 'complaints'.
    In test/sync mode: Directly processes synchronously inline.
    """
    if app is None:
        from flask import current_app
        app = current_app._get_current_object()

    from tasks import process_complaint_job

    is_testing = app.config.get("TESTING", False)
    async_mode = app.config.get("ASYNC_MODE", "redis").lower()

    # 1. Deterministic Synchronous Mode (for tests or explicit sync configuration)
    if is_testing or async_mode == "sync":
        logger.debug("[JobQueue] Running complaint %s in sync mode (TESTING=%s)", complaint_id, is_testing)
        process_complaint_job(complaint_id, app=app)
        return "sync-completed"

    # 2. Asynchronous Mode via Redis Queue (RQ)
    if not RQ_AVAILABLE:
        logger.warning("[JobQueue] RQ / Redis package not available; running job inline synchronously.")
        process_complaint_job(complaint_id, app=app)
        return "inline-no-rq"

    redis_url = app.config.get("REDIS_URL", "redis://localhost:6379/0")
    job_timeout = app.config.get("JOB_TIMEOUT", 180)

    try:
        redis_conn = redis.from_url(redis_url, socket_connect_timeout=2)
        redis_conn.ping()
        q = Queue("complaints", connection=redis_conn)
        job = q.enqueue(
            process_complaint_job,
            complaint_id,
            job_timeout=job_timeout,
            result_ttl=3600,
            failure_ttl=86400,
        )
        logger.info("[JobQueue] Enqueued job %s for complaint %s on Redis queue.", job.id, complaint_id)
        return job.id
    except Exception as exc:
        if app.config.get("IS_PRODUCTION"):
            logger.error("[JobQueue] CRITICAL: Failed to connect to Redis queue in production: %s", exc)
            raise
        else:
            logger.warning(
                "[JobQueue] Redis connection failed (%s). Falling back to inline synchronous processing for local dev.",
                exc
            )
            process_complaint_job(complaint_id, app=app)
            return "inline-dev-fallback"

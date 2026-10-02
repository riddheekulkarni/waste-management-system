"""
Background AI Worker Process for EcoClean Civic.

Listens to the 'complaints' Redis queue, loads the YOLOv8 model weights on startup,
and executes asynchronous AI processing jobs.

Usage:
    python backend/worker.py
    # or with custom queue / concurrency via rq:
    rq worker complaints --url redis://localhost:6379/0
"""

import logging
import os
import sys

# Ensure backend root is in python search path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from tasks import get_worker_detector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("ecoclean.worker")

try:
    import redis
    from rq import Connection, Queue, Worker
except ImportError as exc:
    logger.error("RQ and Redis packages are required to run the standalone worker: %s", exc)
    sys.exit(1)


def start_worker():
    app = create_app()

    with app.app_context():
        redis_url = app.config.get("REDIS_URL", "redis://localhost:6379/0")
        logger.info("Initializing EcoClean Civic AI Background Worker...")
        logger.info("Connecting to Redis: %s", redis_url)

        # Preload YOLO model weights so inference jobs don't incur load latency
        logger.info("Pre-warming WasteDetector weights...")
        detector = get_worker_detector(app)
        logger.info("Detector warmed: mode=%s, ai_mode=%s", detector.mode, detector.ai_mode)

        try:
            conn = redis.from_url(redis_url)
            conn.ping()
            logger.info("Redis connection established successfully.")
        except Exception as exc:
            logger.error("Cannot connect to Redis at %s: %s", redis_url, exc)
            logger.error("Ensure Redis server is running (e.g. `docker compose up redis`).")
            sys.exit(1)

        queues = ["complaints"]
        logger.info("Listening on queue(s): %s", queues)

        with Connection(conn):
            worker = Worker(queues, name="ai-inference-worker")
            worker.work(with_scheduler=True)


if __name__ == "__main__":
    start_worker()

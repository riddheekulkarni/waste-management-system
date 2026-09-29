"""
Shared flask-limiter instance.

Defined here (not in app.py) to break the circular import that would result
from route modules importing directly from app.py, which itself imports those
route blueprints.

Usage in route modules:
    from extensions import limiter

Usage in the app factory:
    from extensions import limiter
    limiter.init_app(app)
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

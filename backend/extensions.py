"""
Shared application extensions.

Defined here (not in app.py) to prevent circular imports with route blueprints.
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

migrate = Migrate()

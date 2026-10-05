"""
EcoClean Civic Root Application Launcher.
Allows running `python run.py` or importing `app` directly from the repository root.
"""
import os
import sys

# Ensure backend directory is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app import create_app

app = create_app()

if __name__ == "__main__":
    _debug = os.environ.get("FLASK_ENV", "development").lower() != "production"
    _port = int(os.environ.get("PORT", 5050))
    _reloader_type = os.environ.get("FLASK_RELOADER_TYPE", "stat")
    app.run(
        debug=_debug,
        host="0.0.0.0",
        port=_port,
        reloader_type=_reloader_type,
        exclude_patterns=["*site-packages*", "*uploads*", "*__pycache__*", "*.pt*"],
    )

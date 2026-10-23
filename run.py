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

import argparse

app = create_app()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EcoClean Civic Platform Application Server")
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"), help="Host IP to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 5050)), help="Port number to listen on (default: 5050)")
    parser.add_argument("--no-debug", dest="debug", action="store_false", help="Disable Flask debug mode")
    parser.set_defaults(debug=os.environ.get("FLASK_ENV", "development").lower() != "production")
    args = parser.parse_args()

    reloader_type = os.environ.get("FLASK_RELOADER_TYPE", "stat")
    display_host = "localhost" if args.host == "0.0.0.0" else args.host

    print("=" * 60)
    print("  🌱 EcoClean Civic Platform Launcher")
    print(f"  Serving at:   http://{display_host}:{args.port}")
    print(f"  Health probe: http://{display_host}:{args.port}/api/health")
    print(f"  Debug mode:   {'Enabled' if args.debug else 'Disabled'}")
    print("=" * 60)

    app.run(
        debug=args.debug,
        host=args.host,
        port=args.port,
        reloader_type=reloader_type,
        exclude_patterns=["*site-packages*", "*uploads*", "*__pycache__*", "*.pt*"],
    )


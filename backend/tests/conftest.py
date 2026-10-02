"""
Pytest configuration and shared fixtures for the EcoClean test suite.

The test app is wired to an in-memory SQLite database so every test run
starts from a clean state and never touches the development database file.
The SQLALCHEMY_DATABASE_URI env-var override is injected *before*
create_app() is called so that db.create_all() inside the factory uses the
correct in-memory URI from the very first call.
"""

import os
import sys

import pytest

# ---------------------------------------------------------------------------
# Ensure the backend package root is importable regardless of how pytest is
# invoked (e.g. from the repo root or from backend/).
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def app():
    """
    Create a Flask application instance configured for testing.

    - Uses an in-memory SQLite database (isolated per test function).
    - Seeds one admin and one citizen user so RBAC tests have valid accounts.
    - Tears down the schema after every test to guarantee isolation.
    """
    # Override the database URI *before* importing create_app so the app
    # factory's db.create_all() targets the in-memory database.
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["SECRET_KEY"] = "test-secret-key-ecoclean"

    # Import here (after env override) to avoid module-level side effects.
    from app import create_app
    from models import db, User

    flask_app = create_app()
    flask_app.config.update(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SECRET_KEY": "test-secret-key-ecoclean",
            "WTF_CSRF_ENABLED": False,
            # Disable rate-limiting in tests so upload tests aren't blocked.
            "RATELIMIT_ENABLED": False,
        }
    )

    with flask_app.app_context():
        db.create_all()

        # Seed deterministic test accounts used by RBAC & notification tests.
        admin = User(username="testadmin", email="admin@test.com", role="admin")
        admin.set_password("adminpass")

        citizen = User(username="testcitizen", email="citizen@test.com", role="citizen")
        citizen.set_password("citizenpass")

        db.session.add_all([admin, citizen])
        db.session.commit()

        yield flask_app

        db.session.remove()
        db.drop_all()

    # Clean up env overrides after the test.
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("SECRET_KEY", None)


@pytest.fixture(scope="function")
def client(app):
    """Return a test HTTP client bound to the test app."""
    return app.test_client()


@pytest.fixture(scope="function")
def admin_client(app):
    """Return a test client pre-authenticated as admin."""
    c = app.test_client()
    c.post(
        "/api/auth/login",
        json={"identifier": "testadmin", "password": "adminpass"},
    )
    return c


@pytest.fixture(scope="function")
def citizen_client(app):
    """Return a test client pre-authenticated as citizen."""
    c = app.test_client()
    c.post(
        "/api/auth/login",
        json={"identifier": "testcitizen", "password": "citizenpass"},
    )
    return c

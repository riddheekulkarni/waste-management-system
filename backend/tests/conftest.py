import os
import sys
import pytest

# Ensure backend directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from models import db, User, Complaint


@pytest.fixture
def app():
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SECRET_KEY": "test-secret-key",
    })

    with app.app_context():
        db.create_all()
        # Seed test admin & citizen
        admin = User(username="testadmin", email="admin@test.com", role="admin")
        admin.set_password("adminpass")
        citizen = User(username="testcitizen", email="citizen@test.com", role="citizen")
        citizen.set_password("citizenpass")
        db.session.add(admin)
        db.session.add(citizen)
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()

"""Test fixtures: isolated SQLite DB, seeded roles/admin, authenticated client.

Environment overrides happen at import time — before any app module is loaded —
because engine and settings are constructed on first import.
"""
import os
import tempfile

_TMPDIR = tempfile.mkdtemp(prefix="jrl_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMPDIR}/test.db"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["SEED_DEMO_DATA"] = "false"
os.environ["UPLOAD_DIR"] = f"{_TMPDIR}/uploads"
os.environ["REPORT_DIR"] = f"{_TMPDIR}/reports"

import pytest
from fastapi.testclient import TestClient

from app.core.constants import RoleName
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models import Role, User


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        roles = {}
        for rn in RoleName:
            role = Role(name=rn.value, description=rn.value)
            db.add(role)
            roles[rn.value] = role
        db.flush()
        db.add(User(email="admin@test.local", full_name="Test Admin",
                    hashed_password=hash_password("Passw0rd!"), role_id=roles["admin"].id))
        db.add(User(email="viewer@test.local", full_name="Test Viewer",
                    hashed_password=hash_password("Passw0rd!"), role_id=roles["viewer"].id))
        db.commit()
    finally:
        db.close()
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def _login(client, email):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "Passw0rd!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def admin_headers(client):
    return _login(client, "admin@test.local")


@pytest.fixture(scope="session")
def viewer_headers(client):
    return _login(client, "viewer@test.local")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.session import get_db
from app.main import app

SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(client):
    client.post(
        "/api/auth/register",
        json={"email": "user@example.com", "password": "password123"},
    )
    response = client.post(
        "/api/auth/login",
        data={"username": "user@example.com", "password": "password123"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _login(client, email: str, password: str = "password123") -> dict:
    client.post("/api/auth/register", json={"email": email, "password": password})
    token = client.post("/api/auth/login", data={"username": email, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_headers(auth_headers):
    # The first account created is the admin, and `auth_headers` is always the first one.
    return auth_headers


@pytest.fixture()
def analyst_headers(client, admin_headers):
    return _login(client, "analyst@example.com")


@pytest.fixture()
def viewer_headers(client, admin_headers):
    headers = _login(client, "viewer@example.com")
    viewer_id = client.get("/api/auth/me", headers=headers).json()["id"]
    client.patch(f"/api/users/{viewer_id}/role", json={"role": "viewer"}, headers=admin_headers)
    return headers


@pytest.fixture()
def make_key(client, admin_headers):
    """Create an API key for a source (as the admin) and return the plain key."""

    def make(source: str, name: str | None = None) -> str:
        response = client.post(
            "/api/api-keys", json={"name": name or f"{source}-key", "source": source}, headers=admin_headers
        )
        assert response.status_code == 201, response.text
        return response.json()["key"]

    return make

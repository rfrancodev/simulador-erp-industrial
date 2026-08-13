"""Tests for authentication, authorization and token issuance (H-01)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.connection import session_dependency
from app.domain.auth import UserCreate, UserRole
from app.domain.entities import Base
from app.main import app
from app.services.auth_service import AuthService

pytestmark = pytest.mark.no_auth


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_fks(dbapi_connection, connection_record):
        dbapi_connection.execute("pragma foreign_keys=ON")

    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine) -> Session:
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def client(session: Session):
    def override():
        yield session

    app.dependency_overrides[session_dependency] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _create_user(
    session: Session, username: str = "admin", password: str = "secret123", role: UserRole = UserRole.ADMIN
):
    return AuthService(session).create_user(
        UserCreate(username=username, password=password, role=role)
    )


def _token_for(client: TestClient, username: str, password: str) -> str:
    resp = client.post(
        "/api/auth/login", data={"username": username, "password": password}
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


class TestLogin:
    def test_login_success(self, client, session):
        _create_user(session)
        resp = client.post("/api/auth/login", data={"username": "admin", "password": "secret123"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["access_token"]
        assert body["token_type"] == "bearer"
        assert body["user"]["username"] == "admin"
        assert body["user"]["role"] == "admin"

    def test_login_wrong_password(self, client, session):
        _create_user(session)
        resp = client.post("/api/auth/login", data={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401

    def test_login_unknown_user(self, client):
        resp = client.post("/api/auth/login", data={"username": "nobody", "password": "whatever"})
        assert resp.status_code == 401


class TestMe:
    def test_me_with_valid_token(self, client, session):
        _create_user(session)
        token = _token_for(client, "admin", "secret123")
        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["username"] == "admin"

    def test_me_without_token(self, client):
        assert client.get("/api/auth/me").status_code == 401

    def test_me_with_invalid_token(self, client):
        resp = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
        assert resp.status_code == 401


class TestRegister:
    def test_register_requires_admin(self, client, session):
        _create_user(session, username="viewer", role=UserRole.VIEWER)
        token = _token_for(client, "viewer", "secret123")
        resp = client.post(
            "/api/auth/register",
            headers={"Authorization": f"Bearer {token}"},
            json={"username": "newbie", "password": "secret123", "role": "viewer"},
        )
        assert resp.status_code == 403

    def test_register_by_admin_succeeds(self, client, session):
        _create_user(session)
        token = _token_for(client, "admin", "secret123")
        resp = client.post(
            "/api/auth/register",
            headers={"Authorization": f"Bearer {token}"},
            json={"username": "operator1", "password": "secret123", "role": "operator"},
        )
        assert resp.status_code == 201
        assert resp.json()["role"] == "operator"

    def test_register_duplicate_username(self, client, session):
        _create_user(session)
        token = _token_for(client, "admin", "secret123")
        resp = client.post(
            "/api/auth/register",
            headers={"Authorization": f"Bearer {token}"},
            json={"username": "admin", "password": "secret123", "role": "viewer"},
        )
        assert resp.status_code == 409


class TestAuthorization:
    def test_unauthenticated_returns_401(self, client):
        assert client.get("/api/production/materials").status_code == 401

    def test_viewer_can_read_but_not_write(self, client, session):
        _create_user(session, username="viewer", role=UserRole.VIEWER)
        token = _token_for(client, "viewer", "secret123")
        headers = {"Authorization": f"Bearer {token}"}
        assert client.get("/api/production/materials", headers=headers).status_code == 200
        resp = client.post(
            "/api/production/materials",
            headers=headers,
            json={
                "material_code": "MAT-AUTH-1",
                "material_name": "X",
                "material_type": "RAW_MATERIAL",
                "base_unit": "KG",
                "plant": "P001",
            },
        )
        assert resp.status_code == 403

    def test_operator_can_write_but_not_delete(self, client, session):
        _create_user(session, username="opuser", role=UserRole.OPERATOR)
        token = _token_for(client, "opuser", "secret123")
        headers = {"Authorization": f"Bearer {token}"}
        resp = client.post(
            "/api/production/materials",
            headers=headers,
            json={
                "material_code": "MAT-AUTH-2",
                "material_name": "Y",
                "material_type": "RAW_MATERIAL",
                "base_unit": "KG",
                "plant": "P001",
            },
        )
        assert resp.status_code == 201
        material_id = resp.json()["id"]
        assert client.delete(f"/api/production/materials/{material_id}", headers=headers).status_code == 403

    def test_admin_can_delete(self, client, session):
        _create_user(session)
        token = _token_for(client, "admin", "secret123")
        headers = {"Authorization": f"Bearer {token}"}
        resp = client.post(
            "/api/production/materials",
            headers=headers,
            json={
                "material_code": "MAT-AUTH-3",
                "material_name": "Z",
                "material_type": "RAW_MATERIAL",
                "base_unit": "KG",
                "plant": "P001",
            },
        )
        material_id = resp.json()["id"]
        assert client.delete(f"/api/production/materials/{material_id}", headers=headers).status_code == 204


class TestAccountLockout:
    def test_failed_attempts_do_not_lock_out_correct_password(self, client, session):
        _create_user(session)
        for _ in range(5):
            resp = client.post("/api/auth/login", data={"username": "admin", "password": "wrong"})
            assert resp.status_code == 401
        resp = client.post("/api/auth/login", data={"username": "admin", "password": "secret123"})
        assert resp.status_code == 200

    def test_successful_login_resets_counter(self, client, session):
        _create_user(session)
        for _ in range(4):
            client.post("/api/auth/login", data={"username": "admin", "password": "wrong"})
        # A successful login resets the counter before lockout triggers.
        assert client.post("/api/auth/login", data={"username": "admin", "password": "secret123"}).status_code == 200


class TestTokenLifecycle:
    def test_missing_secret_is_rejected(self, monkeypatch):
        from app.security import tokens as tokens_mod

        monkeypatch.delenv("SECRET_KEY", raising=False)
        with pytest.raises(RuntimeError, match="SECRET_KEY must be set"):
            tokens_mod.validate_secret_key()

    def test_short_secret_is_rejected(self, monkeypatch):
        from app.security import tokens as tokens_mod

        monkeypatch.setenv("SECRET_KEY", "too-short")
        with pytest.raises(RuntimeError, match="at least 32 bytes"):
            tokens_mod.validate_secret_key()

    def test_expired_token_returns_401(self, client, session, monkeypatch):
        _create_user(session)
        from app.security import tokens as tokens_mod

        monkeypatch.setattr(tokens_mod, "token_expiry_minutes", lambda: -1)
        token = tokens_mod.create_access_token(subject="admin")
        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    def test_token_for_inactive_user_returns_401(self, client, session):
        user = _create_user(session)
        token = _token_for(client, "admin", "secret123")
        user.is_active = False
        session.commit()
        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    def test_token_for_deleted_user_returns_401(self, client, session):
        user = _create_user(session)
        token = _token_for(client, "admin", "secret123")
        session.delete(user)
        session.commit()
        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

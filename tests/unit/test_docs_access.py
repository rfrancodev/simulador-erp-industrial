"""Tests for admin-only access to the Swagger/OpenAPI documentation.

Covers /docs and /openapi.json (backend enforcement) and the navbar link
(only rendered for admins).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.connection import session_dependency
from app.domain.auth import UserCreate, UserRole
from app.domain.entities import Base
from app.main import app
from app.security.tokens import create_access_token
from app.services.auth_service import AuthService


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


@pytest.fixture
def make_user(session: Session):
    def _make(username: str, role: UserRole) -> str:
        AuthService(session).create_user(
            UserCreate(username=username, password="secret123", role=role)
        )
        return create_access_token(subject=username)

    return _make


class TestDocsBackend:
    @pytest.mark.no_auth
    def test_docs_unauthenticated_returns_401(self, client: TestClient):
        assert client.get("/docs").status_code == 401

    @pytest.mark.no_auth
    def test_openapi_unauthenticated_returns_401(self, client: TestClient):
        assert client.get("/openapi.json").status_code == 401

    @pytest.mark.no_auth
    def test_docs_admin_cookie_returns_200(self, client: TestClient, make_user):
        token = make_user("admin-docs", UserRole.ADMIN)
        client.cookies.set("access_token", token)
        resp = client.get("/docs")
        assert resp.status_code == 200
        assert "swagger" in resp.text.lower()

    @pytest.mark.no_auth
    def test_openapi_admin_cookie_returns_200(self, client: TestClient, make_user):
        token = make_user("admin-openapi", UserRole.ADMIN)
        client.cookies.set("access_token", token)
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["openapi"].startswith("3.")
        assert "paths" in data

    @pytest.mark.no_auth
    @pytest.mark.parametrize("role", [UserRole.VIEWER, UserRole.OPERATOR])
    def test_docs_non_admin_cookie_returns_403(
        self, client: TestClient, make_user, role
    ):
        token = make_user(f"non-admin-docs-{role.value}", role)
        client.cookies.set("access_token", token)
        assert client.get("/docs").status_code == 403

    @pytest.mark.no_auth
    @pytest.mark.parametrize("role", [UserRole.VIEWER, UserRole.OPERATOR])
    def test_openapi_non_admin_cookie_returns_403(
        self, client: TestClient, make_user, role
    ):
        token = make_user(f"non-admin-openapi-{role.value}", role)
        client.cookies.set("access_token", token)
        assert client.get("/openapi.json").status_code == 403

    @pytest.mark.no_auth
    def test_openapi_admin_bearer_token_returns_200(
        self, client: TestClient, make_user
    ):
        token = make_user("admin-bearer", UserRole.ADMIN)
        resp = client.get(
            "/openapi.json", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        assert "paths" in resp.json()

    @pytest.mark.no_auth
    def test_docs_non_admin_bearer_token_returns_403(
        self, client: TestClient, make_user
    ):
        token = make_user("viewer-bearer", UserRole.VIEWER)
        resp = client.get("/docs", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403


class TestDocsNavbar:
    @pytest.mark.no_auth
    def test_admin_sees_api_docs_link(self, client: TestClient, make_user):
        token = make_user("admin-nav", UserRole.ADMIN)
        client.cookies.set("access_token", token)
        resp = client.get("/dashboard/")
        assert resp.status_code == 200
        assert 'href="/docs"' in resp.text

    @pytest.mark.no_auth
    @pytest.mark.parametrize("role", [UserRole.VIEWER, UserRole.OPERATOR])
    def test_non_admin_does_not_see_api_docs_link(
        self, client: TestClient, make_user, role
    ):
        token = make_user(f"nav-{role.value}", role)
        client.cookies.set("access_token", token)
        resp = client.get("/dashboard/")
        assert resp.status_code == 200
        assert 'href="/docs"' not in resp.text
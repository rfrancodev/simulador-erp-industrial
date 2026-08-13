"""Tests for the in-memory sliding-window rate limiter (M-16, M-20, M-21)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.connection import session_dependency
from app.domain.entities import Base
from app.main import app
from app.middleware.rate_limit import (
    SlidingWindowRateLimiter,
    _client_key,
    rate_limiter,
)


class TestSlidingWindowRateLimiter:
    def test_allows_within_limit(self):
        limiter = SlidingWindowRateLimiter(requests_per_minute=5)
        for _ in range(5):
            assert limiter.allow("10.0.0.1") is True

    def test_blocks_after_limit(self):
        limiter = SlidingWindowRateLimiter(requests_per_minute=3)
        assert limiter.allow("10.0.0.1") is True
        assert limiter.allow("10.0.0.1") is True
        assert limiter.allow("10.0.0.1") is True
        assert limiter.allow("10.0.0.1") is False

    def test_keys_are_isolated(self):
        limiter = SlidingWindowRateLimiter(requests_per_minute=1)
        assert limiter.allow("10.0.0.1") is True
        assert limiter.allow("10.0.0.2") is True
        assert limiter.allow("10.0.0.1") is False

    def test_reset_clears_state(self):
        limiter = SlidingWindowRateLimiter(requests_per_minute=1)
        assert limiter.allow("10.0.0.1") is True
        assert limiter.allow("10.0.0.1") is False
        limiter.reset()
        assert limiter.allow("10.0.0.1") is True


class _FakeHeaders(dict):
    def get(self, key, default=None):
        return dict.get(self, key.lower(), default)


class _FakeClient:
    def __init__(self, host):
        self.host = host


class _FakeRequest:
    def __init__(self, host="127.0.0.1", headers=None):
        self.client = _FakeClient(host)
        self.headers = _FakeHeaders(headers or {})


class TestClientKey:
    def test_uses_forwarded_for_when_trusted(self, monkeypatch):
        monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
        monkeypatch.setenv("TRUSTED_PROXY_IPS", "127.0.0.1")
        req = _FakeRequest(headers={"x-forwarded-for": "1.2.3.4, 10.0.0.1"})
        assert _client_key(req) == "1.2.3.4"

    def test_uses_real_ip_when_trusted(self, monkeypatch):
        monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
        monkeypatch.setenv("TRUSTED_PROXY_IPS", "127.0.0.1")
        req = _FakeRequest(headers={"x-real-ip": "5.6.7.8"})
        assert _client_key(req) == "5.6.7.8"

    def test_ignores_proxy_headers_from_untrusted_client(self, monkeypatch):
        monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
        monkeypatch.setenv("TRUSTED_PROXY_IPS", "127.0.0.1")
        req = _FakeRequest(host="9.9.9.9", headers={"x-forwarded-for": "1.2.3.4"})
        assert _client_key(req) == "9.9.9.9"

    def test_ignores_proxy_headers_by_default(self, monkeypatch):
        monkeypatch.delenv("TRUST_PROXY_HEADERS", raising=False)
        req = _FakeRequest(host="9.9.9.9", headers={"x-forwarded-for": "1.2.3.4"})
        assert _client_key(req) == "9.9.9.9"


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


class TestRateLimitMiddleware:
    def test_returns_429_after_limit(self, client):
        original = rate_limiter.requests_per_minute
        rate_limiter.requests_per_minute = 1
        rate_limiter.reset()
        try:
            assert client.get("/api/dashboard/kpis").status_code == 200
            assert client.get("/api/dashboard/kpis").status_code == 429
        finally:
            rate_limiter.requests_per_minute = original
            rate_limiter.reset()

    def test_non_api_paths_are_not_limited(self, client):
        original = rate_limiter.requests_per_minute
        rate_limiter.requests_per_minute = 1
        rate_limiter.reset()
        try:
            for _ in range(5):
                assert client.get("/health").status_code == 200
        finally:
            rate_limiter.requests_per_minute = original
            rate_limiter.reset()

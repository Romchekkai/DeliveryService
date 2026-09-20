"""Shared fixtures for the delivery-service test-suite.

Layout
------
tests/unit            pure unit tests (in-memory fakes, no PostgreSQL / Redis / network)
tests/integration_db  repositories, the scheduler job and migrations against a real PostgreSQL
tests/integration     HTTP API (FastAPI app + real PostgreSQL + real JWT verification)

Environment
-----------
DB_HOST / DB_PORT / DB_USER / DB_PASSWORD  connection to the PostgreSQL server
TEST_DB_NAME                               database for the tests (default delivery_service_db_test)
REQUIRE_DB=1                               fail (instead of skip) when PostgreSQL is unreachable
"""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timedelta, timezone

# Settings objects are created at import time. Real environment variables win over .env.
os.environ.setdefault("DB_PASSWORD", "dev_local_pass_123")
os.environ.setdefault("SCHEDULER_ENABLED", "false")

import httpx  # noqa: E402
import jwt  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from delivery_service.domain.entities.parcel import ParcelType  # noqa: E402
from delivery_service.infrastructure.config import db_settings  # noqa: E402
from delivery_service.infrastructure.db.models import (  # noqa: E402,F401
    parcel_model,
    parcel_type_model,
)
from delivery_service.infrastructure.db.models.base_model import Base  # noqa: E402
from delivery_service.infrastructure.db.models.parcel_type_model import (  # noqa: E402
    ParcelTypeModel,
)
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

TEST_DB_NAME = os.getenv("TEST_DB_NAME", "delivery_service_db_test")
REQUIRE_DB = os.getenv("REQUIRE_DB") == "1"


def db_url(name: str = TEST_DB_NAME) -> str:
    return db_settings.model_copy(update={"name": name}).url


def assert_safe_db_name(name: str) -> None:
    # Fixtures drop and truncate tables - never let them touch a development database.
    assert name.endswith("_test"), f"refusing to run destructive test fixtures on {name!r}"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        path = str(item.path).replace("\\", "/")
        if "/tests/unit/" in path:
            item.add_marker(pytest.mark.unit)
        elif "/tests/integration_db/" in path or "/tests/integration/" in path:
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.db)


# ---------------------------------------------------------------------------- database ----


@pytest_asyncio.fixture(scope="session")
async def db_engine() -> AsyncIterator[AsyncEngine]:
    assert_safe_db_name(TEST_DB_NAME)
    engine = create_async_engine(db_url())
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:  # noqa: BLE001
        await engine.dispose()
        if REQUIRE_DB:
            raise
        pytest.skip(f"PostgreSQL test database is not reachable: {e!r}")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)


async def _truncate(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE parcel, parcel_type RESTART IDENTITY CASCADE"))


@pytest_asyncio.fixture
async def session(
    db_engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as s:
        yield s
    await _truncate(db_engine)  # the session is closed here, so no lock is held


@pytest_asyncio.fixture
async def parcel_types(session: AsyncSession) -> list[ParcelType]:
    """Three reference rows, ids 1..3 (sequences restart after every test)."""
    for name in ("Одежда", "Электроника", "Разное"):
        session.add(ParcelTypeModel(name=name))
    await session.commit()
    return [ParcelType(1, "Одежда"), ParcelType(2, "Электроника"), ParcelType(3, "Разное")]


# --------------------------------------------------------------------------------- JWT ----


@pytest.fixture(scope="session")
def rsa_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def public_key_pem(rsa_key: rsa.RSAPrivateKey) -> str:
    return (
        rsa_key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )


@pytest.fixture(scope="session")
def make_token(rsa_key: rsa.RSAPrivateKey) -> Callable[..., str]:
    """Builds access tokens the same way the users service does (RS256, sub + role)."""

    def _make(
        user_id: uuid.UUID | None = None,
        role: str = "user",
        expires_in: timedelta = timedelta(minutes=30),
        key: rsa.RSAPrivateKey | None = None,
    ) -> str:
        now = datetime.now(timezone.utc)
        claims = {
            "sub": str(user_id or uuid.uuid4()),
            "role": role,
            "iat": int(now.timestamp()),
            "exp": int((now + expires_in).timestamp()),
        }
        return jwt.encode(claims, key or rsa_key, algorithm="RS256")

    return _make


@pytest.fixture
def auth(make_token: Callable[..., str]) -> Callable[..., dict[str, str]]:
    def _auth(user_id: uuid.UUID | None = None, role: str = "user") -> dict[str, str]:
        return {"Authorization": f"Bearer {make_token(user_id, role)}"}

    return _auth


# ---------------------------------------------------------------------------- HTTP API ----


@pytest_asyncio.fixture
async def client(
    db_engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    public_key_pem: str,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[httpx.AsyncClient]:
    from delivery_service.infrastructure.db.session import get_session
    from delivery_service.infrastructure.di import jwt_verifier
    from delivery_service.presentation.main import app

    # The verifier normally downloads the key from the users service - pre-load it instead.
    monkeypatch.setattr(jwt_verifier, "_public_key", public_key_pem)
    monkeypatch.setattr(jwt_verifier, "_fetched_at", time.monotonic())
    monkeypatch.setattr(jwt_verifier, "_cache_seconds", 10**9)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    await _truncate(db_engine)

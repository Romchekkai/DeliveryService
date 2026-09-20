"""Shared fixtures for the users-service test-suite.

Layout
------
tests/unit            pure unit tests (in-memory fakes, no PostgreSQL)
tests/integration_db  repositories / use cases / migrations against a real PostgreSQL
tests/integration     HTTP API (FastAPI app + real PostgreSQL + in-memory Vault)

Environment
-----------
DB_HOST / DB_PORT / DB_USER / DB_PASSWORD  connection to the PostgreSQL server
TEST_DB_NAME                               database for the tests (default user_service_db_test)
REQUIRE_DB=1                               fail (instead of skip) when PostgreSQL is unreachable
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

# Settings objects are created at import time and need these two values. Real environment
# variables win over the local .env file, so this only fills the gaps.
os.environ.setdefault("DB_PASSWORD", "dev_local_pass_123")
os.environ.setdefault("VAULT_TOKEN", "test-token")

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
import user_service.infrastructure.security.vault_client_factory as _vault_factory  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from user_service.infrastructure.config import db_settings  # noqa: E402
from user_service.infrastructure.db.models import Base  # noqa: E402

from tests.fakes.vault import FakeVaultClient  # noqa: E402


class _AuthenticatedFakeVault(FakeVaultClient):
    """What ``hvac.Client(url=..., token=...)`` returns, minus the network."""

    def __init__(self, url: str | None = None, token: str | None = None) -> None:
        super().__init__()

    def is_authenticated(self) -> bool:
        return True


# di.py connects to Vault while it is being imported. Swap hvac.Client for an in-memory
# Transit engine just for that import; create_vault_client() itself stays the real one.
_real_hvac_client = _vault_factory.hvac.Client
_vault_factory.hvac.Client = _AuthenticatedFakeVault  # type: ignore[misc,assignment]
try:
    import user_service.infrastructure.di  # noqa: E402,F401
finally:
    _vault_factory.hvac.Client = _real_hvac_client  # type: ignore[misc]

TEST_DB_NAME = os.getenv("TEST_DB_NAME", "user_service_db_test")
REQUIRE_DB = os.getenv("REQUIRE_DB") == "1"


def db_url(name: str = TEST_DB_NAME) -> str:
    return db_settings.model_copy(update={"name": name}).url


def assert_safe_db_name(name: str) -> None:
    # Fixtures drop and truncate tables - never let them touch a development database.
    assert name.endswith("_test"), f"refusing to run destructive test fixtures on {name!r}"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        path = str(item.path)
        if "/tests/unit/" in path.replace("\\", "/"):
            item.add_marker(pytest.mark.unit)
        elif "/tests/integration_db/" in path.replace("\\", "/"):
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.db)
        elif "/tests/integration/" in path.replace("\\", "/"):
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
        await conn.execute(text("TRUNCATE refresh_tokens, users RESTART IDENTITY CASCADE"))


@pytest_asyncio.fixture
async def session(
    db_engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as s:
        yield s
    await _truncate(db_engine)  # the session is closed here, so no lock is held


# ---------------------------------------------------------------------------- HTTP API ----


@pytest_asyncio.fixture
async def client(
    db_engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> AsyncIterator[httpx.AsyncClient]:
    from user_service.infrastructure.di import get_session
    from user_service.presentation.main import app

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    await _truncate(db_engine)


@pytest.fixture(scope="session")
def vault_client() -> Iterator[FakeVaultClient]:
    yield FakeVaultClient()

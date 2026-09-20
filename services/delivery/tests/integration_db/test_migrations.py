"""Alembic migrations must build the schema the ORM models expect.

Runs alembic in a subprocess against a throw-away database, so it can not disturb the
schema used by the other DB tests.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest import REQUIRE_DB, assert_safe_db_name, db_url

SERVICE_DIR = Path(__file__).resolve().parents[2]
VERSIONS_DIR = SERVICE_DIR / "migrations" / "versions"
MIGRATION_DB = "delivery_service_db_migrations_test"


def alembic(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "DB_NAME": MIGRATION_DB}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=SERVICE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest_asyncio.fixture
async def migration_db() -> AsyncIterator[str]:
    assert_safe_db_name(MIGRATION_DB)
    admin = create_async_engine(db_url("postgres"), isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{MIGRATION_DB}" WITH (FORCE)'))
            await conn.execute(text(f'CREATE DATABASE "{MIGRATION_DB}"'))
    except Exception as e:  # noqa: BLE001
        await admin.dispose()
        if REQUIRE_DB:
            raise
        pytest.skip(f"PostgreSQL is not reachable: {e!r}")
    yield MIGRATION_DB
    async with admin.connect() as conn:
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{MIGRATION_DB}" WITH (FORCE)'))
    await admin.dispose()


async def table_names() -> set[str]:
    engine = create_async_engine(db_url(MIGRATION_DB))
    try:
        async with engine.connect() as conn:
            return set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
    finally:
        await engine.dispose()


def test_migration_files_exist() -> None:
    assert list(VERSIONS_DIR.glob("*.py")), (
        "migrations/versions is empty, so `alembic upgrade head` creates no tables and the "
        "service fails with 'relation parcel_type does not exist'. Generate the schema with "
        "`alembic revision --autogenerate -m 'create parcel tables'`."
    )


async def test_upgrade_head_creates_tables(migration_db: str) -> None:
    result = alembic("upgrade", "head")
    assert result.returncode == 0, result.stderr

    assert {"parcel", "parcel_type", "alembic_version"} <= await table_names()


async def test_models_and_migrations_are_in_sync(migration_db: str) -> None:
    assert alembic("upgrade", "head").returncode == 0

    result = alembic("check")

    assert result.returncode == 0, (
        "Models changed but no migration was generated - run "
        "`alembic revision --autogenerate`.\n" + result.stdout + result.stderr
    )


async def test_downgrade_base_drops_tables(migration_db: str) -> None:
    assert alembic("upgrade", "head").returncode == 0

    result = alembic("downgrade", "base")

    assert result.returncode == 0, result.stderr
    assert {"parcel", "parcel_type"}.isdisjoint(await table_names())

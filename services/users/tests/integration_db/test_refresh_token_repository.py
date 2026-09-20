from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from user_service.domain.entities.refresh_token import RefreshToken
from user_service.domain.entities.user import User
from user_service.domain.value_objects.email import Email
from user_service.domain.value_objects.password_hash import PasswordHash
from user_service.infrastructure.db.repositories import (
    SQLAlchemyRefreshTokenRepository,
    SqlAlchemyUserRepository,
)


@pytest.fixture
def repo(session: AsyncSession) -> SQLAlchemyRefreshTokenRepository:
    return SQLAlchemyRefreshTokenRepository(session)


async def make_user(session: AsyncSession, email: str = "owner@example.com") -> User:
    user = User.register(Email(email), PasswordHash("h"))
    await SqlAlchemyUserRepository(session).add(user)  # refresh_tokens.user_id is a FK
    return user


async def test_add_and_get_by_hash(
    repo: SQLAlchemyRefreshTokenRepository, session: AsyncSession
) -> None:
    user = await make_user(session)
    token = RefreshToken.create(user_id=user.id, token_hash="a" * 64)
    await repo.add(token)

    found = await repo.get_by_hash("a" * 64)

    assert found is not None
    assert found.id == token.id
    assert found.user_id == user.id
    assert found.revoked is False
    assert found.is_valid()
    assert found.expires_at.tzinfo is not None


async def test_get_unknown_hash_returns_none(repo: SQLAlchemyRefreshTokenRepository) -> None:
    assert await repo.get_by_hash("f" * 64) is None


async def test_token_hash_is_unique(
    repo: SQLAlchemyRefreshTokenRepository, session: AsyncSession
) -> None:
    from sqlalchemy.exc import IntegrityError

    user = await make_user(session)
    await repo.add(RefreshToken.create(user_id=user.id, token_hash="b" * 64))

    with pytest.raises(IntegrityError):
        await repo.add(RefreshToken.create(user_id=user.id, token_hash="b" * 64))


async def test_add_for_unknown_user_violates_fk(
    repo: SQLAlchemyRefreshTokenRepository,
) -> None:
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        await repo.add(RefreshToken.create(user_id=uuid4(), token_hash="c" * 64))


async def test_update_revoke(repo: SQLAlchemyRefreshTokenRepository, session: AsyncSession) -> None:
    user = await make_user(session)
    token = RefreshToken.create(user_id=user.id, token_hash="d" * 64)
    await repo.add(token)

    token.revoke()
    await repo.update(token)
    session.expire_all()

    found = await repo.get_by_hash("d" * 64)
    assert found is not None
    assert found.revoked is True
    assert not found.is_valid()


async def test_update_persists_expiry(
    repo: SQLAlchemyRefreshTokenRepository, session: AsyncSession
) -> None:
    user = await make_user(session)
    token = RefreshToken.create(user_id=user.id, token_hash="e" * 64)
    await repo.add(token)

    token.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await repo.update(token)
    session.expire_all()

    found = await repo.get_by_hash("e" * 64)
    assert found is not None and not found.is_valid()


async def test_update_missing_raises(repo: SQLAlchemyRefreshTokenRepository) -> None:
    with pytest.raises(ValueError):
        await repo.update(RefreshToken.create(user_id=uuid4(), token_hash="0" * 64))


async def test_revoke_all_for_user(
    repo: SQLAlchemyRefreshTokenRepository, session: AsyncSession
) -> None:
    alice = await make_user(session, "alice@example.com")
    bob = await make_user(session, "bob@example.com")
    for i in range(3):
        await repo.add(RefreshToken.create(user_id=alice.id, token_hash=f"a{i}".ljust(64, "0")))
    await repo.add(RefreshToken.create(user_id=bob.id, token_hash="b0".ljust(64, "0")))

    await repo.revoke_all_for_user(alice.id)
    session.expire_all()

    for i in range(3):
        alice_token = await repo.get_by_hash(f"a{i}".ljust(64, "0"))
        assert alice_token is not None and alice_token.revoked
    bob_token = await repo.get_by_hash("b0".ljust(64, "0"))
    assert bob_token is not None and not bob_token.revoked

"""
Composition root
"""

import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from user_service.application.use_cases.authenticate_user import AuthenticateUserUseCase
from user_service.application.use_cases.get_user_by_id import GetUserByIdUseCase
from user_service.application.use_cases.refresh_access_token import RefreshAccessTokenUseCase
from user_service.application.use_cases.register_user import RegisterUser
from user_service.infrastructure.config import db_settings, jwt_settings, vault_settings
from user_service.infrastructure.db.repositories import (
    SQLAlchemyRefreshTokenRepository,
    SqlAlchemyUserRepository,
)
from user_service.infrastructure.security.jwt_service import VaultJWTTokenService
from user_service.infrastructure.security.password_hasher import BcryptPasswordHasher
from user_service.infrastructure.security.refresh_token_hasher import Sha256RefreshTokenHasher
from user_service.infrastructure.security.vault_client_factory import create_vault_client
from user_service.infrastructure.security.vault_exceptions import VaultConnectionError
from user_service.infrastructure.security.vault_transit_signer import VaultTransitSigner

logger = logging.getLogger(__name__)


# ---------- Database ----------

engine = create_async_engine(
    db_settings.url,
    echo=db_settings.echo,
    pool_size=db_settings.pool_size,
    max_overflow=db_settings.max_overflow,
    pool_timeout=db_settings.pool_timeout,
    pool_recycle=db_settings.pool_recycle,
    pool_pre_ping=db_settings.pool_pre_ping,
)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ---------- Vault / Security ----------

try:
    vault_client = create_vault_client(vault_settings)
    _signer = VaultTransitSigner(vault_client, vault_settings.transit_key_name)

    token_service = VaultJWTTokenService(
        signer=_signer,
        expire_minutes=jwt_settings.expire_minutes,
    )
    logger.info("Подключение к Vault установлено, публичный ключ JWT получен.")

except VaultConnectionError as e:
    logger.critical(f"Не удалось инициализировать Vault: {e}")
    raise RuntimeError(
        "Сервис не может стартовать без подключения к Vault. "
        "Проверьте, что контейнер vault-dev запущен и VAULT_TOKEN корректен."
    ) from e


password_hasher = BcryptPasswordHasher()
refresh_token_hasher = Sha256RefreshTokenHasher()  # ← добавлено


# ---------- FastAPI Dependencies ----------


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session


def get_user_repository(session: AsyncSession) -> SqlAlchemyUserRepository:
    return SqlAlchemyUserRepository(session)


def get_refresh_token_repository(session: AsyncSession) -> SQLAlchemyRefreshTokenRepository:
    return SQLAlchemyRefreshTokenRepository(session)


def get_register_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RegisterUser:
    repo = SqlAlchemyUserRepository(session)
    return RegisterUser(user_repository=repo, password_hasher=password_hasher)


def get_authenticate_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthenticateUserUseCase:
    repo = SqlAlchemyUserRepository(session)
    refresh_repo = SQLAlchemyRefreshTokenRepository(session)  # ← добавлено
    return AuthenticateUserUseCase(
        user_repository=repo,
        refresh_token_repository=refresh_repo,  # ← добавлено
        password_hasher=password_hasher,
        token_service=token_service,
        refresh_token_hasher=refresh_token_hasher,  # ← добавлено
    )


def get_refresh_use_case(  # ← добавлено целиком
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RefreshAccessTokenUseCase:
    repo = SqlAlchemyUserRepository(session)
    refresh_repo = SQLAlchemyRefreshTokenRepository(session)
    return RefreshAccessTokenUseCase(
        user_repository=repo,
        refresh_token_repository=refresh_repo,
        token_service=token_service,
        refresh_token_hasher=refresh_token_hasher,
    )


def get_user_by_id_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GetUserByIdUseCase:
    repo = SqlAlchemyUserRepository(session)
    return GetUserByIdUseCase(user_repository=repo)

"""Use cases wired to the real repositories, real bcrypt and the (in-memory) Vault signer."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from user_service.application.dto.token_dto import RefreshTokenInputDTO
from user_service.application.dto.user_dto import LoginInputDTO, RegisterUserInputDTO
from user_service.application.use_cases.authenticate_user import AuthenticateUserUseCase
from user_service.application.use_cases.refresh_access_token import RefreshAccessTokenUseCase
from user_service.application.use_cases.register_user import RegisterUser
from user_service.domain.exceptions import (
    InvalidCredentialsError,
    InvalidTokenError,
    UserAlreadyExistsError,
)
from user_service.domain.value_objects.role import Role
from user_service.infrastructure.db.repositories import (
    SQLAlchemyRefreshTokenRepository,
    SqlAlchemyUserRepository,
)
from user_service.infrastructure.security.jwt_service import VaultJWTTokenService
from user_service.infrastructure.security.password_hasher import BcryptPasswordHasher
from user_service.infrastructure.security.refresh_token_hasher import Sha256RefreshTokenHasher
from user_service.infrastructure.security.vault_transit_signer import VaultTransitSigner

from tests.fakes.vault import FakeVaultClient


@pytest.fixture
def token_service() -> VaultJWTTokenService:
    signer = VaultTransitSigner(FakeVaultClient(), "key")  # type: ignore[arg-type]
    return VaultJWTTokenService(signer=signer)


@pytest.fixture
def register(session: AsyncSession) -> RegisterUser:
    return RegisterUser(SqlAlchemyUserRepository(session), BcryptPasswordHasher())


@pytest.fixture
def login(session: AsyncSession, token_service: VaultJWTTokenService) -> AuthenticateUserUseCase:
    return AuthenticateUserUseCase(
        user_repository=SqlAlchemyUserRepository(session),
        refresh_token_repository=SQLAlchemyRefreshTokenRepository(session),
        password_hasher=BcryptPasswordHasher(),
        token_service=token_service,
        refresh_token_hasher=Sha256RefreshTokenHasher(),
    )


@pytest.fixture
def refresh(
    session: AsyncSession, token_service: VaultJWTTokenService
) -> RefreshAccessTokenUseCase:
    return RefreshAccessTokenUseCase(
        user_repository=SqlAlchemyUserRepository(session),
        refresh_token_repository=SQLAlchemyRefreshTokenRepository(session),
        token_service=token_service,
        refresh_token_hasher=Sha256RefreshTokenHasher(),
    )


async def test_register_and_login_against_db(
    register: RegisterUser, login: AuthenticateUserUseCase, token_service: VaultJWTTokenService
) -> None:
    user = await register.execute(RegisterUserInputDTO("flow@example.com", "password123"))

    tokens = await login.execute(LoginInputDTO("flow@example.com", "password123"))

    payload = token_service.decode_token(tokens.access_token)
    assert payload.user_id == user.id
    assert payload.role is Role.USER


async def test_register_duplicate_against_db(register: RegisterUser) -> None:
    await register.execute(RegisterUserInputDTO("dup@example.com", "password123"))

    with pytest.raises(UserAlreadyExistsError):
        await register.execute(RegisterUserInputDTO("dup@example.com", "password123"))


async def test_login_wrong_password_against_db(
    register: RegisterUser, login: AuthenticateUserUseCase
) -> None:
    await register.execute(RegisterUserInputDTO("wrong@example.com", "password123"))

    with pytest.raises(InvalidCredentialsError):
        await login.execute(LoginInputDTO("wrong@example.com", "not-the-password"))


async def test_refresh_flow_rotates_tokens_against_db(
    register: RegisterUser, login: AuthenticateUserUseCase, refresh: RefreshAccessTokenUseCase
) -> None:
    await register.execute(RegisterUserInputDTO("rotate@example.com", "password123"))
    first = await login.execute(LoginInputDTO("rotate@example.com", "password123"))

    second = await refresh.execute(RefreshTokenInputDTO(first.refresh_token))

    assert second.refresh_token != first.refresh_token
    with pytest.raises(InvalidTokenError):  # the old one was revoked
        await refresh.execute(RefreshTokenInputDTO(first.refresh_token))
    third = await refresh.execute(RefreshTokenInputDTO(second.refresh_token))
    assert third.access_token

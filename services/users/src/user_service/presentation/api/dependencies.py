from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from user_service.application.dto.user_dto import UserOutputDTO
from user_service.application.use_cases.authenticate_user import AuthenticateUserUseCase
from user_service.application.use_cases.get_user_by_id import GetUserByIdUseCase
from user_service.application.use_cases.refresh_access_token import RefreshAccessTokenUseCase
from user_service.application.use_cases.register_user import RegisterUser
from user_service.domain.exceptions import InvalidTokenError
from user_service.infrastructure.db.repositories import (
    SQLAlchemyRefreshTokenRepository,
    SqlAlchemyUserRepository,
)
from user_service.infrastructure.di import (
    get_session,
    password_hasher,
    refresh_token_hasher,
    token_service,
)

bearer_scheme = HTTPBearer()


def get_register_use_case(session: AsyncSession = Depends(get_session)) -> RegisterUser:
    repo = SqlAlchemyUserRepository(session)
    return RegisterUser(user_repository=repo, password_hasher=password_hasher)


def get_authenticate_use_case(
    session: AsyncSession = Depends(get_session),
) -> AuthenticateUserUseCase:
    repo = SqlAlchemyUserRepository(session)
    refresh_repo = SQLAlchemyRefreshTokenRepository(session)
    return AuthenticateUserUseCase(
        user_repository=repo,
        refresh_token_repository=refresh_repo,
        password_hasher=password_hasher,
        token_service=token_service,
        refresh_token_hasher=refresh_token_hasher,
    )


def get_refresh_use_case(session: AsyncSession = Depends(get_session)) -> RefreshAccessTokenUseCase:
    repo = SqlAlchemyUserRepository(session)
    refresh_repo = SQLAlchemyRefreshTokenRepository(session)
    return RefreshAccessTokenUseCase(
        user_repository=repo,
        refresh_token_repository=refresh_repo,
        token_service=token_service,
        refresh_token_hasher=refresh_token_hasher,
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> UserOutputDTO:
    try:
        payload = token_service.decode_token(credentials.credentials)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Невалидный или истёкший токен"
        )

    use_case = GetUserByIdUseCase(user_repository=SqlAlchemyUserRepository(session))
    try:
        return await use_case.execute(payload.user_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден"
        )


# security = HTTPBearer(auto_error=True)
#
#
# async def get_current_user_payload(
#     credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
# ) -> TokenPayload:
#     token = credentials.credentials
#     try:
#         return token_service.decode_token(token)
#     except InvalidTokenError as e:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail=str(e) or "Could not validate credentials",
#             headers={"WWW-Authenticate": "Bearer"},
#         ) from e
#     except DomainError as e:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail=str(e),
#             headers={"WWW-Authenticate": "Bearer"},
#         ) from e
#
#
# # Type aliases
# SessionDep = Annotated[AsyncSession, Depends(get_session)]
# CurrentUserPayload = Annotated[TokenPayload, Depends(get_current_user_payload)]
# RegisterUseCaseDep = Annotated[RegisterUser, Depends(get_register_use_case)]
# AuthenticateUseCaseDep = Annotated[AuthenticateUserUseCase, Depends(get_authenticate_use_case)]
# GetUserByIdUseCaseDep = Annotated[GetUserByIdUseCase, Depends(get_user_by_id_use_case)]

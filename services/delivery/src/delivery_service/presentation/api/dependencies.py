from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from delivery_service.application.use_cases.get_parcel_by_id import GetParcelsByIdUseCase
from delivery_service.application.use_cases.get_parcel_types import GetParcelTypesUseCase
from delivery_service.application.use_cases.get_parcels_by_user import GetParcelsByUserUseCase
from delivery_service.application.use_cases.parcel_create import CreateParcelUseCase
from delivery_service.infrastructure.db.repositories.sql_alc_parcel_repository import (
    SqlAlchemyParcelRepository,
)
from delivery_service.infrastructure.db.repositories.sql_alc_parcel_type_repository import (
    SqlAlchemyParcelTypeRepository,
)
from delivery_service.infrastructure.db.session import get_session
from delivery_service.infrastructure.di import jwt_verifier
from delivery_service.infrastructure.security.jwt_verifier import InvalidTokenError, TokenPayload

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> TokenPayload:
    """Посылку можно создать только имея валидный токен users-сервиса."""
    try:
        return await jwt_verifier.verify(credentials.credentials)
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def require_admin(current_user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Требуется роль admin")
    return current_user


def get_create_parcel_use_case(
    session: AsyncSession = Depends(get_session),
) -> CreateParcelUseCase:
    return CreateParcelUseCase(
        parcel_repository=SqlAlchemyParcelRepository(session),
        parcel_type_repository=SqlAlchemyParcelTypeRepository(session),
    )


def get_parcel_by_id_use_case(
    session: AsyncSession = Depends(get_session),
) -> GetParcelsByIdUseCase:
    return GetParcelsByIdUseCase(parcel_repository=SqlAlchemyParcelRepository(session))


def get_parcels_by_user_use_case(
    session: AsyncSession = Depends(get_session),
) -> GetParcelsByUserUseCase:
    return GetParcelsByUserUseCase(parcel_repository=SqlAlchemyParcelRepository(session))


def get_parcel_types_use_case(
    session: AsyncSession = Depends(get_session),
) -> GetParcelTypesUseCase:
    return GetParcelTypesUseCase(parcel_types_repo=SqlAlchemyParcelTypeRepository(session))

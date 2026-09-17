from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from user_service.domain.entities.refresh_token import RefreshToken
from user_service.domain.entities.user import User
from user_service.domain.exceptions import UserAlreadyExistsError, UserNotFoundError
from user_service.domain.repositories import IUserRepository, RefreshTokenRepository
from user_service.domain.value_objects.email import Email
from user_service.infrastructure.db.models import RefreshTokenModel, UserModel


class SqlAlchemyUserRepository(IUserRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, user: User) -> None:
        model = UserModel.from_entity(user)
        self._session.add(model)
        try:
            await self._session.commit()
        except IntegrityError as e:
            await self._session.rollback()
            raise UserAlreadyExistsError(str(user.email)) from e

    async def get_by_email(self, email: Email) -> Optional[User]:
        result = await self._session.execute(select(UserModel).where(UserModel.email == str(email)))
        model = result.scalar_one_or_none()
        return model.to_entity() if model else None

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        result = await self._session.execute(select(UserModel).where(UserModel.id == user_id))
        model = result.scalar_one_or_none()
        return model.to_entity() if model else None

    async def update(self, user: User) -> None:
        user_to_update = await self._session.get(UserModel, user.id)
        if user_to_update is None:
            raise UserNotFoundError(user.id)

        user_to_update.email = str(user.email)
        user_to_update.password_hash = user.password_hash.value
        user_to_update.role = user.role
        user_to_update.status = user.status

        await self._session.commit()

    async def exists_with_email(self, email: Email) -> bool:
        result = await self._session.execute(select(UserModel).where(UserModel.email == str(email)))
        return result.scalar_one_or_none() is not None


class SQLAlchemyRefreshTokenRepository(RefreshTokenRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, token: RefreshToken) -> None:
        model = RefreshTokenModel.from_entity(token)
        self._session.add(model)
        await self._session.commit()

    async def get_by_hash(self, token_hash: str) -> Optional[RefreshToken]:
        result = await self._session.execute(
            select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash)
        )
        model = result.scalar_one_or_none()
        return model.to_entity() if model else None

    async def update(self, token: RefreshToken) -> None:
        model = await self._session.get(RefreshTokenModel, token.id)
        if model is None:
            raise ValueError(f"Refresh-токен {token.id} не найден для обновления")

        model.revoked = token.revoked
        model.expires_at = token.expires_at

        await self._session.commit()

    async def revoke_all_for_user(self, user_id: UUID) -> None:
        result = await self._session.execute(
            select(RefreshTokenModel).where(
                RefreshTokenModel.user_id == user_id,
                RefreshTokenModel.revoked == False,  # noqa: E712
            )
        )
        tokens = result.scalars().all()
        for token in tokens:
            token.revoked = True

        await self._session.commit()

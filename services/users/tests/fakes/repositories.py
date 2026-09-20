"""In-memory repositories for use-case unit tests."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from user_service.domain.entities.refresh_token import RefreshToken
from user_service.domain.entities.user import User
from user_service.domain.exceptions import UserAlreadyExistsError, UserNotFoundError
from user_service.domain.repositories import IUserRepository, RefreshTokenRepository
from user_service.domain.value_objects.email import Email


class InMemoryUserRepository(IUserRepository):
    def __init__(self) -> None:
        self.users: dict[UUID, User] = {}

    async def add(self, user: User) -> None:
        if any(u.email == user.email for u in self.users.values()):
            raise UserAlreadyExistsError(str(user.email))
        self.users[user.id] = user

    async def get_by_email(self, email: Email) -> Optional[User]:
        return next((u for u in self.users.values() if u.email == email), None)

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        return self.users.get(user_id)

    async def update(self, user: User) -> None:
        if user.id not in self.users:
            raise UserNotFoundError(user.id)
        self.users[user.id] = user

    async def exists_with_email(self, email: Email) -> bool:
        return await self.get_by_email(email) is not None


class InMemoryRefreshTokenRepository(RefreshTokenRepository):
    def __init__(self) -> None:
        self.tokens: dict[UUID, RefreshToken] = {}

    async def add(self, token: RefreshToken) -> None:
        self.tokens[token.id] = token

    async def get_by_hash(self, token_hash: str) -> Optional[RefreshToken]:
        return next((t for t in self.tokens.values() if t.token_hash == token_hash), None)

    async def revoke_all_for_user(self, user_id: UUID) -> None:
        for token in self.tokens.values():
            if token.user_id == user_id:
                token.revoke()

    async def update(self, token: RefreshToken) -> None:
        if token.id not in self.tokens:
            raise ValueError(f"Refresh-token {token.id} does not exist")
        self.tokens[token.id] = token

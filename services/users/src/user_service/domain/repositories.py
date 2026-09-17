from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from user_service.domain.entities.refresh_token import RefreshToken
from user_service.domain.entities.user import User
from user_service.domain.value_objects.email import Email


class IUserRepository(ABC):
    @abstractmethod
    async def add(self, user: User) -> None: ...

    @abstractmethod
    async def get_by_email(self, email: Email) -> Optional[User]: ...

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> Optional[User]: ...

    @abstractmethod
    async def update(self, user: User) -> None: ...

    @abstractmethod
    async def exists_with_email(self, email: Email) -> bool: ...


class RefreshTokenRepository(ABC):
    @abstractmethod
    async def add(self, token: RefreshToken) -> None: ...

    @abstractmethod
    async def get_by_hash(self, token_hash: str) -> Optional[RefreshToken]: ...

    @abstractmethod
    async def revoke_all_for_user(self, user_id: UUID) -> None: ...

    @abstractmethod
    async def update(self, token: RefreshToken) -> None: ...

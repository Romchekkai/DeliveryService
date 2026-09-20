from abc import ABC, abstractmethod
from uuid import UUID

from user_service.application.interfaces.token_payload import TokenPayload
from user_service.domain.value_objects.role import Role


class TokenService(ABC):
    @abstractmethod
    def generate_access_token(self, user_id: UUID, role: Role) -> str: ...

    @abstractmethod
    def decode_token(self, token: str) -> TokenPayload: ...

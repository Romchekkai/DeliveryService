from dataclasses import dataclass
from uuid import UUID

from user_service.domain.value_objects.role import Role


@dataclass(frozen=True)
class TokenPayload:
    user_id: UUID
    role: Role

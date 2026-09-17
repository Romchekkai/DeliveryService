from dataclasses import dataclass
from uuid import UUID

from user_service.domain.value_objects.role import Role
from user_service.domain.value_objects.status import Status


@dataclass(frozen=True)
class RegisterUserInputDTO:
    email: str
    password: str


@dataclass(frozen=True)
class UserOutputDTO:
    id: UUID
    email: str
    role: Role
    status: Status


@dataclass(frozen=True)
class LoginInputDTO:
    email: str
    password: str


@dataclass(frozen=True)
class TokenOutputDTO:
    access_token: str
    token_type: str = "bearer"

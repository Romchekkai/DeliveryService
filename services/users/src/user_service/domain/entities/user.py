from dataclasses import dataclass
from uuid import UUID, uuid4

from user_service.domain.exceptions import InvalidRoleTransitionError
from user_service.domain.value_objects.email import Email
from user_service.domain.value_objects.password_hash import PasswordHash
from user_service.domain.value_objects.role import Role
from user_service.domain.value_objects.status import Status


@dataclass
class User:
    id: UUID
    email: Email
    password_hash: PasswordHash
    role: Role
    status: Status

    @classmethod
    def register(cls, email: Email, password_hash: PasswordHash) -> "User":
        """Factory method to register a new user"""
        return cls(
            id=uuid4(),
            email=email,
            password_hash=password_hash,
            role=Role.USER,
            status=Status.ACTIVE,
        )

    def block(self) -> None:
        self.status = Status.BLOCKED

    def change_role(self, new_role: Role) -> None:
        if self.status != Status.ACTIVE:
            raise InvalidRoleTransitionError("Cannot change the role of a blocked user")
        self.role = new_role

    def is_active(self) -> bool:
        return self.status == Status.ACTIVE

    def activate(self) -> None:
        self.status = Status.ACTIVE

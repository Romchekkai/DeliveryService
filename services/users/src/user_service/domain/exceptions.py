from uuid import UUID


class DomainError(Exception):
    """Base class for exceptions in user domain module."""


class UserAlreadyBlockedError(DomainError):
    def __init__(self, user_id: UUID):
        super().__init__(f"User {user_id} already blocked")


class InvalidRoleTransitionError(DomainError):
    pass


class UserAlreadyExistsError(DomainError):
    def __init__(self, email: str):
        super().__init__(f"Email {email} already exists")


class InvalidCredentialsError(DomainError):
    pass


class UserNotFoundError(DomainError):
    def __init__(self, user_id: UUID) -> None:
        super().__init__(f"User {user_id} is not found")


class InvalidTokenError(DomainError):
    pass

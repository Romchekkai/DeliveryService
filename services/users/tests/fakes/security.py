"""Cheap deterministic fakes for the security ports (no bcrypt / Vault in unit tests)."""

from __future__ import annotations

import itertools
from uuid import UUID

from user_service.application.interfaces.password_hasher import PasswordHasher
from user_service.application.interfaces.refresh_token_hasher import RefreshTokenHasher
from user_service.application.interfaces.token_payload import TokenPayload
from user_service.application.interfaces.token_service import TokenService
from user_service.domain.exceptions import InvalidTokenError
from user_service.domain.value_objects.role import Role


class FakePasswordHasher(PasswordHasher):
    def hash_password(self, password: str) -> str:
        return f"hashed::{password}"

    def verify_password(self, password: str, password_hash: str) -> bool:
        return password_hash == f"hashed::{password}"


class FakeRefreshTokenHasher(RefreshTokenHasher):
    def __init__(self) -> None:
        self._counter = itertools.count(1)

    def generate_raw_token(self) -> str:
        return f"raw-refresh-{next(self._counter)}"

    def hash(self, token: str) -> str:
        return f"hash({token})"


class FakeTokenService(TokenService):
    def generate_access_token(self, user_id: UUID, role: Role) -> str:
        return f"access::{user_id}::{role.value}"

    def decode_token(self, token: str) -> TokenPayload:
        try:
            _, user_id, role = token.split("::")
            return TokenPayload(user_id=UUID(user_id), role=Role(role))
        except ValueError as e:
            raise InvalidTokenError("bad token") from e

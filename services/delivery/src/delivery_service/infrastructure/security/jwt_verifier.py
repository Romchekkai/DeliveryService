import time
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

import httpx
import jwt
import structlog

logger = structlog.get_logger(__name__)


class InvalidTokenError(Exception):
    pass


@dataclass(frozen=True)
class TokenPayload:
    user_id: UUID
    role: str


class UsersJWTVerifier:
    """Validates the users-service access token using its public key.
    The key is fetched via HTTP once
    and cached to avoid calling the users-service on every request.
    """

    def __init__(
        self, public_key_url: str, algorithm: str = "RS256", cache_seconds: int = 300
    ) -> None:
        self._url = public_key_url
        self._algorithm = algorithm
        self._cache_seconds = cache_seconds
        self._public_key: str | None = None
        self._fetched_at: float = 0.0

    async def _get_public_key(self, force: bool = False) -> Optional[str]:
        expired = time.monotonic() - self._fetched_at > self._cache_seconds
        if self._public_key is None or expired or force:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.get(self._url)
                    response.raise_for_status()
                self._public_key = response.text.strip()
                self._fetched_at = time.monotonic()
                logger.info("users_public_key_fetched", url=self._url)
            except Exception as e:
                logger.error("users_public_key_fetch_failed", error=str(e), url=self._url)
                if self._public_key is None:
                    raise InvalidTokenError("Public key is not available") from e
        return self._public_key

    async def verify(self, token: str) -> TokenPayload:
        public_key = await self._get_public_key()
        if public_key is None:
            raise InvalidTokenError("JWT public key is not available")

        try:
            payload = jwt.decode(token, public_key, algorithms=[self._algorithm])
        except jwt.ExpiredSignatureError as e:
            raise InvalidTokenError("Token expired") from e
        except jwt.InvalidSignatureError:
            # возможно, ключ был ротирован — пробуем обновить и проверить ещё раз
            public_key = await self._get_public_key(force=True)
            if public_key is None:
                raise InvalidTokenError("JWT public key is not available")

            try:
                payload = jwt.decode(token, public_key, algorithms=[self._algorithm])
            except jwt.InvalidTokenError as e:
                raise InvalidTokenError("Invalid token") from e
        except jwt.InvalidTokenError as e:
            raise InvalidTokenError("Invalid token") from e

        return TokenPayload(user_id=UUID(payload["sub"]), role=payload.get("role", "user"))

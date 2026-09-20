from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass
class RefreshToken:
    id: UUID
    user_id: UUID
    token_hash: str  # храним хэш, не сам токен (как с паролем)
    expires_at: datetime
    revoked: bool = False

    @classmethod
    def create(cls, user_id: UUID, token_hash: str, ttl_days: int = 14) -> "RefreshToken":
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        return cls(
            id=uuid4(),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=now + timedelta(days=ttl_days),
        )

    def is_valid(self) -> bool:
        return not self.revoked and datetime.now(timezone.utc) < self.expires_at

    def revoke(self) -> None:
        self.revoked = True

import hashlib
import secrets

from user_service.application.interfaces.refresh_token_hasher import RefreshTokenHasher


class Sha256RefreshTokenHasher(RefreshTokenHasher):
    def generate_raw_token(self) -> str:
        return secrets.token_urlsafe(64)  # криптографически стойкий случайный токен

    def hash(self, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

from delivery_service.infrastructure.config import auth_settings
from delivery_service.infrastructure.currency_provider.redis_client import redis_client
from delivery_service.infrastructure.security.jwt_verifier import UsersJWTVerifier

jwt_verifier = UsersJWTVerifier(
    public_key_url=auth_settings.public_key_url,
    algorithm=auth_settings.algorithm,
    cache_seconds=auth_settings.public_key_cache_seconds,
)

__all__ = ["jwt_verifier", "redis_client"]

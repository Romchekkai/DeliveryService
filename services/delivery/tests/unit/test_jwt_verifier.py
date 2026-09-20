import time
from datetime import timedelta
from typing import Any, Callable
from uuid import uuid4

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from delivery_service.infrastructure.security import jwt_verifier as jwt_verifier_module
from delivery_service.infrastructure.security.jwt_verifier import (
    InvalidTokenError,
    UsersJWTVerifier,
)

KEY_URL = "http://users:8000/api/v1/keys/public"


class UsersServiceStub:
    """Plays the role of GET /api/v1/keys/public of the users service."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, pem: str) -> None:
        self.pem = pem
        self.status = 200
        self.requests = 0
        real_client = httpx.AsyncClient

        def handler(request: httpx.Request) -> httpx.Response:
            self.requests += 1
            if self.status != 200:
                return httpx.Response(self.status)
            return httpx.Response(200, text=self.pem + "\n")

        def factory(**kwargs: Any) -> httpx.AsyncClient:
            return real_client(transport=httpx.MockTransport(handler), **kwargs)

        monkeypatch.setattr(jwt_verifier_module.httpx, "AsyncClient", factory)


@pytest.fixture
def users_service(monkeypatch: pytest.MonkeyPatch, public_key_pem: str) -> UsersServiceStub:
    return UsersServiceStub(monkeypatch, public_key_pem)


async def test_valid_token(users_service: UsersServiceStub, make_token: Callable[..., str]) -> None:
    user_id = uuid4()

    payload = await UsersJWTVerifier(KEY_URL).verify(make_token(user_id, "admin"))

    assert payload.user_id == user_id
    assert payload.role == "admin"


async def test_role_defaults_to_user(
    users_service: UsersServiceStub, rsa_key: rsa.RSAPrivateKey
) -> None:
    import jwt

    token = jwt.encode(
        {"sub": str(uuid4()), "exp": int(time.time()) + 60}, rsa_key, algorithm="RS256"
    )

    assert (await UsersJWTVerifier(KEY_URL).verify(token)).role == "user"


async def test_public_key_is_cached(
    users_service: UsersServiceStub, make_token: Callable[..., str]
) -> None:
    verifier = UsersJWTVerifier(KEY_URL, cache_seconds=300)

    await verifier.verify(make_token())
    await verifier.verify(make_token())

    assert users_service.requests == 1


async def test_public_key_is_refetched_after_the_cache_expired(
    users_service: UsersServiceStub, make_token: Callable[..., str]
) -> None:
    verifier = UsersJWTVerifier(KEY_URL, cache_seconds=0)

    await verifier.verify(make_token())
    time.sleep(0.01)
    await verifier.verify(make_token())

    assert users_service.requests == 2


async def test_expired_token(
    users_service: UsersServiceStub, make_token: Callable[..., str]
) -> None:
    with pytest.raises(InvalidTokenError, match=r"(?i)expired|истёк"):
        await UsersJWTVerifier(KEY_URL).verify(make_token(expires_in=timedelta(seconds=-5)))


async def test_token_signed_with_another_key_is_rejected(
    users_service: UsersServiceStub, make_token: Callable[..., str]
) -> None:
    foreign_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    with pytest.raises(InvalidTokenError):
        await UsersJWTVerifier(KEY_URL).verify(make_token(key=foreign_key))


async def test_rotated_key_is_refetched_on_invalid_signature(
    users_service: UsersServiceStub,
    rsa_key: rsa.RSAPrivateKey,
    make_token: Callable[..., str],
) -> None:
    from cryptography.hazmat.primitives import serialization

    stale_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    stale_pem = (
        stale_key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    verifier = UsersJWTVerifier(KEY_URL, cache_seconds=300)
    verifier._public_key = stale_pem  # cached before the rotation
    verifier._fetched_at = time.monotonic()
    # The users service now publishes the new key (fixture's key), tokens are signed with it.

    payload = await verifier.verify(make_token())

    assert payload.role == "user"
    assert users_service.requests == 1  # exactly one refresh was needed


@pytest.mark.parametrize("garbage", ["", "abc", "a.b.c", "Bearer token"])
async def test_garbage_token(users_service: UsersServiceStub, garbage: str) -> None:
    with pytest.raises(InvalidTokenError):
        await UsersJWTVerifier(KEY_URL).verify(garbage)


async def test_users_service_down_and_no_cached_key(
    users_service: UsersServiceStub, make_token: Callable[..., str]
) -> None:
    users_service.status = 503

    with pytest.raises(InvalidTokenError, match="not available"):
        await UsersJWTVerifier(KEY_URL).verify(make_token())


async def test_users_service_down_but_key_is_cached(
    users_service: UsersServiceStub, make_token: Callable[..., str]
) -> None:
    verifier = UsersJWTVerifier(KEY_URL, cache_seconds=0)
    await verifier.verify(make_token())
    users_service.status = 503
    time.sleep(0.01)  # cache expired, refresh fails -> the last known key is still used

    payload = await verifier.verify(make_token())

    assert payload.role == "user"

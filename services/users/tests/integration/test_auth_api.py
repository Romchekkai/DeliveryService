import httpx
import jwt
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from user_service.domain.value_objects.email import Email
from user_service.infrastructure.db.repositories import SqlAlchemyUserRepository

PASSWORD = "password123"


async def register(client: httpx.AsyncClient, email: str = "api@example.com") -> httpx.Response:
    return await client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})


async def login(client: httpx.AsyncClient, email: str = "api@example.com") -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestRegisterAPI:
    async def test_register_201(self, client: httpx.AsyncClient) -> None:
        response = await register(client)

        assert response.status_code == 201
        body = response.json()
        assert body["email"] == "api@example.com"
        assert body["role"] == "user"
        assert body["status"] == "active"
        assert body["id"]
        assert "password" not in body and "password_hash" not in body

    async def test_register_duplicate_409(self, client: httpx.AsyncClient) -> None:
        await register(client)

        response = await register(client)

        assert response.status_code == 409

    @pytest.mark.parametrize(
        "payload",
        [
            {"email": "not-an-email", "password": PASSWORD},
            {"email": "ok@example.com", "password": "short"},
            {"email": "ok@example.com"},
            {"password": PASSWORD},
            {},
        ],
    )
    async def test_register_invalid_payload_422(
        self, client: httpx.AsyncClient, payload: dict[str, str]
    ) -> None:
        response = await client.post("/api/v1/auth/register", json=payload)

        assert response.status_code == 422


class TestLoginAPI:
    async def test_login_200(self, client: httpx.AsyncClient) -> None:
        await register(client)

        body = await login(client)

        assert body["token_type"] == "bearer"
        assert body["access_token"].count(".") == 2
        assert body["refresh_token"]

    async def test_login_wrong_password_401(self, client: httpx.AsyncClient) -> None:
        await register(client)

        response = await client.post(
            "/api/v1/auth/login", json={"email": "api@example.com", "password": "wrong-password"}
        )

        assert response.status_code == 401

    async def test_login_unknown_user_401(self, client: httpx.AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/login", json={"email": "ghost@example.com", "password": PASSWORD}
        )

        assert response.status_code == 401

    async def test_blocked_user_cannot_login(
        self, client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await register(client)
        async with session_factory() as session:
            repo = SqlAlchemyUserRepository(session)
            user = await repo.get_by_email(Email("api@example.com"))
            assert user is not None
            user.block()
            await repo.update(user)

        response = await client.post(
            "/api/v1/auth/login", json={"email": "api@example.com", "password": PASSWORD}
        )

        assert response.status_code == 401

    async def test_access_token_is_verifiable_with_the_published_public_key(
        self, client: httpx.AsyncClient
    ) -> None:
        """Contract with the delivery service: it downloads /keys/public and verifies tokens."""
        user_id = (await register(client)).json()["id"]
        access_token = (await login(client))["access_token"]
        public_key = (await client.get("/api/v1/keys/public")).text.strip()

        claims = jwt.decode(access_token, public_key, algorithms=["RS256"])

        assert claims["sub"] == user_id
        assert claims["role"] == "user"


class TestRefreshAPI:
    async def test_refresh_200(self, client: httpx.AsyncClient) -> None:
        await register(client)
        tokens = await login(client)

        response = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )

        assert response.status_code == 200
        assert response.json()["refresh_token"] != tokens["refresh_token"]
        assert response.json()["access_token"]

    async def test_refresh_invalid_401(self, client: httpx.AsyncClient) -> None:
        response = await client.post("/api/v1/auth/refresh", json={"refresh_token": "nope"})

        assert response.status_code == 401

    async def test_refresh_token_can_be_used_only_once(self, client: httpx.AsyncClient) -> None:
        await register(client)
        tokens = await login(client)
        payload = {"refresh_token": tokens["refresh_token"]}
        assert (await client.post("/api/v1/auth/refresh", json=payload)).status_code == 200

        response = await client.post("/api/v1/auth/refresh", json=payload)

        assert response.status_code == 401


class TestMeAPI:
    async def test_me_after_register(self, client: httpx.AsyncClient) -> None:
        user_id = (await register(client)).json()["id"]
        tokens = await login(client)

        response = await client.get("/api/v1/auth/me", headers=bearer(tokens["access_token"]))

        assert response.status_code == 200, response.text
        assert response.json() == {
            "id": user_id,
            "email": "api@example.com",
            "role": "user",
            "status": "active",
        }

    async def test_me_without_token_is_rejected(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/api/v1/auth/me")

        assert response.status_code in (401, 403)

    async def test_me_with_garbage_token_401(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/api/v1/auth/me", headers=bearer("garbage"))

        assert response.status_code == 401


class TestKeysAPI:
    async def test_public_key_is_pem(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/api/v1/keys/public")

        assert response.status_code == 200
        assert response.text.startswith("-----BEGIN PUBLIC KEY-----")

    async def test_jwks(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/api/v1/.well-known/jwks.json")

        assert response.status_code == 200
        [key] = response.json()["keys"]
        assert key["kty"] == "RSA" and key["alg"] == "RS256" and key["kid"] == "1"


class TestOperationalEndpoints:
    async def test_health(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    async def test_metrics(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/metrics")

        assert response.status_code == 200
        assert "http_requests_total" in response.text or "python_info" in response.text

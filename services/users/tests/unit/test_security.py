import base64
from datetime import datetime, timezone
from uuid import uuid4

import jwt
import pytest
import requests.exceptions
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from hvac.exceptions import VaultError
from user_service.domain.exceptions import InvalidTokenError
from user_service.domain.value_objects.role import Role
from user_service.infrastructure.config import VaultSettings
from user_service.infrastructure.security import vault_client_factory
from user_service.infrastructure.security.jwks_converter import pem_to_jwk
from user_service.infrastructure.security.jwt_service import VaultJWTTokenService
from user_service.infrastructure.security.password_hasher import BcryptPasswordHasher
from user_service.infrastructure.security.refresh_token_hasher import Sha256RefreshTokenHasher
from user_service.infrastructure.security.vault_exceptions import VaultConnectionError
from user_service.infrastructure.security.vault_transit_signer import VaultTransitSigner

from tests.fakes.vault import FakeVaultClient, public_pem


def make_service(
    client: FakeVaultClient | None = None, expire_minutes: int = 30
) -> tuple[VaultJWTTokenService, FakeVaultClient]:
    client = client or FakeVaultClient()
    signer = VaultTransitSigner(client, "user-service-jwt")  # type: ignore[arg-type]
    return VaultJWTTokenService(signer=signer, expire_minutes=expire_minutes), client


class TestBcryptPasswordHasher:
    def test_hash_and_verify(self) -> None:
        hasher = BcryptPasswordHasher()
        hashed = hasher.hash_password("s3cret-pass")

        assert hashed != "s3cret-pass"
        assert hasher.verify_password("s3cret-pass", hashed)
        assert not hasher.verify_password("other-pass", hashed)

    def test_same_password_gives_different_hashes(self) -> None:
        hasher = BcryptPasswordHasher()

        assert hasher.hash_password("same") != hasher.hash_password("same")


class TestSha256RefreshTokenHasher:
    def test_hash_is_deterministic_hex_of_64_chars(self) -> None:
        hasher = Sha256RefreshTokenHasher()
        digest = hasher.hash("token")

        assert digest == hasher.hash("token")
        assert len(digest) == 64  # matches RefreshTokenModel.token_hash String(64)
        int(digest, 16)

    def test_different_tokens_have_different_hashes(self) -> None:
        hasher = Sha256RefreshTokenHasher()

        assert hasher.hash("a") != hasher.hash("b")

    def test_raw_tokens_are_unique_and_long(self) -> None:
        hasher = Sha256RefreshTokenHasher()
        tokens = {hasher.generate_raw_token() for _ in range(50)}

        assert len(tokens) == 50
        assert all(len(t) >= 80 for t in tokens)


class TestVaultJWTTokenService:
    def test_token_roundtrip(self) -> None:
        service, _ = make_service()
        user_id = uuid4()

        payload = service.decode_token(service.generate_access_token(user_id, Role.ADMIN))

        assert payload.user_id == user_id
        assert payload.role is Role.ADMIN

    def test_header_and_claims(self) -> None:
        service, _ = make_service(expire_minutes=30)
        user_id = uuid4()
        before = int(datetime.now(timezone.utc).timestamp())

        token = service.generate_access_token(user_id, Role.USER)

        assert jwt.get_unverified_header(token) == {"alg": "RS256", "typ": "JWT", "kid": "1"}
        claims = jwt.decode(token, options={"verify_signature": False})
        assert claims["sub"] == str(user_id)
        assert claims["role"] == "user"
        assert claims["iat"] >= before
        assert claims["exp"] - claims["iat"] == 30 * 60

    def test_token_is_accepted_by_a_standard_jwt_library(self) -> None:
        """Contract with the delivery service, which verifies tokens with plain PyJWT."""
        service, _ = make_service()
        user_id = uuid4()
        token = service.generate_access_token(user_id, Role.USER)

        claims = jwt.decode(token, service.get_public_key_pem(), algorithms=["RS256"])

        assert claims["sub"] == str(user_id)

    def test_expired_token_is_rejected(self) -> None:
        service, _ = make_service(expire_minutes=-1)
        token = service.generate_access_token(uuid4(), Role.USER)

        with pytest.raises(InvalidTokenError, match=r"(?i)expired|истёк"):
            service.decode_token(token)

    def test_tampered_payload_is_rejected(self) -> None:
        service, _ = make_service()
        header, _payload, signature = service.generate_access_token(uuid4(), Role.USER).split(".")
        forged = base64.urlsafe_b64encode(
            b'{"sub":"%s","role":"admin","iat":1,"exp":9999999999}' % str(uuid4()).encode()
        ).rstrip(b"=")

        with pytest.raises(InvalidTokenError):
            service.decode_token(f"{header}.{forged.decode()}.{signature}")

    def test_token_signed_with_foreign_key_is_rejected(self) -> None:
        service, _ = make_service()
        foreign, _ = make_service()  # another key pair, same kid

        with pytest.raises(InvalidTokenError):
            service.decode_token(foreign.generate_access_token(uuid4(), Role.USER))

    @pytest.mark.parametrize("garbage", ["", "abc", "a.b.c", "....", "Bearer x.y.z"])
    def test_garbage_is_rejected(self, garbage: str) -> None:
        service, _ = make_service()

        with pytest.raises(InvalidTokenError):
            service.decode_token(garbage)

    def test_old_key_versions_stay_verifiable_after_rotation(self) -> None:
        client = FakeVaultClient()
        old_service, _ = make_service(client)
        old_token = old_service.generate_access_token(uuid4(), Role.USER)

        client.rotate()
        new_service, _ = make_service(client)

        assert new_service.get_key_id() == "2"
        assert new_service.get_all_key_versions() == [1, 2]
        assert new_service.decode_token(old_token).role is Role.USER  # kid=1 still resolvable
        assert (
            jwt.get_unverified_header(new_service.generate_access_token(uuid4(), Role.USER))["kid"]
            == "2"
        )

    def test_public_key_pem_is_returned(self) -> None:
        service, client = make_service()

        assert service.get_public_key_pem() == public_pem(client.private_key())


class TestVaultTransitSigner:
    def test_sign_returns_unpadded_base64url(self) -> None:
        signer = VaultTransitSigner(FakeVaultClient(), "key")  # type: ignore[arg-type]

        signature = signer.sign(b"data")

        assert "=" not in signature
        assert "+" not in signature and "/" not in signature

    def test_key_versions(self) -> None:
        signer = VaultTransitSigner(FakeVaultClient(versions=3), "key")  # type: ignore[arg-type]

        assert signer.get_latest_key_version() == 3
        assert signer.get_all_key_versions() == [1, 2, 3]

    def test_specific_public_key_version(self) -> None:
        client = FakeVaultClient(versions=2)
        signer = VaultTransitSigner(client, "key")  # type: ignore[arg-type]

        assert signer.get_public_key_pem(version=1) == public_pem(client.private_key(1))
        assert signer.get_public_key_pem() == public_pem(client.private_key(2))

    def test_vault_errors_are_wrapped(self) -> None:
        client = FakeVaultClient()

        def boom(*args: object, **kwargs: object) -> None:
            raise VaultError("vault is down")

        client.secrets.transit.sign_data = boom
        client.secrets.transit.read_key = boom
        signer = VaultTransitSigner(client, "key")  # type: ignore[arg-type]

        with pytest.raises(VaultConnectionError):
            signer.sign(b"data")
        with pytest.raises(VaultConnectionError):
            signer.get_public_key_pem()
        with pytest.raises(VaultConnectionError):
            signer.get_latest_key_version()
        with pytest.raises(VaultConnectionError):
            signer.get_all_key_versions()


class TestJwksConverter:
    def test_rsa_key_is_converted_to_jwk(self) -> None:
        client = FakeVaultClient()
        key = client.private_key()

        jwk = pem_to_jwk(public_pem(key), kid="7")

        assert jwk["kty"] == "RSA" and jwk["alg"] == "RS256" and jwk["use"] == "sig"
        assert jwk["kid"] == "7"
        numbers = key.public_key().public_numbers()
        decode = lambda v: int.from_bytes(  # noqa: E731
            base64.urlsafe_b64decode(v + "=" * (-len(v) % 4)), "big"
        )
        assert decode(jwk["n"]) == numbers.n
        assert decode(jwk["e"]) == numbers.e

    def test_non_rsa_key_is_rejected(self) -> None:
        pem = (
            ec.generate_private_key(ec.SECP256R1())
            .public_key()
            .public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
            )
            .decode()
        )

        with pytest.raises(TypeError):
            pem_to_jwk(pem, kid="1")


class TestCreateVaultClient:
    settings = VaultSettings(url="http://vault:8200", token="t")

    def _patch_client(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        authenticated: bool = True,
        error: Exception | None = None,
    ) -> None:
        class FakeHvacClient:
            def __init__(self, url: str, token: str) -> None:
                self.url, self.token = url, token

            def is_authenticated(self) -> bool:
                if error:
                    raise error
                return authenticated

        monkeypatch.setattr(vault_client_factory.hvac, "Client", FakeHvacClient)

    def test_returns_authenticated_client(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._patch_client(monkeypatch)

        client = vault_client_factory.create_vault_client(self.settings)

        assert client.url == "http://vault:8200"

    def test_unreachable_vault(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._patch_client(monkeypatch, error=requests.exceptions.ConnectionError("refused"))

        with pytest.raises(VaultConnectionError, match="недоступен"):
            vault_client_factory.create_vault_client(self.settings)

    def test_vault_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._patch_client(monkeypatch, error=VaultError("boom"))

        with pytest.raises(VaultConnectionError):
            vault_client_factory.create_vault_client(self.settings)

    def test_bad_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._patch_client(monkeypatch, authenticated=False)

        with pytest.raises(VaultConnectionError, match="VAULT_TOKEN"):
            vault_client_factory.create_vault_client(self.settings)

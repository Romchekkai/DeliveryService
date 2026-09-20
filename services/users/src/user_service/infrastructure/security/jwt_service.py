import base64
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt

from user_service.application.interfaces.token_payload import TokenPayload
from user_service.application.interfaces.token_service import TokenService
from user_service.domain.exceptions import InvalidTokenError
from user_service.domain.value_objects.role import Role
from user_service.infrastructure.security.vault_transit_signer import VaultTransitSigner


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class VaultJWTTokenService(TokenService):
    def __init__(self, signer: VaultTransitSigner, expire_minutes: int = 30):
        self._signer = signer
        self._expire_minutes = expire_minutes
        self._current_version = signer.get_latest_key_version()
        self._public_key_pem = signer.get_public_key_pem(version=self._current_version)

    def get_key_id(self) -> str:
        return str(self._current_version)

    def get_public_key_pem(self, version: int | None = None) -> str:
        if version is None or version == self._current_version:
            return self._public_key_pem
        return self._signer.get_public_key_pem(version=version)

    def get_all_key_versions(self) -> list[int]:
        return self._signer.get_all_key_versions()

    def generate_access_token(self, user_id: UUID, role: Role) -> str:
        now = datetime.now(timezone.utc)
        header = {"alg": "RS256", "typ": "JWT", "kid": self.get_key_id()}
        payload = {
            "sub": str(user_id),
            "role": role.value,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=self._expire_minutes)).timestamp()),
        }

        header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
        payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
        signing_input = f"{header_b64}.{payload_b64}"

        signature_b64 = self._signer.sign(signing_input.encode())

        return f"{signing_input}.{signature_b64}"

    def decode_token(self, token: str) -> TokenPayload:
        try:
            unverified_header = jwt.get_unverified_header(token)
            token_kid = unverified_header.get("kid")

            public_key_pem = self.get_public_key_pem(version=int(token_kid) if token_kid else None)

            payload = jwt.decode(token, public_key_pem, algorithms=["RS256"])
        except jwt.ExpiredSignatureError:
            raise InvalidTokenError("Token expired")
        except jwt.InvalidTokenError:
            raise InvalidTokenError("Invalid token")

        return TokenPayload(
            user_id=UUID(payload["sub"]),
            role=Role(payload["role"]),
        )

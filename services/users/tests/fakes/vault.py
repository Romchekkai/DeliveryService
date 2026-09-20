"""In-memory stand-in for ``hvac.Client`` (Vault Transit engine).

It signs with real RSA keys, so ``VaultTransitSigner`` / ``VaultJWTTokenService`` run their
production code paths - only the network hop to Vault is replaced.
"""

from __future__ import annotations

import base64
from types import SimpleNamespace
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


def _new_key() -> rsa.RSAPrivateKey:
    # 2048 bits like the real transit key (rsa-2048).
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def public_pem(key: rsa.RSAPrivateKey) -> str:
    return (
        key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )


class FakeVaultClient:
    def __init__(self, versions: int = 1) -> None:
        self._keys: dict[int, rsa.RSAPrivateKey] = {}
        for _ in range(versions):
            self.rotate()
        self.secrets = SimpleNamespace(
            transit=SimpleNamespace(read_key=self._read_key, sign_data=self._sign_data)
        )

    def rotate(self) -> int:
        version = max(self._keys, default=0) + 1
        self._keys[version] = _new_key()
        return version

    def private_key(self, version: int | None = None) -> rsa.RSAPrivateKey:
        return self._keys[version or max(self._keys)]

    # --- hvac.Client.secrets.transit API used by the service -----------------------------

    def _read_key(self, name: str) -> dict[str, Any]:
        return {
            "data": {"keys": {str(v): {"public_key": public_pem(k)} for v, k in self._keys.items()}}
        }

    def _sign_data(
        self,
        name: str,
        hash_input: str,
        signature_algorithm: str = "pkcs1v15",
        hash_algorithm: str = "sha2-256",
    ) -> dict[str, Any]:
        assert signature_algorithm == "pkcs1v15"
        assert hash_algorithm == "sha2-256"
        version = max(self._keys)
        signature = self._keys[version].sign(
            base64.b64decode(hash_input), padding.PKCS1v15(), hashes.SHA256()
        )
        return {"data": {"signature": f"vault:v{version}:{base64.b64encode(signature).decode()}"}}

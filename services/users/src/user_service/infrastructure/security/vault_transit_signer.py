# infrastructure/security/vault_transit_signer.py (дополнение — обработка ошибок при чтении ключа)
import base64
from typing import Any

import hvac
from hvac.exceptions import VaultError

from user_service.infrastructure.security.vault_exceptions import VaultConnectionError


class VaultTransitSigner:
    def __init__(self, client: hvac.Client, key_name: str):
        self._client = client
        self._key_name = key_name

    def sign(self, data: bytes) -> str:
        input_b64 = base64.b64encode(data).decode()
        try:
            response = self._client.secrets.transit.sign_data(
                name=self._key_name,
                hash_input=input_b64,
                signature_algorithm="pkcs1v15",
                hash_algorithm="sha2-256",
            )
        except VaultError as e:
            raise VaultConnectionError(
                f"Не удалось подписать данные через Vault Transit: {e}"
            ) from e

        vault_signature = response["data"]["signature"]
        raw_b64 = vault_signature.split(":", 2)[2]
        raw_bytes = base64.b64decode(raw_b64)
        return base64.urlsafe_b64encode(raw_bytes).rstrip(b"=").decode()

    def get_public_key_pem(self, version: int | None = None) -> str | Any:
        try:
            response = self._client.secrets.transit.read_key(name=self._key_name)
        except VaultError as e:
            raise VaultConnectionError(
                f"Не удалось прочитать ключ '{self._key_name}' из Vault Transit: {e}"
            ) from e

        keys = response["data"]["keys"]
        target_version = str(version or max(int(v) for v in keys.keys()))
        return keys[target_version]["public_key"]

    def get_latest_key_version(self) -> int:
        """Текущая (последняя) версия ключа — используется как kid при подписи."""
        try:
            response = self._client.secrets.transit.read_key(name=self._key_name)
        except VaultError as e:
            raise VaultConnectionError(
                f"Не удалось прочитать ключ '{self._key_name}' из Vault Transit: {e}"
            ) from e

        keys = response["data"]["keys"]
        return max(int(v) for v in keys.keys())

    def get_all_key_versions(self) -> list[int]:
        """Все версии ключа, известные Vault — нужно для JWKS во время ротации,
        чтобы отдавать не только последнюю, но и ещё не истёкшие старые версии."""
        try:
            response = self._client.secrets.transit.read_key(name=self._key_name)
        except VaultError as e:
            raise VaultConnectionError(
                f"Не удалось прочитать ключ '{self._key_name}' из Vault Transit: {e}"
            ) from e

        keys = response["data"]["keys"]
        return sorted(int(v) for v in keys.keys())

import hvac
import requests.exceptions
from hvac.exceptions import VaultError

from user_service.infrastructure.config import VaultSettings
from user_service.infrastructure.security.vault_exceptions import VaultConnectionError


def create_vault_client(settings: VaultSettings) -> hvac.Client:
    try:
        client = hvac.Client(url=settings.url, token=settings.token)
    except Exception as e:
        raise VaultConnectionError(
            f"Не удалось создать клиент Vault по адресу {settings.url}: {e}"
        ) from e

    try:
        is_authenticated = client.is_authenticated()
    except requests.exceptions.ConnectionError as e:
        raise VaultConnectionError(
            f"Vault недоступен по адресу {settings.url}. "
            f"Проверьте, что контейнер vault-dev запущен."
        ) from e
    except VaultError as e:
        raise VaultConnectionError(f"Ошибка Vault при проверке аутентификации: {e}") from e

    if not is_authenticated:
        raise VaultConnectionError("Аутентификация в Vault не удалась — проверьте VAULT_TOKEN.")

    return client

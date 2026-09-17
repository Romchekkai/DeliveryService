# infrastructure/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DB_", env_file=".env", extra="ignore")

    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: str
    name: str = "user_service_db"

    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 1800
    pool_pre_ping: bool = True
    echo: bool = False

    @property
    def url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"
        )


class VaultSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VAULT_", env_file=".env", extra="ignore")

    url: str = "http://localhost:8200"
    token: str
    transit_key_name: str = "user-service-jwt"


class JWTSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JWT_", env_file=".env", extra="ignore")

    expire_minutes: int = 30


# Инстансы — создаются один раз при импорте модуля, используются везде через импорт
db_settings = DatabaseSettings()  # type: ignore[call-arg]
vault_settings = VaultSettings()  # type: ignore[call-arg]
jwt_settings = JWTSettings()

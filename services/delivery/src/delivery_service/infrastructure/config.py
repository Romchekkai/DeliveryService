from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DB_", env_file=".env", extra="ignore")

    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: str
    name: str = "delivery_service_db"

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


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REDIS_", env_file=".env", extra="ignore")

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    rate_key: str = "fx:usd_rub"
    rate_ttl_seconds: int = 3600  # курс ЦБ обновляется раз в сутки, часа кэша достаточно

    @property
    def url(self) -> str:
        return f"redis://{self.host}:{self.port}/{self.db}"


class FxSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FX_", env_file=".env", extra="ignore")

    url: str = "https://www.cbr-xml-daily.ru/daily_json.js"
    timeout_seconds: int = 10


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AUTH_", env_file=".env", extra="ignore")

    # публичный ключ users-сервиса для локальной проверки подписи JWT
    public_key_url: str = "http://localhost:8000/api/v1/keys/public"
    algorithm: str = "RS256"
    public_key_cache_seconds: int = 300


class SchedulerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCHEDULER_", env_file=".env", extra="ignore")

    enabled: bool = True
    calculate_costs_interval_minutes: int = 5


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "dev"
    sentry_dsn: str = ""
    json_logs: bool = True


db_settings = DatabaseSettings()  # type: ignore[call-arg]
redis_settings = RedisSettings()
fx_settings = FxSettings()
auth_settings = AuthSettings()
scheduler_settings = SchedulerSettings()
app_settings = AppSettings()

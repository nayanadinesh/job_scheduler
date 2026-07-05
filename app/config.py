from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://scheduler:scheduler@localhost:5432/scheduler"
    secret_key: str = "dev-secret-change-in-prod"
    access_token_expire_minutes: int = 60
    environment: str = "development"
    log_level: str = "INFO"

    # Worker tuning
    worker_count: int = 2
    poll_interval_ms: int = 500
    heartbeat_interval_s: int = 5
    visibility_timeout_s: int = 30
    reaper_interval_s: int = 10


settings = Settings()

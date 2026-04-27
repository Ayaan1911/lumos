from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    test_database_url: str | None = None
    database_min_pool_size: int = 1
    database_max_pool_size: int = 10
    admin_token: str
    issuer_key_path: str = ".lumos/issuer_ed25519.key"
    nonce_ttl_seconds: int = 60
    timestamp_skew_seconds: int = 30
    session_ttl_seconds: int = 600
    capability_ttl_seconds: int = 300

    model_config = SettingsConfigDict(
        env_prefix="LUMOS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

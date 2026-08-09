from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Usage Metering & Billing Engine"
    app_env: str = "development"
    debug: bool = True

    database_url: str

    jwt_secret: str
    jwt_algorithm: str = "HS256"

    stripe_secret_key: str
    stripe_webhook_secret: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
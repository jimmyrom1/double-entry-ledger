from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = (
        "postgresql://app:app@localhost:5432/subscriptions_test?options=-c%20search_path%3Dledger"
    )
    TEST_DATABASE_URL: str = "postgresql://app:app@localhost:5432/subscriptions_test?options=-c%20search_path%3Dledger_test"
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:5173",
    ]
    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

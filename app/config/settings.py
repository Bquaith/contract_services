from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="data-contracts-service")
    app_env: str = Field(default="dev")
    debug: bool = Field(default=False)
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    log_level: str = Field(
        default="INFO", validation_alias=AliasChoices("DATA_CONTRACTS_LOG_LEVEL", "LOG_LEVEL")
    )
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/data_contracts",
        validation_alias=AliasChoices("DATA_CONTRACTS_DATABASE_URL", "DATABASE_URL"),
    )
    api_key: str = Field(
        default="dev-api-key", validation_alias=AliasChoices("DATA_CONTRACTS_API_KEY", "API_KEY")
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

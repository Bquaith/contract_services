from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="data-contracts-service")
    app_env: str = Field(default="dev")
    debug: bool = Field(
        default=False,
        validation_alias=AliasChoices("DATA_CONTRACTS_DEBUG", "APP_DEBUG"),
    )
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
    auth_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("DATA_CONTRACTS_AUTH_ENABLED", "AUTH_ENABLED"),
    )
    auth_issuer_url: str = Field(
        default="http://localhost:8081/realms/vkr",
        validation_alias=AliasChoices("DATA_CONTRACTS_AUTH_ISSUER_URL", "AUTH_ISSUER_URL"),
    )
    auth_jwks_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DATA_CONTRACTS_AUTH_JWKS_URL", "AUTH_JWKS_URL"),
    )
    auth_jwks_json: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DATA_CONTRACTS_AUTH_JWKS_JSON", "AUTH_JWKS_JSON"),
    )
    auth_audience: str = Field(
        default="contracts-api",
        validation_alias=AliasChoices("DATA_CONTRACTS_AUTH_AUDIENCE", "AUTH_AUDIENCE"),
    )
    auth_swagger_client_id: str = Field(
        default="contracts-ui-dev",
        validation_alias=AliasChoices(
            "DATA_CONTRACTS_AUTH_SWAGGER_CLIENT_ID",
            "AUTH_SWAGGER_CLIENT_ID",
        ),
    )
    auth_swagger_use_pkce: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "DATA_CONTRACTS_AUTH_SWAGGER_USE_PKCE",
            "AUTH_SWAGGER_USE_PKCE",
        ),
    )
    auth_roles_claim: str = Field(
        default="system_roles",
        validation_alias=AliasChoices("DATA_CONTRACTS_AUTH_ROLES_CLAIM", "AUTH_ROLES_CLAIM"),
    )
    auth_username_claim: str = Field(
        default="preferred_username",
        validation_alias=AliasChoices("DATA_CONTRACTS_AUTH_USERNAME_CLAIM", "AUTH_USERNAME_CLAIM"),
    )
    auth_allowed_algorithms: str = Field(
        default="RS256",
        validation_alias=AliasChoices(
            "DATA_CONTRACTS_AUTH_ALLOWED_ALGORITHMS",
            "AUTH_ALLOWED_ALGORITHMS",
        ),
    )
    auth_http_timeout_seconds: float = Field(
        default=5.0,
        validation_alias=AliasChoices(
            "DATA_CONTRACTS_AUTH_HTTP_TIMEOUT_SECONDS",
            "AUTH_HTTP_TIMEOUT_SECONDS",
        ),
    )
    auth_jwks_cache_ttl_seconds: int = Field(
        default=300,
        validation_alias=AliasChoices(
            "DATA_CONTRACTS_AUTH_JWKS_CACHE_TTL_SECONDS",
            "AUTH_JWKS_CACHE_TTL_SECONDS",
        ),
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def resolved_auth_jwks_url(self) -> str:
        if self.auth_jwks_url:
            return self.auth_jwks_url
        issuer = self.auth_issuer_url.rstrip("/")
        return f"{issuer}/protocol/openid-connect/certs"

    @property
    def resolved_auth_authorization_url(self) -> str:
        issuer = self.auth_issuer_url.rstrip("/")
        return f"{issuer}/protocol/openid-connect/auth"

    @property
    def resolved_auth_token_url(self) -> str:
        issuer = self.auth_issuer_url.rstrip("/")
        return f"{issuer}/protocol/openid-connect/token"

    @property
    def parsed_auth_algorithms(self) -> tuple[str, ...]:
        return tuple(
            item.strip() for item in self.auth_allowed_algorithms.split(",") if item.strip()
        ) or ("RS256",)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

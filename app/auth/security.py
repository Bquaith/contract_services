from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import jwt
from fastapi import Depends, Request, Security
from fastapi.security import OAuth2AuthorizationCodeBearer
from jwt import ExpiredSignatureError, InvalidAudienceError, InvalidIssuerError, InvalidTokenError
from jwt.algorithms import RSAAlgorithm

from app.api.errors import ApiError
from app.config import Settings, get_settings

ROLE_ADMIN = "admin"
ROLE_CONSUMER = "consumer"
ROLE_CONTRACTS_READER = "contracts_reader"
ROLE_PRODUCER = "producer"

READ_ROLES = (
    ROLE_ADMIN,
    ROLE_CONSUMER,
    ROLE_CONTRACTS_READER,
    ROLE_PRODUCER,
)
WRITE_ROLES = (
    ROLE_ADMIN,
    ROLE_PRODUCER,
)
ADMIN_ROLES = (ROLE_ADMIN,)
SCHEMA_ROLES = (
    ROLE_ADMIN,
    ROLE_PRODUCER,
)
AUTH_DISABLED_ROLES = tuple(dict.fromkeys(READ_ROLES + WRITE_ROLES))
OIDC_SWAGGER_SCHEME_NAME = "KeycloakOIDC"
OIDC_SWAGGER_SCOPES = {
    "openid": "OpenID Connect login",
    "profile": "Basic profile information",
    "email": "User email",
}


@dataclass(frozen=True)
class Principal:
    subject: str
    username: str
    roles: tuple[str, ...]
    issued_for: str | None = None
    claims: dict[str, Any] | None = None

    @property
    def actor(self) -> str:
        return self.username or self.subject

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl="http://localhost/oidc/auth",
    tokenUrl="http://localhost/oidc/token",
    scopes=OIDC_SWAGGER_SCOPES,
    auto_error=False,
    scheme_name=OIDC_SWAGGER_SCHEME_NAME,
)


class OIDCTokenVerifier:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._jwks_lock = threading.Lock()
        self._jwks_cache: dict[str, Any] | None = None
        self._jwks_loaded_at = 0.0

    def verify(self, token: str) -> Principal:
        try:
            header = jwt.get_unverified_header(token)
        except InvalidTokenError as exc:
            raise ApiError(
                status_code=401,
                code="invalid_token",
                message="Malformed bearer token",
                details={},
            ) from exc

        algorithm = str(header.get("alg") or "").strip()
        if algorithm not in self.settings.parsed_auth_algorithms:
            raise ApiError(
                status_code=401,
                code="invalid_token",
                message="Unsupported signing algorithm",
                details={"alg": algorithm},
            )

        signing_key = self._resolve_signing_key(header.get("kid"))
        try:
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=list(self.settings.parsed_auth_algorithms),
                audience=self.settings.auth_audience,
                issuer=self.settings.auth_issuer_url,
                options={"require": ["exp", "iat", "sub"]},
            )
        except ExpiredSignatureError as exc:
            raise ApiError(
                status_code=401,
                code="token_expired",
                message="Bearer token has expired",
                details={},
            ) from exc
        except InvalidAudienceError as exc:
            raise ApiError(
                status_code=401,
                code="invalid_token",
                message="Bearer token has invalid audience",
                details={"audience": self.settings.auth_audience},
            ) from exc
        except InvalidIssuerError as exc:
            raise ApiError(
                status_code=401,
                code="invalid_token",
                message="Bearer token has invalid issuer",
                details={"issuer": self.settings.auth_issuer_url},
            ) from exc
        except InvalidTokenError as exc:
            raise ApiError(
                status_code=401,
                code="invalid_token",
                message="Bearer token validation failed",
                details={},
            ) from exc

        roles = self._extract_roles(claims)
        subject = str(claims.get("sub") or "").strip()
        username = self._principal_username(claims, subject)

        return Principal(
            subject=subject,
            username=username,
            roles=roles,
            issued_for=self._optional_str(claims.get("azp")),
            claims=dict(claims),
        )

    def _principal_username(self, claims: dict[str, Any], subject: str) -> str:
        preferred = self._optional_str(claims.get(self.settings.auth_username_claim))
        if preferred:
            return preferred

        issued_for = self._optional_str(claims.get("azp"))
        if issued_for:
            return issued_for

        client_id = self._optional_str(claims.get("clientId"))
        if client_id:
            return client_id

        return subject

    def _extract_roles(self, claims: dict[str, Any]) -> tuple[str, ...]:
        collected: list[str] = []

        configured_roles = claims.get(self.settings.auth_roles_claim)
        if isinstance(configured_roles, list):
            collected.extend(str(item).strip() for item in configured_roles if str(item).strip())
        elif isinstance(configured_roles, str) and configured_roles.strip():
            collected.append(configured_roles.strip())

        realm_access = claims.get("realm_access")
        if isinstance(realm_access, dict):
            raw_realm_roles = realm_access.get("roles")
            if isinstance(raw_realm_roles, list):
                collected.extend(str(item).strip() for item in raw_realm_roles if str(item).strip())

        resource_access = claims.get("resource_access")
        if isinstance(resource_access, dict):
            for resource_claim in resource_access.values():
                if not isinstance(resource_claim, dict):
                    continue
                raw_resource_roles = resource_claim.get("roles")
                if isinstance(raw_resource_roles, list):
                    collected.extend(str(item).strip() for item in raw_resource_roles if str(item).strip())

        return tuple(dict.fromkeys(item for item in collected if item))

    def _resolve_signing_key(self, kid: Any) -> Any:
        key_id = self._optional_str(kid)
        jwks = self._load_jwks(force_refresh=False)
        key_data = self._find_key(jwks, key_id)
        if key_data is None:
            jwks = self._load_jwks(force_refresh=True)
            key_data = self._find_key(jwks, key_id)

        if key_data is None:
            raise ApiError(
                status_code=401,
                code="invalid_token",
                message="Signing key was not found in JWKS",
                details={"kid": key_id or ""},
            )

        return RSAAlgorithm.from_jwk(json.dumps(key_data))

    def _load_jwks(self, force_refresh: bool) -> dict[str, Any]:
        static_jwks = self.settings.auth_jwks_json
        if static_jwks:
            try:
                payload = json.loads(static_jwks)
            except json.JSONDecodeError as exc:
                raise ApiError(
                    status_code=500,
                    code="auth_configuration_error",
                    message="Configured AUTH_JWKS_JSON is not valid JSON",
                    details={},
                ) from exc
            if not isinstance(payload, dict):
                raise ApiError(
                    status_code=500,
                    code="auth_configuration_error",
                    message="Configured AUTH_JWKS_JSON must be a JSON object",
                    details={},
                )
            return payload

        now = time.monotonic()
        with self._jwks_lock:
            is_cache_valid = (
                self._jwks_cache is not None
                and (now - self._jwks_loaded_at) < self.settings.auth_jwks_cache_ttl_seconds
            )
            if not force_refresh and is_cache_valid:
                return self._jwks_cache

            payload = self._fetch_jwks()
            self._jwks_cache = payload
            self._jwks_loaded_at = now
            return payload

    def _fetch_jwks(self) -> dict[str, Any]:
        try:
            with urlopen(
                self.settings.resolved_auth_jwks_url,
                timeout=self.settings.auth_http_timeout_seconds,
            ) as response:
                raw_payload = response.read().decode("utf-8")
        except HTTPError as exc:
            raise ApiError(
                status_code=503,
                code="auth_unavailable",
                message="Unable to fetch JWKS from identity provider",
                details={"status_code": exc.code},
            ) from exc
        except URLError as exc:
            raise ApiError(
                status_code=503,
                code="auth_unavailable",
                message="Unable to reach identity provider JWKS endpoint",
                details={"reason": str(exc.reason)},
            ) from exc

        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError as exc:
            raise ApiError(
                status_code=503,
                code="auth_unavailable",
                message="Identity provider returned malformed JWKS payload",
                details={},
            ) from exc

        if not isinstance(payload, dict):
            raise ApiError(
                status_code=503,
                code="auth_unavailable",
                message="Identity provider returned invalid JWKS payload",
                details={},
            )

        return payload

    @staticmethod
    def _find_key(jwks: dict[str, Any], kid: str | None) -> dict[str, Any] | None:
        raw_keys = jwks.get("keys")
        if not isinstance(raw_keys, list):
            return None

        for item in raw_keys:
            if not isinstance(item, dict):
                continue
            if kid and str(item.get("kid") or "").strip() != kid:
                continue
            return item
        return None

    @staticmethod
    def _optional_str(value: Any) -> str | None:
        text_value = str(value or "").strip()
        return text_value or None


@lru_cache(maxsize=1)
def get_token_verifier() -> OIDCTokenVerifier:
    return OIDCTokenVerifier(get_settings())


def configure_swagger_oidc(settings: Settings) -> None:
    flow = oauth2_scheme.model.flows.authorizationCode
    if flow is None:
        return
    flow.authorizationUrl = settings.resolved_auth_authorization_url
    flow.tokenUrl = settings.resolved_auth_token_url


def build_swagger_init_oauth(settings: Settings) -> dict[str, Any]:
    return {
        "clientId": settings.auth_swagger_client_id,
        "appName": settings.app_name,
        "usePkceWithAuthorizationCodeGrant": settings.auth_swagger_use_pkce,
    }


def get_current_principal(
    request: Request,
    token: str | None = Security(oauth2_scheme, scopes=["openid"]),
) -> Principal:
    settings = get_settings()

    if not settings.auth_enabled:
        return Principal(
            subject="auth-disabled",
            username="system",
            roles=AUTH_DISABLED_ROLES,
            claims={},
        )

    cached_principal = getattr(request.state, "principal", None)
    if isinstance(cached_principal, Principal):
        return cached_principal

    if token is None:
        raise ApiError(
            status_code=401,
            code="unauthorized",
            message="Missing bearer token",
            details={"header": "Authorization"},
        )

    principal = get_token_verifier().verify(token)
    request.state.principal = principal
    return principal


def require_roles(*allowed_roles: str):
    normalized_roles = tuple(dict.fromkeys(role.strip() for role in allowed_roles if role.strip()))

    def _dependency(principal: Principal = Depends(get_current_principal)) -> Principal:
        if not get_settings().auth_enabled:
            return principal

        if set(principal.roles).intersection(normalized_roles):
            return principal

        raise ApiError(
            status_code=403,
            code="forbidden",
            message="Access denied",
            details={},
        )

    return _dependency


require_contract_admin = require_roles(*ADMIN_ROLES)
require_contract_read = require_roles(*READ_ROLES)
require_contract_schema = require_roles(*SCHEMA_ROLES)
require_contract_write = require_roles(*WRITE_ROLES)

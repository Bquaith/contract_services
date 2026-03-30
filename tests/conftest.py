from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.auth import get_token_verifier
from app.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app

TEST_ISSUER_URL = "http://test-keycloak.local/realms/vkr"
TEST_AUDIENCE = "contracts-api"
TEST_KID = "pytest-key-1"
TEST_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
TEST_PUBLIC_JWK = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(TEST_PRIVATE_KEY.public_key()))
TEST_PUBLIC_JWK["kid"] = TEST_KID
TEST_JWKS_JSON = json.dumps({"keys": [TEST_PUBLIC_JWK]})


def _ensure_database_exists(database_url: str) -> None:
    url: URL = make_url(database_url)
    if not url.database:
        return

    admin_url = url.set(database="postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

    with admin_engine.connect() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
            {"db_name": url.database},
        ).scalar()
        if not exists:
            database_name = url.database.replace('"', "")
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))

    admin_engine.dispose()


@pytest.fixture(scope="session")
def test_database_url() -> str:
    return os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/data_contracts_test",
    )


@pytest.fixture(scope="session")
def engine(test_database_url: str):
    _ensure_database_exists(test_database_url)
    engine = create_engine(test_database_url, pool_pre_ping=True)

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    yield engine

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def clean_tables(engine) -> None:
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE'))


@pytest.fixture
def db_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def _build_access_token(
    *,
    username: str,
    roles: list[str],
    subject: str | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject or f"user:{username}",
        "iss": TEST_ISSUER_URL,
        "aud": TEST_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
        "preferred_username": username,
        "system_roles": roles,
    }
    return jwt.encode(
        payload,
        TEST_PRIVATE_KEY,
        algorithm="RS256",
        headers={"kid": TEST_KID},
    )


@pytest.fixture
def client(test_database_url: str, db_session_factory, clean_tables):
    _ = clean_tables
    os.environ["DATABASE_URL"] = test_database_url
    os.environ["AUTH_ENABLED"] = "true"
    os.environ["AUTH_ISSUER_URL"] = TEST_ISSUER_URL
    os.environ["AUTH_AUDIENCE"] = TEST_AUDIENCE
    os.environ["AUTH_JWKS_JSON"] = TEST_JWKS_JSON
    os.environ["AUTH_SWAGGER_CLIENT_ID"] = "contracts-ui-dev"
    get_settings.cache_clear()
    get_token_verifier.cache_clear()

    app = create_app()

    def override_get_db():
        db: Session = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as api_client:
        yield api_client

    app.dependency_overrides.clear()


@pytest.fixture
def write_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_build_access_token(username='pytest-admin', roles=['admin', 'producer', 'consumer'])}",
    }


@pytest.fixture
def read_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_build_access_token(username='pytest-consumer', roles=['consumer'])}",
    }


@pytest.fixture
def contracts_reader_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_build_access_token(username='pytest-airflow', roles=['contracts_reader'])}",
    }

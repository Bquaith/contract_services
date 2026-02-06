from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app


TEST_API_KEY = "test-api-key"


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


@pytest.fixture
def client(test_database_url: str, db_session_factory, clean_tables):
    _ = clean_tables
    os.environ["DATABASE_URL"] = test_database_url
    os.environ["API_KEY"] = TEST_API_KEY
    get_settings.cache_clear()

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
        "X-API-Key": TEST_API_KEY,
        "X-Actor": "pytest",
    }

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.db import get_db
from app.service import CompatibilityService, ContractService, ContractVersionService, ValidationService


DbSession = Annotated[Session, Depends(get_db)]


def get_contract_service(db: DbSession) -> ContractService:
    return ContractService(db)


def get_version_service(db: DbSession) -> ContractVersionService:
    return ContractVersionService(db)


def get_compatibility_service(db: DbSession) -> CompatibilityService:
    return CompatibilityService(db)


def get_validation_service(db: DbSession) -> ValidationService:
    return ValidationService(db)


def get_actor(x_actor: Annotated[str | None, Header(alias="X-Actor")] = None) -> str:
    return x_actor.strip() if x_actor else "system"

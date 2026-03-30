from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.auth import Principal, get_current_principal
from app.config import get_settings
from app.db import get_db
from app.service import (
    CompatibilityService,
    ContractService,
    ContractVersionService,
    IntrospectionService,
    ValidationService,
)

DbSession = Annotated[Session, Depends(get_db)]


def get_contract_service(db: DbSession) -> ContractService:
    return ContractService(db)


def get_version_service(db: DbSession) -> ContractVersionService:
    return ContractVersionService(db)


def get_compatibility_service(db: DbSession) -> CompatibilityService:
    return CompatibilityService(db)


def get_introspection_service(db: DbSession) -> IntrospectionService:
    return IntrospectionService(db)


def get_validation_service(db: DbSession) -> ValidationService:
    return ValidationService(db)


def get_actor(
    principal: Annotated[Principal, Depends(get_current_principal)],
    x_actor: Annotated[str | None, Header(alias="X-Actor")] = None,
) -> str:
    if get_settings().auth_enabled:
        return principal.actor
    return x_actor.strip() if x_actor else "system"

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_version_service
from app.schemas.version import PublishedContractResponse
from app.service import ContractVersionService

router = APIRouter(prefix="/contracts", tags=["publish"])


@router.get("/{namespace}/{name}/active", response_model=PublishedContractResponse)
def get_active_contract(
    namespace: str,
    name: str,
    service: Annotated[ContractVersionService, Depends(get_version_service)],
) -> PublishedContractResponse:
    contract, version = service.get_active_version_by_namespace_name(namespace, name)
    return PublishedContractResponse.model_validate({"contract": contract, "version": version})


@router.get("/{namespace}/{name}/version/{version}", response_model=PublishedContractResponse)
def get_contract_version(
    namespace: str,
    name: str,
    version: str,
    service: Annotated[ContractVersionService, Depends(get_version_service)],
) -> PublishedContractResponse:
    contract, version_row = service.get_version_by_namespace_name(namespace, name, version)
    return PublishedContractResponse.model_validate({"contract": contract, "version": version_row})

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_actor,
    get_compatibility_service,
    get_contract_service,
    get_version_service,
)
from app.schemas.contract import (
    ContractCreateRequest,
    ContractListItem,
    ContractResponse,
    ContractUpdateRequest,
)
from app.schemas.enums import ContractStatus, TargetLayer
from app.schemas.version import (
    CompatibilityCheckRequest,
    CompatibilityCheckResponse,
    ContractVersionCreateRequest,
    ContractVersionResponse,
)
from app.service import CompatibilityService, ContractService, ContractVersionService

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.post("", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
def create_contract(
    payload: ContractCreateRequest,
    actor: Annotated[str, Depends(get_actor)],
    service: Annotated[ContractService, Depends(get_contract_service)],
) -> ContractResponse:
    _ = actor
    contract = service.create_contract(payload)
    return ContractResponse.model_validate(contract)


@router.get("", response_model=list[ContractListItem])
def list_contracts(
    namespace: str | None = Query(default=None),
    name: str | None = Query(default=None),
    owner: str | None = Query(default=None),
    status_filter: ContractStatus | None = Query(default=None, alias="status"),
    tag: str | None = Query(default=None),
    target_layer: TargetLayer | None = Query(default=None),
    service: ContractService = Depends(get_contract_service),
) -> list[ContractListItem]:
    rows = service.list_contracts(
        namespace=namespace,
        name=name,
        owner=owner,
        status=status_filter,
        tag=tag,
        target_layer=target_layer.value if target_layer else None,
    )
    return [ContractListItem.model_validate(item) for item in rows]


@router.get("/{contract_id}", response_model=ContractResponse)
def get_contract(
    contract_id: UUID,
    service: Annotated[ContractService, Depends(get_contract_service)],
) -> ContractResponse:
    contract = service.get_contract(contract_id)
    return ContractResponse.model_validate(contract)


@router.patch("/{contract_id}", response_model=ContractResponse)
def update_contract(
    contract_id: UUID,
    payload: ContractUpdateRequest,
    actor: Annotated[str, Depends(get_actor)],
    service: Annotated[ContractService, Depends(get_contract_service)],
) -> ContractResponse:
    _ = actor
    contract = service.update_contract(contract_id, payload)
    return ContractResponse.model_validate(contract)


@router.delete("/{contract_id}", response_model=ContractResponse)
def archive_contract(
    contract_id: UUID,
    actor: Annotated[str, Depends(get_actor)],
    service: Annotated[ContractService, Depends(get_contract_service)],
) -> ContractResponse:
    _ = actor
    contract = service.archive_contract(contract_id)
    return ContractResponse.model_validate(contract)


@router.post(
    "/{contract_id}/versions",
    response_model=ContractVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_version(
    contract_id: UUID,
    payload: ContractVersionCreateRequest,
    actor: Annotated[str, Depends(get_actor)],
    service: Annotated[ContractVersionService, Depends(get_version_service)],
) -> ContractVersionResponse:
    row = service.create_version(contract_id, payload, actor)
    return ContractVersionResponse.model_validate(row)


@router.get("/{contract_id}/versions", response_model=list[ContractVersionResponse])
def list_versions(
    contract_id: UUID,
    service: Annotated[ContractVersionService, Depends(get_version_service)],
) -> list[ContractVersionResponse]:
    rows = service.list_versions(contract_id)
    return [ContractVersionResponse.model_validate(item) for item in rows]


@router.get("/{contract_id}/versions/{version}", response_model=ContractVersionResponse)
def get_version(
    contract_id: UUID,
    version: str,
    service: Annotated[ContractVersionService, Depends(get_version_service)],
) -> ContractVersionResponse:
    row = service.get_version(contract_id, version)
    return ContractVersionResponse.model_validate(row)


@router.post("/{contract_id}/versions/{version}/promote", response_model=ContractVersionResponse)
def promote_version(
    contract_id: UUID,
    version: str,
    actor: Annotated[str, Depends(get_actor)],
    service: Annotated[ContractVersionService, Depends(get_version_service)],
) -> ContractVersionResponse:
    _ = actor
    row = service.promote_version(contract_id, version)
    return ContractVersionResponse.model_validate(row)


@router.post("/{contract_id}/versions/{version}/deprecate", response_model=ContractVersionResponse)
def deprecate_version(
    contract_id: UUID,
    version: str,
    actor: Annotated[str, Depends(get_actor)],
    service: Annotated[ContractVersionService, Depends(get_version_service)],
) -> ContractVersionResponse:
    _ = actor
    row = service.deprecate_version(contract_id, version)
    return ContractVersionResponse.model_validate(row)


@router.post(
    "/{contract_id}/versions/{new_version}/compatibility",
    response_model=CompatibilityCheckResponse,
)
def check_compatibility(
    contract_id: UUID,
    new_version: str,
    payload: CompatibilityCheckRequest,
    actor: Annotated[str, Depends(get_actor)],
    service: Annotated[CompatibilityService, Depends(get_compatibility_service)],
) -> CompatibilityCheckResponse:
    result = service.check(contract_id, new_version, payload, actor)
    return CompatibilityCheckResponse.model_validate(result)

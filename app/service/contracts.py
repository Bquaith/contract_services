from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.db.models import Contract
from app.schemas.contract import ContractCreateRequest, ContractUpdateRequest
from app.schemas.enums import ContractStatus


class ContractService:
    def __init__(self, session: Session):
        self.session = session

    def create_contract(self, payload: ContractCreateRequest) -> Contract:
        exists_stmt = select(Contract).where(
            Contract.namespace == payload.namespace,
            Contract.name == payload.name,
            Contract.deleted_at.is_(None),
        )
        if self.session.scalar(exists_stmt):
            raise ApiError(
                status_code=409,
                code="contract_already_exists",
                message="Contract with namespace/name already exists",
                details={"namespace": payload.namespace, "name": payload.name},
            )

        contract = Contract(
            namespace=payload.namespace,
            name=payload.name,
            entity_name=payload.entity_name,
            entity_type=payload.entity_type,
            description=payload.description,
            owners=payload.owners,
            tags=payload.tags,
            target_layer=payload.target_layer,
            status=ContractStatus.DRAFT,
        )

        try:
            self.session.add(contract)
            self.session.commit()
            self.session.refresh(contract)
        except IntegrityError as exc:
            self.session.rollback()
            raise ApiError(
                status_code=409,
                code="contract_already_exists",
                message="Contract with namespace/name already exists",
                details={"namespace": payload.namespace, "name": payload.name},
            ) from exc

        return contract

    def list_contracts(
        self,
        namespace: str | None = None,
        name: str | None = None,
        owner: str | None = None,
        status: ContractStatus | None = None,
        tag: str | None = None,
        target_layer: str | None = None,
    ) -> list[Contract]:
        stmt = select(Contract).where(Contract.deleted_at.is_(None))

        if namespace:
            stmt = stmt.where(Contract.namespace == namespace)
        if name:
            stmt = stmt.where(Contract.name == name)
        if owner:
            stmt = stmt.where(Contract.owners.contains([owner]))
        if status:
            stmt = stmt.where(Contract.status == status)
        if tag:
            stmt = stmt.where(Contract.tags.any(tag))
        if target_layer:
            stmt = stmt.where(Contract.target_layer == target_layer)

        stmt = stmt.order_by(Contract.created_at.desc())
        return list(self.session.scalars(stmt))

    def get_contract(self, contract_id: UUID) -> Contract:
        stmt = select(Contract).where(Contract.id == contract_id, Contract.deleted_at.is_(None))
        contract = self.session.scalar(stmt)
        if not contract:
            raise ApiError(
                status_code=404,
                code="contract_not_found",
                message="Contract not found",
                details={"contract_id": str(contract_id)},
            )
        return contract

    def get_by_namespace_name(self, namespace: str, name: str) -> Contract:
        stmt = select(Contract).where(
            Contract.namespace == namespace,
            Contract.name == name,
            Contract.deleted_at.is_(None),
        )
        contract = self.session.scalar(stmt)
        if not contract:
            raise ApiError(
                status_code=404,
                code="contract_not_found",
                message="Contract not found",
                details={"namespace": namespace, "name": name},
            )
        return contract

    def update_contract(self, contract_id: UUID, payload: ContractUpdateRequest) -> Contract:
        contract = self.get_contract(contract_id)
        updates = payload.model_dump(exclude_unset=True)

        if not updates:
            return contract

        if "description" in updates:
            contract.description = updates["description"]
        if "owners" in updates and updates["owners"] is not None:
            contract.owners = list(dict.fromkeys([item.strip() for item in updates["owners"] if item]))
        if "tags" in updates and updates["tags"] is not None:
            contract.tags = list(dict.fromkeys([item.strip() for item in updates["tags"] if item]))
        if "status" in updates and updates["status"] is not None:
            contract.status = updates["status"]
        if "target_layer" in updates and updates["target_layer"] is not None:
            contract.target_layer = updates["target_layer"]

        contract.updated_at = datetime.now(timezone.utc)
        self.session.commit()

        self.session.refresh(contract)
        return contract

    def archive_contract(self, contract_id: UUID) -> Contract:
        contract = self.get_contract(contract_id)

        contract.status = ContractStatus.ARCHIVED
        contract.deleted_at = datetime.now(timezone.utc)
        contract.updated_at = datetime.now(timezone.utc)
        self.session.commit()

        self.session.refresh(contract)
        return contract

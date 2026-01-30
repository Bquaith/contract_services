from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.db.models import Contract, ContractVersion
from app.schemas.contract import ContractSchema
from app.schemas.enums import ContractStatus, VersionStatus
from app.schemas.version import ContractVersionCreateRequest
from app.service.utils import calculate_checksum, ensure_semver
from app.validators import validate_contract_schema


class ContractVersionService:
    def __init__(self, session: Session):
        self.session = session

    def create_version(
        self,
        contract_id: UUID,
        payload: ContractVersionCreateRequest,
        actor: str,
    ) -> ContractVersion:
        ensure_semver(payload.version)
        contract = self._get_contract(contract_id)

        validation = validate_contract_schema(payload.schema)
        if validation.verdict.value == "fail":
            raise ApiError(
                status_code=422,
                code="schema_validation_failed",
                message="Contract schema validation failed",
                details={
                    "verdict": validation.verdict.value,
                    "violations": [item.model_dump(mode="json") for item in validation.violations],
                },
            )

        existing_stmt = select(ContractVersion).where(
            ContractVersion.contract_id == contract_id,
            ContractVersion.version == payload.version,
        )
        if self.session.scalar(existing_stmt):
            raise ApiError(
                status_code=409,
                code="version_already_exists",
                message="Contract version already exists",
                details={"contract_id": str(contract_id), "version": payload.version},
            )

        schema_json = payload.schema.model_dump(mode="json")
        version = ContractVersion(
            contract_id=contract.id,
            version=payload.version,
            status=VersionStatus.DRAFT,
            schema_json=schema_json,
            checksum=calculate_checksum(schema_json),
            compatibility_mode=payload.compatibility_mode,
            created_by=actor,
            is_locked=False,
        )

        self.session.add(version)
        self.session.commit()

        self.session.refresh(version)
        return version

    def list_versions(self, contract_id: UUID) -> list[ContractVersion]:
        self._get_contract(contract_id)
        stmt = (
            select(ContractVersion)
            .where(ContractVersion.contract_id == contract_id)
            .order_by(ContractVersion.created_at.desc())
        )
        return list(self.session.scalars(stmt))

    def get_version(self, contract_id: UUID, version: str) -> ContractVersion:
        self._get_contract(contract_id)
        stmt = select(ContractVersion).where(
            ContractVersion.contract_id == contract_id,
            ContractVersion.version == version,
        )
        version_row = self.session.scalar(stmt)
        if not version_row:
            raise ApiError(
                status_code=404,
                code="version_not_found",
                message="Contract version not found",
                details={"contract_id": str(contract_id), "version": version},
            )
        return version_row

    def get_version_by_namespace_name(
        self,
        namespace: str,
        name: str,
        version: str,
    ) -> tuple[Contract, ContractVersion]:
        contract = self._get_contract_by_namespace_name(namespace, name)
        version_row = self.get_version(contract.id, version)
        return contract, version_row

    def get_active_version_by_namespace_name(self, namespace: str, name: str) -> tuple[Contract, ContractVersion]:
        contract = self._get_contract_by_namespace_name(namespace, name)
        if not contract.active_version:
            raise ApiError(
                status_code=404,
                code="active_version_not_found",
                message="Active version is not set",
                details={"namespace": namespace, "name": name},
            )
        version_row = self.get_version(contract.id, contract.active_version)
        return contract, version_row

    def promote_version(self, contract_id: UUID, version: str) -> ContractVersion:
        contract = self._get_contract(contract_id)
        version_row = self.get_version(contract_id, version)

        version_row.status = VersionStatus.STABLE
        version_row.is_locked = True
        contract.active_version = version_row.version
        contract.status = ContractStatus.ACTIVE
        self.session.commit()

        self.session.refresh(version_row)
        return version_row

    def deprecate_version(self, contract_id: UUID, version: str) -> ContractVersion:
        contract = self._get_contract(contract_id)
        version_row = self.get_version(contract_id, version)

        version_row.status = VersionStatus.DEPRECATED
        version_row.is_locked = True
        if contract.active_version == version_row.version:
            contract.active_version = None
        self.session.commit()

        self.session.refresh(version_row)
        return version_row

    def parse_schema(self, version_row: ContractVersion) -> ContractSchema:
        return ContractSchema.model_validate(version_row.schema_json)

    def _get_contract(self, contract_id: UUID) -> Contract:
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

    def _get_contract_by_namespace_name(self, namespace: str, name: str) -> Contract:
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

from __future__ import annotations

from functools import cmp_to_key
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.compatibility import (
    build_compatibility_report,
    build_schema_diff,
    policy_passed_for_bump,
    required_mode_for_bump,
    verdict_for_mode,
)
from app.db.models import CompatibilityCheck, Contract, ContractVersion
from app.schemas.contract import JsonSchemaDocument
from app.schemas.enums import ContractStatus, VersionStatus
from app.schemas.version import ContractVersionCreateRequest
from app.service.utils import (
    calculate_checksum,
    compare_semver,
    detect_version_bump,
    ensure_semver,
)
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

        validation = validate_contract_schema(payload.schema_document)
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

        latest_existing = self._get_latest_version_row(contract_id)
        if latest_existing and compare_semver(payload.version, latest_existing.version) <= 0:
            raise ApiError(
                status_code=409,
                code="invalid_version_order",
                message="Version must be greater than the latest existing version",
                details={
                    "contract_id": str(contract_id),
                    "latest_version": latest_existing.version,
                    "candidate_version": payload.version,
                },
            )

        schema_json = payload.schema_document
        compatibility_row: CompatibilityCheck | None = None
        if latest_existing is not None:
            compatibility_row = self._build_compatibility_check(
                contract_id=contract_id,
                base_version_row=latest_existing,
                candidate_version=payload.version,
                candidate_schema=schema_json,
                actor=actor,
            )
            if compatibility_row.policy_passed is False:
                self.session.add(compatibility_row)
                self.session.commit()
                raise ApiError(
                    status_code=409,
                    code="version_policy_violation",
                    message="Version bump is incompatible with schema changes",
                    details={
                        "base_version": latest_existing.version,
                        "candidate_version": payload.version,
                        "version_bump": (
                            compatibility_row.version_bump.value
                            if compatibility_row.version_bump is not None
                            else None
                        ),
                        "policy_mode": compatibility_row.mode.value,
                        "report": {
                            "backward_compatible": compatibility_row.backward_compatible,
                            "forward_compatible": compatibility_row.forward_compatible,
                            "full_compatible": compatibility_row.full_compatible,
                            "violations": compatibility_row.violations_json,
                            "diff": compatibility_row.diff_json,
                        },
                    },
                )

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
        if compatibility_row is not None:
            self.session.add(compatibility_row)
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

    def get_active_version_by_namespace_name(
        self,
        namespace: str,
        name: str,
    ) -> tuple[Contract, ContractVersion]:
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

    def parse_schema(self, version_row: ContractVersion) -> JsonSchemaDocument:
        return dict(version_row.schema_json)

    def get_previous_version(self, contract_id: UUID, version: str) -> ContractVersion | None:
        rows = self.list_versions(contract_id)
        lower_versions = [row for row in rows if compare_semver(row.version, version) < 0]
        if not lower_versions:
            return None
        return max(lower_versions, key=cmp_to_key(self._compare_version_rows))

    def _get_latest_version_row(self, contract_id: UUID) -> ContractVersion | None:
        stmt = select(ContractVersion).where(ContractVersion.contract_id == contract_id)
        rows = list(self.session.scalars(stmt))
        if not rows:
            return None
        return max(rows, key=cmp_to_key(self._compare_version_rows))

    def _build_compatibility_check(
        self,
        *,
        contract_id: UUID,
        base_version_row: ContractVersion,
        candidate_version: str,
        candidate_schema: JsonSchemaDocument,
        actor: str,
    ) -> CompatibilityCheck:
        version_bump = detect_version_bump(base_version_row.version, candidate_version)
        report = build_compatibility_report(self.parse_schema(base_version_row), candidate_schema)
        mode = required_mode_for_bump(version_bump)
        verdict = verdict_for_mode(report, mode)
        policy_passed = policy_passed_for_bump(report, version_bump)
        diff = build_schema_diff(self.parse_schema(base_version_row), candidate_schema)

        return CompatibilityCheck(
            contract_id=contract_id,
            base_version=base_version_row.version,
            candidate_version=candidate_version,
            mode=mode,
            verdict=verdict,
            version_bump=version_bump,
            backward_compatible=report["backward_compatible"],
            forward_compatible=report["forward_compatible"],
            full_compatible=report["full_compatible"],
            policy_passed=policy_passed,
            violations_json=report["violations"],
            diff_json=diff,
            created_by=actor,
        )

    @staticmethod
    def _compare_version_rows(left: ContractVersion, right: ContractVersion) -> int:
        return compare_semver(left.version, right.version)

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

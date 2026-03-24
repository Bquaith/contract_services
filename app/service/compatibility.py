from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.compatibility import (
    build_compatibility_report,
    build_schema_diff,
    policy_passed_for_bump,
    verdict_for_mode,
)
from app.db.models import CompatibilityCheck
from app.schemas.version import CompatibilityCheckRequest
from app.service.utils import compare_semver, detect_version_bump
from app.service.versions import ContractVersionService


class CompatibilityService:
    def __init__(self, session: Session):
        self.session = session
        self.version_service = ContractVersionService(session)

    def check(
        self,
        contract_id: UUID,
        new_version: str,
        payload: CompatibilityCheckRequest,
        actor: str,
    ) -> dict:
        contract = self.version_service._get_contract(contract_id)
        candidate = self.version_service.get_version(contract_id, new_version)
        previous_version = self.version_service.get_previous_version(contract_id, new_version)

        base_version = (
            payload.base_version
            or contract.active_version
            or (previous_version.version if previous_version is not None else None)
        )
        if not base_version:
            raise ApiError(
                status_code=400,
                code="base_version_required",
                message="Base version is required because no reference version could be inferred",
                details={"contract_id": str(contract_id)},
            )

        base = self.version_service.get_version(contract_id, base_version)
        mode = payload.mode or candidate.compatibility_mode

        base_schema = self.version_service.parse_schema(base)
        candidate_schema = self.version_service.parse_schema(candidate)

        report = build_compatibility_report(base_schema, candidate_schema)
        diff = build_schema_diff(base_schema, candidate_schema)
        verdict = verdict_for_mode(report, mode)

        version_bump = None
        policy_passed = None
        if compare_semver(new_version, base_version) > 0:
            version_bump = detect_version_bump(base_version, new_version)
            policy_passed = policy_passed_for_bump(report, version_bump)

        check_row = CompatibilityCheck(
            contract_id=contract_id,
            base_version=base_version,
            candidate_version=new_version,
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

        self.session.add(check_row)
        self.session.commit()

        return {
            "contract_id": contract_id,
            "base_version": base_version,
            "candidate_version": new_version,
            "mode": mode,
            "verdict": verdict,
            "version_bump": version_bump,
            "backward_compatible": report["backward_compatible"],
            "forward_compatible": report["forward_compatible"],
            "full_compatible": report["full_compatible"],
            "policy_passed": policy_passed,
            "violations": report["violations"],
            "diff": diff,
        }

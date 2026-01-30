from uuid import UUID

from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.compatibility import build_schema_diff, evaluate_compatibility
from app.db.models import CompatibilityCheck
from app.schemas.version import CompatibilityCheckRequest
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

        base_version = payload.base_version or contract.active_version
        if not base_version:
            raise ApiError(
                status_code=400,
                code="base_version_required",
                message="Base version is required because contract has no active version",
                details={"contract_id": str(contract_id)},
            )

        base = self.version_service.get_version(contract_id, base_version)
        mode = payload.mode or candidate.compatibility_mode

        base_schema = self.version_service.parse_schema(base)
        candidate_schema = self.version_service.parse_schema(candidate)

        diff = build_schema_diff(base_schema, candidate_schema)
        verdict, violations = evaluate_compatibility(base_schema, candidate_schema, mode)

        check_row = CompatibilityCheck(
            contract_id=contract_id,
            base_version=base_version,
            candidate_version=new_version,
            mode=mode,
            verdict=verdict,
            violations_json=violations,
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
            "violations": violations,
            "diff": diff,
        }

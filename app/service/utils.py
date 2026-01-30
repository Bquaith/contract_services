import hashlib
import json
import re
from typing import Any

from app.api.errors import ApiError

SEMVER_PATTERN = re.compile(
    r"^(0|[1-9]\\d*)\\.(0|[1-9]\\d*)\\.(0|[1-9]\\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\\.[0-9A-Za-z-]+)*)?"
    r"(?:\\+[0-9A-Za-z-]+(?:\\.[0-9A-Za-z-]+)*)?$"
)


def ensure_semver(version: str) -> None:
    if not SEMVER_PATTERN.fullmatch(version):
        raise ApiError(
            status_code=422,
            code="invalid_semver",
            message="Version must match SemVer format, e.g. 1.0.0",
            details={"version": version},
        )


def calculate_checksum(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

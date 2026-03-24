from __future__ import annotations

import hashlib
import json
import re
from functools import cmp_to_key
from dataclasses import dataclass
from typing import Any, Iterable

from app.api.errors import ApiError
from app.schemas.enums import VersionBumpType

SEMVER_PATTERN = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


@dataclass(frozen=True)
class SemVer:
    major: int
    minor: int
    patch: int
    prerelease: tuple[str, ...] = ()
    build: str | None = None


def ensure_semver(version: str) -> None:
    if not SEMVER_PATTERN.fullmatch(version):
        raise ApiError(
            status_code=422,
            code="invalid_semver",
            message="Version must match SemVer format, e.g. 1.0.0",
            details={"version": version},
        )


def parse_semver(version: str) -> SemVer:
    ensure_semver(version)
    match = SEMVER_PATTERN.fullmatch(version)
    if match is None:
        raise AssertionError("SemVer validation must return a match")

    prerelease = match.group("prerelease")
    return SemVer(
        major=int(match.group("major")),
        minor=int(match.group("minor")),
        patch=int(match.group("patch")),
        prerelease=tuple(prerelease.split(".")) if prerelease else (),
        build=match.group("build"),
    )


def _compare_prerelease_identifier(left: str, right: str) -> int:
    left_is_digit = left.isdigit()
    right_is_digit = right.isdigit()

    if left_is_digit and right_is_digit:
        return (int(left) > int(right)) - (int(left) < int(right))
    if left_is_digit and not right_is_digit:
        return -1
    if not left_is_digit and right_is_digit:
        return 1
    return (left > right) - (left < right)


def compare_semver(left: str, right: str) -> int:
    left_version = parse_semver(left)
    right_version = parse_semver(right)

    core_left = (left_version.major, left_version.minor, left_version.patch)
    core_right = (right_version.major, right_version.minor, right_version.patch)
    if core_left != core_right:
        return (core_left > core_right) - (core_left < core_right)

    if not left_version.prerelease and not right_version.prerelease:
        return 0
    if not left_version.prerelease:
        return 1
    if not right_version.prerelease:
        return -1

    for left_identifier, right_identifier in zip(left_version.prerelease, right_version.prerelease):
        identifier_comparison = _compare_prerelease_identifier(left_identifier, right_identifier)
        if identifier_comparison != 0:
            return identifier_comparison

    return (len(left_version.prerelease) > len(right_version.prerelease)) - (
        len(left_version.prerelease) < len(right_version.prerelease)
    )


def detect_version_bump(base_version: str, candidate_version: str) -> VersionBumpType:
    base = parse_semver(base_version)
    candidate = parse_semver(candidate_version)

    if compare_semver(candidate_version, base_version) <= 0:
        raise ApiError(
            status_code=409,
            code="invalid_version_order",
            message="Version must be greater than the previous version",
            details={"base_version": base_version, "candidate_version": candidate_version},
        )

    if candidate.major != base.major:
        return VersionBumpType.MAJOR
    if candidate.minor != base.minor:
        return VersionBumpType.MINOR
    if candidate.patch != base.patch:
        return VersionBumpType.PATCH

    raise ApiError(
        status_code=409,
        code="unsupported_version_bump",
        message="Only MAJOR, MINOR or PATCH bumps are supported",
        details={"base_version": base_version, "candidate_version": candidate_version},
    )


def max_semver(versions: Iterable[str]) -> str | None:
    parsed_versions = list(versions)
    if not parsed_versions:
        return None
    return max(parsed_versions, key=cmp_to_key(compare_semver))


def calculate_checksum(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

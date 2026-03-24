from enum import Enum


class EntityType(str, Enum):
    TABLE = "table"
    TOPIC = "topic"


class TargetLayer(str, Enum):
    RAW = "raw"
    CURATED = "curated"
    AUDIT = "audit"


class ContractStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class VersionStatus(str, Enum):
    DRAFT = "draft"
    STABLE = "stable"
    DEPRECATED = "deprecated"


class CompatibilityMode(str, Enum):
    BACKWARD = "backward"
    FORWARD = "forward"
    FULL = "full"
    NONE = "none"


class CompatibilityDirection(str, Enum):
    BACKWARD = "backward"
    FORWARD = "forward"


class CompatibilityVerdict(str, Enum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


class FieldType(str, Enum):
    STRING = "string"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    DATE = "date"
    TIMESTAMP = "timestamp"
    DECIMAL = "decimal"
    JSON = "json"


class ValidationTarget(str, Enum):
    SCHEMA = "schema"
    COMPATIBILITY = "compatibility"


class ValidationVerdict(str, Enum):
    OK = "ok"
    FAIL = "fail"


class VersionBumpType(str, Enum):
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"

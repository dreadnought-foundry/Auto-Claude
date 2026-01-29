"""Sprint type definitions and coverage thresholds.

This module defines the 6 sprint types supported by Maestro-integrated specs
and their corresponding coverage requirements.

Sprint Types:
    - fullstack: Full-stack features (75% coverage)
    - backend: Backend services (85% coverage)
    - frontend: Frontend UI (70% coverage)
    - research: Research/investigation (30% coverage)
    - spike: Quick experiments (0% coverage)
    - infrastructure: DevOps/infra (60% coverage)
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class SprintType(str, Enum):
    """Valid sprint types with type-specific quality requirements."""

    FULLSTACK = "fullstack"
    BACKEND = "backend"
    FRONTEND = "frontend"
    RESEARCH = "research"
    SPIKE = "spike"
    INFRASTRUCTURE = "infrastructure"


@dataclass(frozen=True)
class TypeRequirements:
    """Quality requirements for a sprint type."""

    coverage_threshold: int
    integration_tests_required: bool = False
    documentation_required: bool = False
    smoke_tests_required: bool = False
    visual_regression_required: bool = False


# Coverage thresholds by sprint type
COVERAGE_THRESHOLDS: dict[SprintType, int] = {
    SprintType.FULLSTACK: 75,
    SprintType.BACKEND: 85,
    SprintType.FRONTEND: 70,
    SprintType.RESEARCH: 30,
    SprintType.SPIKE: 0,
    SprintType.INFRASTRUCTURE: 60,
}

# Full requirements by type (for future quality gate integration)
TYPE_REQUIREMENTS: dict[SprintType, TypeRequirements] = {
    SprintType.FULLSTACK: TypeRequirements(coverage_threshold=75),
    SprintType.BACKEND: TypeRequirements(
        coverage_threshold=85, integration_tests_required=True
    ),
    SprintType.FRONTEND: TypeRequirements(
        coverage_threshold=70, visual_regression_required=True
    ),
    SprintType.RESEARCH: TypeRequirements(
        coverage_threshold=30, documentation_required=True
    ),
    SprintType.SPIKE: TypeRequirements(coverage_threshold=0, documentation_required=True),
    SprintType.INFRASTRUCTURE: TypeRequirements(
        coverage_threshold=60, smoke_tests_required=True
    ),
}

# Default type when not specified
DEFAULT_TYPE = SprintType.FULLSTACK

# Valid type values as strings (for validation)
VALID_TYPES = [t.value for t in SprintType]


def get_coverage_threshold(
    sprint_type: Optional[str] = None, override: Optional[int] = None
) -> int:
    """Get the coverage threshold for a sprint type.

    Args:
        sprint_type: The sprint type string (e.g., "backend"). Defaults to "fullstack".
        override: Optional override threshold from spec.

    Returns:
        The coverage threshold percentage (0-100).

    Examples:
        >>> get_coverage_threshold("backend")
        85
        >>> get_coverage_threshold(None)
        75
        >>> get_coverage_threshold("backend", override=50)
        50
    """
    if override is not None:
        return max(0, min(100, override))

    try:
        parsed_type = SprintType(sprint_type) if sprint_type else DEFAULT_TYPE
    except ValueError:
        parsed_type = DEFAULT_TYPE

    return COVERAGE_THRESHOLDS[parsed_type]


def get_type_requirements(sprint_type: Optional[str] = None) -> TypeRequirements:
    """Get the full requirements for a sprint type.

    Args:
        sprint_type: The sprint type string. Defaults to "fullstack".

    Returns:
        TypeRequirements dataclass with all quality requirements.
    """
    try:
        parsed_type = SprintType(sprint_type) if sprint_type else DEFAULT_TYPE
    except ValueError:
        parsed_type = DEFAULT_TYPE

    return TYPE_REQUIREMENTS[parsed_type]


def validate_sprint_type(sprint_type: str) -> tuple[bool, str]:
    """Validate a sprint type value.

    Args:
        sprint_type: The type string to validate.

    Returns:
        Tuple of (is_valid, error_message). Error message is empty if valid.

    Examples:
        >>> validate_sprint_type("backend")
        (True, '')
        >>> validate_sprint_type("invalid")
        (False, "Invalid sprint type 'invalid'. Must be one of: fullstack, backend, frontend, research, spike, infrastructure")
    """
    if sprint_type in VALID_TYPES:
        return True, ""

    return (
        False,
        f"Invalid sprint type '{sprint_type}'. Must be one of: {', '.join(VALID_TYPES)}",
    )


def validate_coverage_override(override: dict) -> tuple[bool, list[str]]:
    """Validate a coverage override object.

    Args:
        override: Dict with 'threshold' and 'justification' keys.

    Returns:
        Tuple of (is_valid, list of error messages).

    Examples:
        >>> validate_coverage_override({"threshold": 80, "justification": "External API"})
        (True, [])
        >>> validate_coverage_override({"threshold": 80})
        (False, ["'coverage_override.justification' is required"])
    """
    errors = []

    if not isinstance(override, dict):
        return False, ["'coverage_override' must be an object with 'threshold' and 'justification'"]

    threshold = override.get("threshold")
    justification = override.get("justification")

    if threshold is None:
        errors.append("'coverage_override.threshold' is required when coverage_override is present")
    elif not isinstance(threshold, (int, float)):
        errors.append("'coverage_override.threshold' must be a number")
    elif not (0 <= threshold <= 100):
        errors.append("'coverage_override.threshold' must be between 0 and 100")

    if not justification:
        errors.append("'coverage_override.justification' is required when overriding coverage")
    elif not isinstance(justification, str):
        errors.append("'coverage_override.justification' must be a string")
    elif len(justification.strip()) < 10:
        errors.append("'coverage_override.justification' must be at least 10 characters")

    return len(errors) == 0, errors

"""Tests for sprint type definitions and coverage thresholds.

Tests the apps/backend/spec/types.py module which provides:
- Sprint type enum definitions
- Coverage threshold lookups
- Type validation functions
"""

import pytest
import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "backend"))

from spec.types import (
    SprintType,
    TypeRequirements,
    COVERAGE_THRESHOLDS,
    TYPE_REQUIREMENTS,
    VALID_TYPES,
    DEFAULT_TYPE,
    get_coverage_threshold,
    get_type_requirements,
    validate_sprint_type,
    validate_coverage_override,
)


class TestSprintTypeEnum:
    """Tests for SprintType enum."""

    def test_all_six_types_defined(self):
        """Verify all 6 sprint types are defined."""
        assert len(SprintType) == 6
        expected = {"fullstack", "backend", "frontend", "research", "spike", "infrastructure"}
        actual = {t.value for t in SprintType}
        assert actual == expected

    def test_enum_values_are_strings(self):
        """Sprint types should be string enums for JSON compatibility."""
        for sprint_type in SprintType:
            assert isinstance(sprint_type.value, str)

    def test_enum_is_string_subclass(self):
        """SprintType should be usable as a string."""
        assert SprintType.BACKEND == "backend"
        assert SprintType.BACKEND.value == "backend"


class TestCoverageThresholds:
    """Tests for coverage threshold constants and lookup."""

    @pytest.mark.parametrize(
        "sprint_type,expected",
        [
            ("fullstack", 75),
            ("backend", 85),
            ("frontend", 70),
            ("research", 30),
            ("spike", 0),
            ("infrastructure", 60),
        ],
    )
    def test_threshold_values(self, sprint_type, expected):
        """Each sprint type should have the correct coverage threshold."""
        assert get_coverage_threshold(sprint_type) == expected

    def test_default_is_fullstack(self):
        """Missing type should default to fullstack (75%)."""
        assert get_coverage_threshold(None) == 75
        assert get_coverage_threshold("") == 75

    def test_invalid_type_defaults_to_fullstack(self):
        """Invalid type should default to fullstack with no error."""
        assert get_coverage_threshold("invalid_type") == 75
        assert get_coverage_threshold("BACKEND") == 75  # Case sensitive

    def test_override_takes_precedence(self):
        """Coverage override should take precedence over type threshold."""
        assert get_coverage_threshold("backend", override=50) == 50
        assert get_coverage_threshold("spike", override=80) == 80

    def test_override_clamped_to_valid_range(self):
        """Override should be clamped to 0-100."""
        assert get_coverage_threshold("backend", override=-10) == 0
        assert get_coverage_threshold("backend", override=150) == 100

    def test_coverage_thresholds_dict_complete(self):
        """COVERAGE_THRESHOLDS should have entry for every SprintType."""
        for sprint_type in SprintType:
            assert sprint_type in COVERAGE_THRESHOLDS


class TestTypeRequirements:
    """Tests for TypeRequirements dataclass and lookup."""

    def test_type_requirements_dict_complete(self):
        """TYPE_REQUIREMENTS should have entry for every SprintType."""
        for sprint_type in SprintType:
            assert sprint_type in TYPE_REQUIREMENTS

    def test_backend_requires_integration_tests(self):
        """Backend type should require integration tests."""
        reqs = get_type_requirements("backend")
        assert reqs.integration_tests_required is True

    def test_frontend_requires_visual_regression(self):
        """Frontend type should require visual regression tests."""
        reqs = get_type_requirements("frontend")
        assert reqs.visual_regression_required is True

    def test_research_requires_documentation(self):
        """Research type should require documentation."""
        reqs = get_type_requirements("research")
        assert reqs.documentation_required is True

    def test_spike_requires_documentation(self):
        """Spike type should require documentation."""
        reqs = get_type_requirements("spike")
        assert reqs.documentation_required is True

    def test_infrastructure_requires_smoke_tests(self):
        """Infrastructure type should require smoke tests."""
        reqs = get_type_requirements("infrastructure")
        assert reqs.smoke_tests_required is True

    def test_requirements_immutable(self):
        """TypeRequirements should be immutable (frozen dataclass)."""
        reqs = get_type_requirements("backend")
        with pytest.raises(Exception):  # FrozenInstanceError
            reqs.coverage_threshold = 50

    def test_invalid_type_returns_fullstack_requirements(self):
        """Invalid type should return fullstack requirements."""
        reqs = get_type_requirements("invalid")
        assert reqs.coverage_threshold == 75


class TestValidateSprintType:
    """Tests for sprint type validation."""

    @pytest.mark.parametrize(
        "valid_type",
        ["fullstack", "backend", "frontend", "research", "spike", "infrastructure"],
    )
    def test_valid_types_pass(self, valid_type):
        """All valid sprint types should pass validation."""
        is_valid, error = validate_sprint_type(valid_type)
        assert is_valid is True
        assert error == ""

    def test_invalid_type_fails(self):
        """Invalid sprint type should fail with helpful error."""
        is_valid, error = validate_sprint_type("invalid")
        assert is_valid is False
        assert "Invalid sprint type" in error
        assert "fullstack" in error  # Error should list valid types

    def test_case_sensitive(self):
        """Sprint types should be case-sensitive."""
        is_valid, _ = validate_sprint_type("Backend")
        assert is_valid is False

        is_valid, _ = validate_sprint_type("FULLSTACK")
        assert is_valid is False

    def test_empty_string_fails(self):
        """Empty string should fail validation."""
        is_valid, error = validate_sprint_type("")
        assert is_valid is False


class TestValidateCoverageOverride:
    """Tests for coverage override validation."""

    def test_valid_override_passes(self):
        """Valid coverage override should pass."""
        override = {
            "threshold": 80,
            "justification": "External API integration with limited local testability",
        }
        is_valid, errors = validate_coverage_override(override)
        assert is_valid is True
        assert errors == []

    def test_missing_threshold_fails(self):
        """Missing threshold should fail."""
        override = {"justification": "Some valid justification here"}
        is_valid, errors = validate_coverage_override(override)
        assert is_valid is False
        assert any("threshold" in e for e in errors)

    def test_missing_justification_fails(self):
        """Missing justification should fail."""
        override = {"threshold": 80}
        is_valid, errors = validate_coverage_override(override)
        assert is_valid is False
        assert any("justification" in e for e in errors)

    def test_threshold_out_of_range_fails(self):
        """Threshold outside 0-100 should fail."""
        override = {"threshold": 150, "justification": "Valid justification here"}
        is_valid, errors = validate_coverage_override(override)
        assert is_valid is False
        assert any("between 0 and 100" in e for e in errors)

    def test_negative_threshold_fails(self):
        """Negative threshold should fail."""
        override = {"threshold": -10, "justification": "Valid justification here"}
        is_valid, errors = validate_coverage_override(override)
        assert is_valid is False

    def test_short_justification_fails(self):
        """Very short justification should fail."""
        override = {"threshold": 80, "justification": "short"}
        is_valid, errors = validate_coverage_override(override)
        assert is_valid is False
        assert any("at least 10 characters" in e for e in errors)

    def test_non_dict_fails(self):
        """Non-dict override should fail."""
        is_valid, errors = validate_coverage_override("not a dict")
        assert is_valid is False

    def test_non_numeric_threshold_fails(self):
        """Non-numeric threshold should fail."""
        override = {"threshold": "high", "justification": "Valid justification here"}
        is_valid, errors = validate_coverage_override(override)
        assert is_valid is False
        assert any("must be a number" in e for e in errors)

    def test_boundary_thresholds_pass(self):
        """Boundary values (0 and 100) should pass."""
        override_zero = {"threshold": 0, "justification": "Spike work, no coverage needed"}
        is_valid, errors = validate_coverage_override(override_zero)
        assert is_valid is True

        override_hundred = {
            "threshold": 100,
            "justification": "Critical security code needs full coverage",
        }
        is_valid, errors = validate_coverage_override(override_hundred)
        assert is_valid is True


class TestValidTypesConstant:
    """Tests for VALID_TYPES constant."""

    def test_valid_types_matches_enum(self):
        """VALID_TYPES should contain all enum values."""
        assert set(VALID_TYPES) == {t.value for t in SprintType}

    def test_valid_types_is_list_of_strings(self):
        """VALID_TYPES should be a list of strings."""
        assert isinstance(VALID_TYPES, list)
        assert all(isinstance(t, str) for t in VALID_TYPES)


class TestDefaultType:
    """Tests for DEFAULT_TYPE constant."""

    def test_default_is_fullstack(self):
        """Default type should be fullstack."""
        assert DEFAULT_TYPE == SprintType.FULLSTACK
        assert DEFAULT_TYPE.value == "fullstack"

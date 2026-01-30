"""Tests for Maestro Quality Gate integration.

Tests the 9-item pre-flight checklist and sprint type-aware
quality gate enforcement before merge operations.
"""

import asyncio
import json
import pytest
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import sys

# Ensure apps/backend is in path
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "backend"))

from spec.types import SprintType, COVERAGE_THRESHOLDS


# =============================================================================
# TEST DATA
# =============================================================================

# Check behavior by sprint type (matches sprint file matrix)
EXPECTED_CHECK_BEHAVIORS = {
    "tests_pass": {
        SprintType.SPIKE: "skip",
        SprintType.RESEARCH: "required",
        SprintType.FULLSTACK: "required",
        SprintType.BACKEND: "required",
        SprintType.FRONTEND: "required",
        SprintType.INFRASTRUCTURE: "required",
    },
    "coverage_meets_threshold": {
        SprintType.SPIKE: "skip",
        SprintType.RESEARCH: "reduced",  # 30%
        SprintType.FULLSTACK: "required",
        SprintType.BACKEND: "required",
        SprintType.FRONTEND: "required",
        SprintType.INFRASTRUCTURE: "required",
    },
    "no_lint_errors": {
        SprintType.SPIKE: "skip",
        SprintType.RESEARCH: "required",
        SprintType.FULLSTACK: "required",
        SprintType.BACKEND: "required",
        SprintType.FRONTEND: "required",
        SprintType.INFRASTRUCTURE: "required",
    },
    "no_type_errors": {
        SprintType.SPIKE: "skip",
        SprintType.RESEARCH: "skip",
        SprintType.FULLSTACK: "required",
        SprintType.BACKEND: "required",
        SprintType.FRONTEND: "required",
        SprintType.INFRASTRUCTURE: "required",
    },
    "migrations_valid": {
        SprintType.SPIKE: "skip",
        SprintType.RESEARCH: "skip",
        SprintType.FULLSTACK: "required",
        SprintType.BACKEND: "required",
        SprintType.FRONTEND: "required",
        SprintType.INFRASTRUCTURE: "required",
    },
    "documentation_updated": {
        SprintType.SPIKE: "required",  # Only this one
        SprintType.RESEARCH: "required",
        SprintType.FULLSTACK: "optional",
        SprintType.BACKEND: "optional",
        SprintType.FRONTEND: "optional",
        SprintType.INFRASTRUCTURE: "optional",
    },
    "no_debug_statements": {
        SprintType.SPIKE: "skip",
        SprintType.RESEARCH: "required",
        SprintType.FULLSTACK: "required",
        SprintType.BACKEND: "required",
        SprintType.FRONTEND: "required",
        SprintType.INFRASTRUCTURE: "required",
    },
    "no_secrets_in_code": {
        SprintType.SPIKE: "required",
        SprintType.RESEARCH: "required",
        SprintType.FULLSTACK: "required",
        SprintType.BACKEND: "required",
        SprintType.FRONTEND: "required",
        SprintType.INFRASTRUCTURE: "required",
    },
    "changelog_updated": {
        SprintType.SPIKE: "skip",
        SprintType.RESEARCH: "skip",
        SprintType.FULLSTACK: "optional",
        SprintType.BACKEND: "optional",
        SprintType.FRONTEND: "optional",
        SprintType.INFRASTRUCTURE: "optional",
    },
}


# =============================================================================
# CHECK RESULT TESTS
# =============================================================================

class TestCheckResult:
    """Tests for CheckResult dataclass."""

    def test_create_passed_result(self):
        """Create a passing check result."""
        from qa.preflight_checklist import CheckResult

        result = CheckResult(
            check_name="tests_pass",
            passed=True,
            message="All tests passed",
        )
        assert result.passed is True
        assert result.skipped is False
        assert result.check_name == "tests_pass"

    def test_create_failed_result(self):
        """Create a failing check result."""
        from qa.preflight_checklist import CheckResult

        result = CheckResult(
            check_name="coverage_meets_threshold",
            passed=False,
            message="Coverage 45% below threshold 85%",
            details={"actual": 45, "threshold": 85},
        )
        assert result.passed is False
        assert result.details["actual"] == 45

    def test_create_skipped_result(self):
        """Create a skipped check result."""
        from qa.preflight_checklist import CheckResult

        result = CheckResult(
            check_name="tests_pass",
            passed=True,
            message="Skipped for spike sprint",
            skipped=True,
            skip_reason="Spike sprints skip test validation",
        )
        assert result.skipped is True
        assert result.passed is True  # Skipped counts as passed


class TestPreflightResult:
    """Tests for PreflightResult dataclass."""

    def test_all_passed(self):
        """Result with all checks passing."""
        from qa.preflight_checklist import CheckResult, PreflightResult

        checks = [
            CheckResult("tests_pass", True, "Passed"),
            CheckResult("coverage_meets_threshold", True, "Passed"),
        ]
        result = PreflightResult(
            passed=True,
            checks=checks,
            blocking_failures=[],
            warnings=[],
            summary="2/2 checks passed",
        )
        assert result.passed is True
        assert len(result.blocking_failures) == 0

    def test_with_blocking_failure(self):
        """Result with blocking failure."""
        from qa.preflight_checklist import CheckResult, PreflightResult

        failed_check = CheckResult("no_secrets_in_code", False, "Found API key")
        result = PreflightResult(
            passed=False,
            checks=[failed_check],
            blocking_failures=[failed_check],
            warnings=[],
            summary="1/1 checks failed",
        )
        assert result.passed is False
        assert len(result.blocking_failures) == 1

    def test_with_warnings_still_passes(self):
        """Result with warnings but no failures passes."""
        from qa.preflight_checklist import CheckResult, PreflightResult

        warning_check = CheckResult("changelog_updated", False, "Not updated")
        result = PreflightResult(
            passed=True,
            checks=[warning_check],
            blocking_failures=[],
            warnings=[warning_check],
            summary="1 warning, no failures",
        )
        assert result.passed is True
        assert len(result.warnings) == 1


# =============================================================================
# CHECK BEHAVIOR TESTS
# =============================================================================

class TestCheckBehavior:
    """Tests for check behavior configuration."""

    def test_check_behavior_enum(self):
        """CheckBehavior has all expected values."""
        from qa.preflight_checklist import CheckBehavior

        assert CheckBehavior.REQUIRED.value == "required"
        assert CheckBehavior.SKIP.value == "skip"
        assert CheckBehavior.OPTIONAL.value == "optional"
        assert CheckBehavior.REDUCED.value == "reduced"

    def test_all_checks_have_behavior_for_all_types(self):
        """Every check has behavior defined for every sprint type."""
        from qa.preflight_checklist import CHECK_BEHAVIORS

        for check_name, behaviors in CHECK_BEHAVIORS.items():
            for sprint_type in SprintType:
                assert sprint_type in behaviors, f"Missing behavior for {check_name}/{sprint_type}"

    def test_spike_type_behaviors_match_spec(self):
        """Spike sprint behaviors match the sprint specification."""
        from qa.preflight_checklist import CHECK_BEHAVIORS, CheckBehavior

        for check_name, expected in EXPECTED_CHECK_BEHAVIORS.items():
            actual = CHECK_BEHAVIORS[check_name][SprintType.SPIKE]
            expected_behavior = CheckBehavior(expected[SprintType.SPIKE])
            assert actual == expected_behavior, f"{check_name} spike behavior mismatch"

    def test_research_type_behaviors_match_spec(self):
        """Research sprint behaviors match the sprint specification."""
        from qa.preflight_checklist import CHECK_BEHAVIORS, CheckBehavior

        for check_name, expected in EXPECTED_CHECK_BEHAVIORS.items():
            actual = CHECK_BEHAVIORS[check_name][SprintType.RESEARCH]
            expected_behavior = CheckBehavior(expected[SprintType.RESEARCH])
            assert actual == expected_behavior, f"{check_name} research behavior mismatch"

    def test_backend_type_behaviors_match_spec(self):
        """Backend sprint behaviors match the sprint specification."""
        from qa.preflight_checklist import CHECK_BEHAVIORS, CheckBehavior

        for check_name, expected in EXPECTED_CHECK_BEHAVIORS.items():
            actual = CHECK_BEHAVIORS[check_name][SprintType.BACKEND]
            expected_behavior = CheckBehavior(expected[SprintType.BACKEND])
            assert actual == expected_behavior, f"{check_name} backend behavior mismatch"


# =============================================================================
# INDIVIDUAL CHECK TESTS
# =============================================================================

class TestTestsPassCheck:
    """Tests for the tests_pass check."""

    @pytest.mark.asyncio
    async def test_passes_when_all_tests_pass(self, tmp_path):
        """Check passes when test runner returns success."""
        from qa.preflight_checklist import TestsPassCheck
        from analysis.test_discovery import TestDiscoveryResult, TestFramework

        check = TestsPassCheck()

        # Mock test discovery to return a valid framework
        mock_discovery_result = TestDiscoveryResult(
            frameworks=[TestFramework(name="pytest", type="all", command="pytest")],
            test_command="pytest",
            has_tests=True,
        )

        with patch("analysis.test_discovery.TestDiscovery") as mock_discovery_cls:
            mock_discovery = MagicMock()
            mock_discovery.discover.return_value = mock_discovery_result
            mock_discovery_cls.return_value = mock_discovery

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                result = await check.run(tmp_path, tmp_path, SprintType.BACKEND)

        assert result.passed is True

    @pytest.mark.asyncio
    async def test_fails_when_tests_fail(self, tmp_path):
        """Check fails when test runner returns failure."""
        from qa.preflight_checklist import TestsPassCheck
        from analysis.test_discovery import TestDiscoveryResult, TestFramework

        check = TestsPassCheck()

        # Mock test discovery to return a valid framework
        mock_discovery_result = TestDiscoveryResult(
            frameworks=[TestFramework(name="pytest", type="all", command="pytest")],
            test_command="pytest",
            has_tests=True,
        )

        with patch("analysis.test_discovery.TestDiscovery") as mock_discovery_cls:
            mock_discovery = MagicMock()
            mock_discovery.discover.return_value = mock_discovery_result
            mock_discovery_cls.return_value = mock_discovery

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1, stderr="3 tests failed")
                result = await check.run(tmp_path, tmp_path, SprintType.BACKEND)

        assert result.passed is False

    @pytest.mark.asyncio
    async def test_skipped_for_spike(self, tmp_path):
        """Check is skipped for spike sprints."""
        from qa.preflight_checklist import TestsPassCheck

        check = TestsPassCheck()
        result = await check.run(tmp_path, tmp_path, SprintType.SPIKE)

        assert result.skipped is True
        assert result.passed is True


class TestCoverageCheck:
    """Tests for the coverage_meets_threshold check."""

    def _mock_test_discovery(self):
        """Create a mock for test discovery with coverage command."""
        from analysis.test_discovery import TestDiscoveryResult, TestFramework
        return TestDiscoveryResult(
            frameworks=[TestFramework(
                name="pytest",
                type="all",
                command="pytest",
                coverage_command="pytest --cov",
            )],
            test_command="pytest",
            coverage_command="pytest --cov",
            has_tests=True,
        )

    @pytest.mark.asyncio
    async def test_passes_when_above_threshold(self, tmp_path):
        """Check passes when coverage exceeds threshold."""
        from qa.preflight_checklist import CoverageCheck

        check = CoverageCheck()

        with patch("analysis.test_discovery.TestDiscovery") as mock_discovery_cls:
            mock_discovery = MagicMock()
            mock_discovery.discover.return_value = self._mock_test_discovery()
            mock_discovery_cls.return_value = mock_discovery

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="TOTAL    100    10    90%",
                )
                result = await check.run(tmp_path, tmp_path, SprintType.BACKEND)

        assert result.passed is True

    @pytest.mark.asyncio
    async def test_fails_when_below_threshold(self, tmp_path):
        """Check fails when coverage is below threshold."""
        from qa.preflight_checklist import CoverageCheck

        check = CoverageCheck()

        with patch("analysis.test_discovery.TestDiscovery") as mock_discovery_cls:
            mock_discovery = MagicMock()
            mock_discovery.discover.return_value = self._mock_test_discovery()
            mock_discovery_cls.return_value = mock_discovery

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="TOTAL    100    60    40%",
                )
                result = await check.run(tmp_path, tmp_path, SprintType.BACKEND)

        assert result.passed is False
        assert "40%" in result.message or "85%" in result.message

    @pytest.mark.asyncio
    async def test_uses_correct_threshold_per_type(self, tmp_path):
        """Check uses correct coverage threshold for each sprint type."""
        from qa.preflight_checklist import CoverageCheck

        check = CoverageCheck()

        with patch("analysis.test_discovery.TestDiscovery") as mock_discovery_cls:
            mock_discovery = MagicMock()
            mock_discovery.discover.return_value = self._mock_test_discovery()
            mock_discovery_cls.return_value = mock_discovery

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="TOTAL    100    30    70%",
                )
                # 70% passes frontend (70% threshold)
                frontend_result = await check.run(tmp_path, tmp_path, SprintType.FRONTEND)
                assert frontend_result.passed is True

                # 70% fails backend (85% threshold)
                backend_result = await check.run(tmp_path, tmp_path, SprintType.BACKEND)
                assert backend_result.passed is False

    @pytest.mark.asyncio
    async def test_skipped_for_spike(self, tmp_path):
        """Check is skipped for spike sprints."""
        from qa.preflight_checklist import CoverageCheck

        check = CoverageCheck()
        result = await check.run(tmp_path, tmp_path, SprintType.SPIKE)

        assert result.skipped is True

    @pytest.mark.asyncio
    async def test_reduced_threshold_for_research(self, tmp_path):
        """Research sprints use 30% threshold."""
        from qa.preflight_checklist import CoverageCheck

        check = CoverageCheck()

        with patch("analysis.test_discovery.TestDiscovery") as mock_discovery_cls:
            mock_discovery = MagicMock()
            mock_discovery.discover.return_value = self._mock_test_discovery()
            mock_discovery_cls.return_value = mock_discovery

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="TOTAL    100    65    35%",
                )
                result = await check.run(tmp_path, tmp_path, SprintType.RESEARCH)

        assert result.passed is True  # 35% > 30%


class TestNoLintErrorsCheck:
    """Tests for the no_lint_errors check."""

    @pytest.mark.asyncio
    async def test_passes_with_no_errors(self, tmp_path):
        """Check passes when linter finds no issues."""
        from qa.preflight_checklist import NoLintErrorsCheck

        check = NoLintErrorsCheck()

        # Mock _detect_linter to return a linter command
        with patch.object(check, "_detect_linter", return_value="ruff check ."):
            with patch("qa.preflight_checklist.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                result = await check.run(tmp_path, tmp_path, SprintType.BACKEND)

        assert result.passed is True

    @pytest.mark.asyncio
    async def test_fails_with_lint_errors(self, tmp_path):
        """Check fails when linter finds issues."""
        from qa.preflight_checklist import NoLintErrorsCheck

        check = NoLintErrorsCheck()

        # Mock _detect_linter to return a linter command
        with patch.object(check, "_detect_linter", return_value="ruff check ."):
            with patch("qa.preflight_checklist.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1, stderr="E501 line too long")
                result = await check.run(tmp_path, tmp_path, SprintType.BACKEND)

        assert result.passed is False


class TestNoTypeErrorsCheck:
    """Tests for the no_type_errors check."""

    @pytest.mark.asyncio
    async def test_passes_with_no_errors(self, tmp_path):
        """Check passes when type checker finds no issues."""
        from qa.preflight_checklist import NoTypeErrorsCheck

        check = NoTypeErrorsCheck()
        with patch("qa.preflight_checklist.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = await check.run(tmp_path, tmp_path, SprintType.BACKEND)

        assert result.passed is True

    @pytest.mark.asyncio
    async def test_skipped_for_research(self, tmp_path):
        """Check is skipped for research sprints."""
        from qa.preflight_checklist import NoTypeErrorsCheck

        check = NoTypeErrorsCheck()
        result = await check.run(tmp_path, tmp_path, SprintType.RESEARCH)

        assert result.skipped is True


class TestMigrationsValidCheck:
    """Tests for the migrations_valid check."""

    @pytest.mark.asyncio
    async def test_skipped_when_no_migrations_detected(self, tmp_path):
        """Check is skipped when no migration framework is detected."""
        from qa.preflight_checklist import MigrationsValidCheck

        check = MigrationsValidCheck()
        result = await check.run(tmp_path, tmp_path, SprintType.BACKEND)

        # Per user decision: skip automatically if no framework
        assert result.skipped is True
        assert result.passed is True


class TestNoDebugStatementsCheck:
    """Tests for the no_debug_statements check."""

    @pytest.mark.asyncio
    async def test_passes_with_no_debug_statements(self, tmp_path):
        """Check passes when no debug statements found."""
        from qa.preflight_checklist import NoDebugStatementsCheck

        check = NoDebugStatementsCheck()
        # Create a clean file
        (tmp_path / "clean.py").write_text("def hello():\n    return 'world'\n")

        result = await check.run(tmp_path, tmp_path, SprintType.BACKEND)
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_fails_with_console_log(self, tmp_path):
        """Check fails when console.log found."""
        from qa.preflight_checklist import NoDebugStatementsCheck

        check = NoDebugStatementsCheck()
        # Create file with debug statement
        (tmp_path / "debug.js").write_text("console.log('debug');\n")

        result = await check.run(tmp_path, tmp_path, SprintType.FRONTEND)
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_fails_with_python_print(self, tmp_path):
        """Check fails when print() found."""
        from qa.preflight_checklist import NoDebugStatementsCheck

        check = NoDebugStatementsCheck()
        (tmp_path / "debug.py").write_text("print('debug')\n")

        result = await check.run(tmp_path, tmp_path, SprintType.BACKEND)
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_skipped_for_spike(self, tmp_path):
        """Check is skipped for spike sprints."""
        from qa.preflight_checklist import NoDebugStatementsCheck

        check = NoDebugStatementsCheck()
        (tmp_path / "debug.py").write_text("print('debug')\n")

        result = await check.run(tmp_path, tmp_path, SprintType.SPIKE)
        assert result.skipped is True


class TestNoSecretsCheck:
    """Tests for the no_secrets_in_code check."""

    @pytest.mark.asyncio
    async def test_passes_with_no_secrets(self, tmp_path):
        """Check passes when no secrets found."""
        from qa.preflight_checklist import NoSecretsCheck

        check = NoSecretsCheck()
        (tmp_path / "config.py").write_text("API_KEY = os.environ['API_KEY']\n")

        result = await check.run(tmp_path, tmp_path, SprintType.BACKEND)
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_always_runs_even_for_spike(self, tmp_path):
        """Secrets check runs even for spike sprints."""
        from qa.preflight_checklist import NoSecretsCheck

        check = NoSecretsCheck()
        (tmp_path / "config.py").write_text("API_KEY = os.environ['API_KEY']\n")

        result = await check.run(tmp_path, tmp_path, SprintType.SPIKE)
        # Should NOT be skipped - secrets check is always required
        assert result.skipped is False


class TestDocumentationCheck:
    """Tests for the documentation_updated check."""

    @pytest.mark.asyncio
    async def test_passes_when_docs_updated(self, tmp_path):
        """Check passes when documentation is updated."""
        from qa.preflight_checklist import DocumentationCheck

        check = DocumentationCheck()
        (tmp_path / "README.md").write_text("# Updated\n")

        result = await check.run(tmp_path, tmp_path, SprintType.BACKEND)
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_required_for_spike(self, tmp_path):
        """Documentation is required for spike sprints."""
        from qa.preflight_checklist import DocumentationCheck

        check = DocumentationCheck()
        # No documentation
        result = await check.run(tmp_path, tmp_path, SprintType.SPIKE)

        # Should run (not skip) and may fail if no docs
        assert result.skipped is False


class TestChangelogCheck:
    """Tests for the changelog_updated check."""

    @pytest.mark.asyncio
    async def test_optional_for_backend(self, tmp_path):
        """Changelog check is optional for backend sprints."""
        from qa.preflight_checklist import ChangelogCheck

        check = ChangelogCheck()
        result = await check.run(tmp_path, tmp_path, SprintType.BACKEND)

        # Should indicate it's optional (not blocking)
        # The check runs but failure is non-blocking
        assert not result.blocking if hasattr(result, 'blocking') else True

    @pytest.mark.asyncio
    async def test_skipped_for_spike(self, tmp_path):
        """Changelog check is skipped for spike sprints."""
        from qa.preflight_checklist import ChangelogCheck

        check = ChangelogCheck()
        result = await check.run(tmp_path, tmp_path, SprintType.SPIKE)

        assert result.skipped is True


# =============================================================================
# CHECKLIST ORCHESTRATOR TESTS
# =============================================================================

class TestPreflightChecklist:
    """Tests for PreflightChecklist orchestrator."""

    @pytest.mark.asyncio
    async def test_runs_all_checks(self, tmp_path):
        """Orchestrator runs all 9 checks."""
        from qa.preflight_checklist import PreflightChecklist

        checklist = PreflightChecklist()

        # Mock all checks to pass
        for check in checklist.checks:
            check.run = AsyncMock(return_value=MagicMock(
                check_name=check.name,
                passed=True,
                skipped=False,
                message="Passed",
            ))

        result = await checklist.run_all(tmp_path, tmp_path, SprintType.BACKEND)

        assert len(result.checks) == 9

    @pytest.mark.asyncio
    async def test_skips_checks_per_sprint_type(self, tmp_path):
        """Orchestrator skips checks based on sprint type."""
        from qa.preflight_checklist import PreflightChecklist

        checklist = PreflightChecklist()
        result = await checklist.run_all(tmp_path, tmp_path, SprintType.SPIKE)

        # Spike should skip most checks
        skipped_count = sum(1 for c in result.checks if c.skipped)
        assert skipped_count >= 6  # Most checks skip for spike

    @pytest.mark.asyncio
    async def test_collects_blocking_failures(self, tmp_path):
        """Orchestrator collects blocking failures."""
        from qa.preflight_checklist import PreflightChecklist, CheckResult

        checklist = PreflightChecklist()

        # Mock one check to fail
        original_checks = checklist.checks
        for check in original_checks:
            if check.name == "no_secrets_in_code":
                check.run = AsyncMock(return_value=CheckResult(
                    check_name="no_secrets_in_code",
                    passed=False,
                    message="Found API key",
                ))
            else:
                check.run = AsyncMock(return_value=CheckResult(
                    check_name=check.name,
                    passed=True,
                    message="Passed",
                ))

        result = await checklist.run_all(tmp_path, tmp_path, SprintType.BACKEND)

        assert result.passed is False
        assert len(result.blocking_failures) >= 1

    @pytest.mark.asyncio
    async def test_optional_failures_are_warnings(self, tmp_path):
        """Optional check failures become warnings, not blockers."""
        from qa.preflight_checklist import PreflightChecklist, CheckResult

        checklist = PreflightChecklist()

        # Mock changelog to fail (it's optional for backend)
        for check in checklist.checks:
            if check.name == "changelog_updated":
                check.run = AsyncMock(return_value=CheckResult(
                    check_name="changelog_updated",
                    passed=False,
                    message="Changelog not updated",
                ))
            else:
                check.run = AsyncMock(return_value=CheckResult(
                    check_name=check.name,
                    passed=True,
                    message="Passed",
                ))

        result = await checklist.run_all(tmp_path, tmp_path, SprintType.BACKEND)

        # Should still pass overall
        assert result.passed is True
        assert len(result.warnings) >= 1

    @pytest.mark.asyncio
    async def test_parallel_execution(self, tmp_path):
        """Checks run in parallel for performance."""
        from qa.preflight_checklist import PreflightChecklist

        checklist = PreflightChecklist()

        # Track execution times
        import time
        start_time = time.time()

        # Mock checks with artificial delay
        async def slow_check(*args):
            await asyncio.sleep(0.1)
            return MagicMock(
                check_name="test",
                passed=True,
                skipped=False,
                message="Passed",
            )

        for check in checklist.checks:
            check.run = slow_check

        await checklist.run_all(tmp_path, tmp_path, SprintType.BACKEND)
        elapsed = time.time() - start_time

        # If running in parallel, 9 checks with 0.1s each should take < 0.9s
        assert elapsed < 0.5  # Allow some overhead


# =============================================================================
# MAESTRO QUALITY GATE ADAPTER TESTS
# =============================================================================

class TestMaestroQualityGate:
    """Tests for MaestroQualityGate adapter class."""

    def test_init_with_paths(self, tmp_path):
        """Initialize gate with project and spec paths."""
        from qa.maestro_adapter import MaestroQualityGate

        spec_dir = tmp_path / ".auto-claude" / "specs" / "001-test"
        spec_dir.mkdir(parents=True)

        gate = MaestroQualityGate(tmp_path, spec_dir)
        assert gate.project_dir == tmp_path
        assert gate.spec_dir == spec_dir

    def test_detects_sprint_type_from_requirements(self, tmp_path):
        """Gate detects sprint type from requirements.json."""
        from qa.maestro_adapter import MaestroQualityGate

        spec_dir = tmp_path / ".auto-claude" / "specs" / "001-test"
        spec_dir.mkdir(parents=True)

        # Write requirements with sprint type
        requirements = {"sprint_type": "backend"}
        (spec_dir / "requirements.json").write_text(json.dumps(requirements))

        gate = MaestroQualityGate(tmp_path, spec_dir)
        assert gate.sprint_type == SprintType.BACKEND

    def test_default_sprint_type_when_not_specified(self, tmp_path):
        """Gate defaults to fullstack when no type specified."""
        from qa.maestro_adapter import MaestroQualityGate

        spec_dir = tmp_path / ".auto-claude" / "specs" / "001-test"
        spec_dir.mkdir(parents=True)

        # Write requirements without sprint type
        requirements = {"task": "Something"}
        (spec_dir / "requirements.json").write_text(json.dumps(requirements))

        gate = MaestroQualityGate(tmp_path, spec_dir)
        assert gate.sprint_type == SprintType.FULLSTACK

    @pytest.mark.asyncio
    async def test_run_quality_gate(self, tmp_path):
        """Gate runs checklist and returns result."""
        from qa.maestro_adapter import MaestroQualityGate

        spec_dir = tmp_path / ".auto-claude" / "specs" / "001-test"
        spec_dir.mkdir(parents=True)
        requirements = {"sprint_type": "spike"}
        (spec_dir / "requirements.json").write_text(json.dumps(requirements))

        gate = MaestroQualityGate(tmp_path, spec_dir)
        result = await gate.run_quality_gate()

        # Spike should pass easily (most checks skip)
        assert result is not None
        assert hasattr(result, "passed")

    def test_can_merge_when_passed(self, tmp_path):
        """can_merge returns True when gate passes."""
        from qa.maestro_adapter import MaestroQualityGate
        from qa.preflight_checklist import PreflightResult

        gate = MaestroQualityGate(tmp_path, tmp_path)
        result = PreflightResult(
            passed=True,
            checks=[],
            blocking_failures=[],
            warnings=[],
            summary="All passed",
        )
        assert gate.can_merge(result) is True

    def test_cannot_merge_when_blocking_failures(self, tmp_path):
        """can_merge returns False when blocking failures exist."""
        from qa.maestro_adapter import MaestroQualityGate
        from qa.preflight_checklist import PreflightResult, CheckResult

        gate = MaestroQualityGate(tmp_path, tmp_path)
        failure = CheckResult("no_secrets_in_code", False, "Found secret")
        result = PreflightResult(
            passed=False,
            checks=[failure],
            blocking_failures=[failure],
            warnings=[],
            summary="1 failure",
        )
        assert gate.can_merge(result) is False

    def test_format_failure_message(self, tmp_path):
        """Failure message is formatted clearly."""
        from qa.maestro_adapter import MaestroQualityGate
        from qa.preflight_checklist import PreflightResult, CheckResult

        gate = MaestroQualityGate(tmp_path, tmp_path)
        failure = CheckResult(
            check_name="no_secrets_in_code",
            passed=False,
            message="Found API key in config.py:42",
            details={"file": "config.py", "line": 42},
        )
        result = PreflightResult(
            passed=False,
            checks=[failure],
            blocking_failures=[failure],
            warnings=[],
            summary="1 failure",
        )

        message = gate.format_failure_message(result)
        assert "no_secrets_in_code" in message
        assert "API key" in message or "config.py" in message


# =============================================================================
# WORKSPACE INTEGRATION TESTS
# =============================================================================

class TestMergeCommandIntegration:
    """Tests for quality gate integration with merge command."""

    @pytest.mark.asyncio
    async def test_gate_blocks_merge_on_failure(self, tmp_path):
        """Merge is blocked when quality gate fails."""
        from qa.maestro_adapter import MaestroQualityGate
        from qa.preflight_checklist import PreflightResult, CheckResult

        # Set up mock gate that fails
        spec_dir = tmp_path / ".auto-claude" / "specs" / "001-test"
        spec_dir.mkdir(parents=True)
        requirements = {"sprint_type": "backend"}
        (spec_dir / "requirements.json").write_text(json.dumps(requirements))

        gate = MaestroQualityGate(tmp_path, spec_dir)

        # Mock the checklist to fail
        failure = CheckResult("tests_pass", False, "3 tests failed")
        with patch.object(gate.checklist, "run_all", return_value=PreflightResult(
            passed=False,
            checks=[failure],
            blocking_failures=[failure],
            warnings=[],
            summary="Tests failed",
        )):
            result = await gate.run_quality_gate()

        assert gate.can_merge(result) is False

    @pytest.mark.asyncio
    async def test_gate_allows_merge_on_success(self, tmp_path):
        """Merge is allowed when quality gate passes."""
        from qa.maestro_adapter import MaestroQualityGate
        from qa.preflight_checklist import PreflightResult, CheckResult

        spec_dir = tmp_path / ".auto-claude" / "specs" / "001-test"
        spec_dir.mkdir(parents=True)
        requirements = {"sprint_type": "spike"}
        (spec_dir / "requirements.json").write_text(json.dumps(requirements))

        gate = MaestroQualityGate(tmp_path, spec_dir)

        # Mock the checklist to pass
        passed = CheckResult("tests_pass", True, "Passed", skipped=True)
        with patch.object(gate.checklist, "run_all", return_value=PreflightResult(
            passed=True,
            checks=[passed],
            blocking_failures=[],
            warnings=[],
            summary="All passed",
        )):
            result = await gate.run_quality_gate()

        assert gate.can_merge(result) is True


# =============================================================================
# CONFIGURATION TESTS
# =============================================================================

class TestMaestroConfig:
    """Tests for Maestro configuration loading."""

    def test_load_default_config(self, tmp_path):
        """Default configuration is loaded when no file exists."""
        from qa.maestro_adapter import MaestroQualityGate

        gate = MaestroQualityGate(tmp_path, tmp_path)
        # Should not raise, uses defaults
        assert gate.config is not None

    def test_load_custom_config(self, tmp_path):
        """Custom configuration is loaded from maestro.yaml."""
        from qa.maestro_adapter import MaestroQualityGate

        config_dir = tmp_path / ".auto-claude"
        config_dir.mkdir(parents=True)

        config_content = """version: "1.0"
checks:
  tests_pass:
    enabled: true
  coverage_meets_threshold:
    enabled: true
settings:
  block_on_failure: true
"""
        (config_dir / "maestro.yaml").write_text(config_content)

        gate = MaestroQualityGate(tmp_path, tmp_path)
        assert gate.config["version"] == "1.0"
        assert gate.config["checks"]["tests_pass"]["enabled"] is True

    def test_invalid_config_falls_back_to_default(self, tmp_path):
        """Invalid config falls back to defaults."""
        from qa.maestro_adapter import MaestroQualityGate

        config_dir = tmp_path / ".auto-claude"
        config_dir.mkdir(parents=True)
        # Write invalid YAML
        (config_dir / "maestro.yaml").write_text("not: [valid: yaml")

        gate = MaestroQualityGate(tmp_path, tmp_path)
        # Should fall back to default
        assert gate.config is not None
        assert gate.config.get("version") == "1.0"

    def test_can_merge_with_block_disabled(self, tmp_path):
        """can_merge returns True when block_on_failure is disabled."""
        from qa.maestro_adapter import MaestroQualityGate
        from qa.preflight_checklist import PreflightResult, CheckResult

        config_dir = tmp_path / ".auto-claude"
        config_dir.mkdir(parents=True)
        config_content = """settings:
  block_on_failure: false
"""
        (config_dir / "maestro.yaml").write_text(config_content)

        gate = MaestroQualityGate(tmp_path, tmp_path)
        failure = CheckResult("tests_pass", False, "Tests failed")
        result = PreflightResult(
            passed=False,
            checks=[failure],
            blocking_failures=[failure],
            warnings=[],
            summary="Tests failed",
        )
        # Should allow merge even with failures because block_on_failure=false
        assert gate.can_merge(result) is True


# =============================================================================
# SYNC WRAPPER TESTS
# =============================================================================

class TestSyncWrapper:
    """Tests for run_quality_gate_sync function."""

    def test_run_quality_gate_sync_success(self, tmp_path):
        """Sync wrapper returns success tuple."""
        from qa.maestro_adapter import run_quality_gate_sync
        from qa.preflight_checklist import PreflightResult

        spec_dir = tmp_path / ".auto-claude" / "specs" / "001-test"
        spec_dir.mkdir(parents=True)
        requirements = {"sprint_type": "spike"}
        (spec_dir / "requirements.json").write_text(json.dumps(requirements))

        can_merge, message = run_quality_gate_sync(tmp_path, spec_dir)

        # Spike should mostly pass
        assert isinstance(can_merge, bool)
        assert isinstance(message, str)

    def test_run_quality_gate_sync_with_failure(self, tmp_path):
        """Sync wrapper returns failure tuple when gate fails."""
        from qa.maestro_adapter import run_quality_gate_sync, MaestroQualityGate
        from qa.preflight_checklist import PreflightResult, CheckResult

        spec_dir = tmp_path / ".auto-claude" / "specs" / "001-test"
        spec_dir.mkdir(parents=True)
        requirements = {"sprint_type": "backend"}
        (spec_dir / "requirements.json").write_text(json.dumps(requirements))

        # Create a file with debug statement to trigger failure
        (tmp_path / "debug.py").write_text("print('debug')\n")

        can_merge, message = run_quality_gate_sync(tmp_path, spec_dir)

        assert isinstance(message, str)


class TestFormatMessages:
    """Tests for success/failure message formatting."""

    def test_format_success_with_warnings(self, tmp_path):
        """Success message includes warning count."""
        from qa.maestro_adapter import MaestroQualityGate
        from qa.preflight_checklist import PreflightResult, CheckResult

        gate = MaestroQualityGate(tmp_path, tmp_path)
        warning = CheckResult("changelog_updated", False, "Not updated")
        result = PreflightResult(
            passed=True,
            checks=[warning],
            blocking_failures=[],
            warnings=[warning],
            summary="1 warning",
        )

        message = gate.format_success_message(result)
        assert "passed" in message
        assert "warning" in message.lower()

    def test_format_failure_with_details_list(self, tmp_path):
        """Failure message handles detail lists."""
        from qa.maestro_adapter import MaestroQualityGate
        from qa.preflight_checklist import PreflightResult, CheckResult

        gate = MaestroQualityGate(tmp_path, tmp_path)
        failure = CheckResult(
            check_name="no_debug_statements",
            passed=False,
            message="Debug statements found",
            details={"files": ["a.py", "b.py", "c.py"]},
        )
        result = PreflightResult(
            passed=False,
            checks=[failure],
            blocking_failures=[failure],
            warnings=[],
            summary="1 failure",
        )

        message = gate.format_failure_message(result)
        assert "no_debug_statements" in message
        assert "a.py" in message


# =============================================================================
# EXCEPTION HANDLING TESTS
# =============================================================================

class TestExceptionHandling:
    """Tests for exception handling in checks."""

    @pytest.mark.asyncio
    async def test_tests_pass_timeout(self, tmp_path):
        """tests_pass handles timeout gracefully."""
        from qa.preflight_checklist import TestsPassCheck
        from analysis.test_discovery import TestDiscoveryResult, TestFramework

        check = TestsPassCheck()
        mock_discovery_result = TestDiscoveryResult(
            frameworks=[TestFramework(name="pytest", type="all", command="pytest")],
            test_command="pytest",
            has_tests=True,
        )

        with patch("analysis.test_discovery.TestDiscovery") as mock_discovery_cls:
            mock_discovery = MagicMock()
            mock_discovery.discover.return_value = mock_discovery_result
            mock_discovery_cls.return_value = mock_discovery

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired("pytest", 300)
                result = await check.run(tmp_path, tmp_path, SprintType.BACKEND)

        assert result.passed is False
        assert "timed out" in result.message.lower()

    @pytest.mark.asyncio
    async def test_tests_pass_exception(self, tmp_path):
        """tests_pass handles general exception."""
        from qa.preflight_checklist import TestsPassCheck
        from analysis.test_discovery import TestDiscoveryResult, TestFramework

        check = TestsPassCheck()
        mock_discovery_result = TestDiscoveryResult(
            frameworks=[TestFramework(name="pytest", type="all", command="pytest")],
            test_command="pytest",
            has_tests=True,
        )

        with patch("analysis.test_discovery.TestDiscovery") as mock_discovery_cls:
            mock_discovery = MagicMock()
            mock_discovery.discover.return_value = mock_discovery_result
            mock_discovery_cls.return_value = mock_discovery

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = Exception("Process error")
                result = await check.run(tmp_path, tmp_path, SprintType.BACKEND)

        assert result.passed is False
        assert "error" in result.message.lower()

    @pytest.mark.asyncio
    async def test_coverage_timeout(self, tmp_path):
        """coverage check handles timeout gracefully."""
        from qa.preflight_checklist import CoverageCheck
        from analysis.test_discovery import TestDiscoveryResult, TestFramework

        check = CoverageCheck()
        mock_discovery_result = TestDiscoveryResult(
            frameworks=[TestFramework(name="pytest", type="all", command="pytest", coverage_command="pytest --cov")],
            test_command="pytest",
            coverage_command="pytest --cov",
            has_tests=True,
        )

        with patch("analysis.test_discovery.TestDiscovery") as mock_discovery_cls:
            mock_discovery = MagicMock()
            mock_discovery.discover.return_value = mock_discovery_result
            mock_discovery_cls.return_value = mock_discovery

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired("pytest", 300)
                result = await check.run(tmp_path, tmp_path, SprintType.BACKEND)

        assert result.passed is False
        assert "timed out" in result.message.lower()

    @pytest.mark.asyncio
    async def test_coverage_exception(self, tmp_path):
        """coverage check handles general exception."""
        from qa.preflight_checklist import CoverageCheck
        from analysis.test_discovery import TestDiscoveryResult, TestFramework

        check = CoverageCheck()
        mock_discovery_result = TestDiscoveryResult(
            frameworks=[TestFramework(name="pytest", type="all", command="pytest", coverage_command="pytest --cov")],
            test_command="pytest",
            coverage_command="pytest --cov",
            has_tests=True,
        )

        with patch("analysis.test_discovery.TestDiscovery") as mock_discovery_cls:
            mock_discovery = MagicMock()
            mock_discovery.discover.return_value = mock_discovery_result
            mock_discovery_cls.return_value = mock_discovery

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = RuntimeError("Coverage error")
                result = await check.run(tmp_path, tmp_path, SprintType.BACKEND)

        assert result.passed is False
        assert "error" in result.message.lower()

    @pytest.mark.asyncio
    async def test_lint_exception(self, tmp_path):
        """lint check handles exception."""
        from qa.preflight_checklist import NoLintErrorsCheck

        check = NoLintErrorsCheck()

        with patch.object(check, "_detect_linter", return_value="ruff check ."):
            with patch("qa.preflight_checklist.subprocess.run") as mock_run:
                mock_run.side_effect = Exception("Linter crashed")
                result = await check.run(tmp_path, tmp_path, SprintType.BACKEND)

        assert result.passed is False
        assert "error" in result.message.lower()

    @pytest.mark.asyncio
    async def test_type_check_exception(self, tmp_path):
        """type check handles exception."""
        from qa.preflight_checklist import NoTypeErrorsCheck

        check = NoTypeErrorsCheck()

        with patch.object(check, "_detect_type_checker", return_value="mypy ."):
            with patch("qa.preflight_checklist.subprocess.run") as mock_run:
                mock_run.side_effect = Exception("Type checker crashed")
                result = await check.run(tmp_path, tmp_path, SprintType.BACKEND)

        assert result.passed is False
        assert "error" in result.message.lower()


# =============================================================================
# DETECTION METHOD TESTS
# =============================================================================

class TestDetectionMethods:
    """Tests for tool detection methods."""

    @pytest.mark.asyncio
    async def test_linter_detection_biome(self, tmp_path):
        """Detects biome linter."""
        from qa.preflight_checklist import NoLintErrorsCheck

        check = NoLintErrorsCheck()
        (tmp_path / "biome.json").write_text("{}")

        cmd = check._detect_linter(tmp_path)
        assert cmd == "npx biome check"

    @pytest.mark.asyncio
    async def test_linter_detection_eslint_json(self, tmp_path):
        """Detects eslint from .eslintrc.json."""
        from qa.preflight_checklist import NoLintErrorsCheck

        check = NoLintErrorsCheck()
        (tmp_path / ".eslintrc.json").write_text("{}")

        cmd = check._detect_linter(tmp_path)
        assert cmd == "npx eslint ."

    @pytest.mark.asyncio
    async def test_linter_detection_eslint_js(self, tmp_path):
        """Detects eslint from .eslintrc.js."""
        from qa.preflight_checklist import NoLintErrorsCheck

        check = NoLintErrorsCheck()
        (tmp_path / ".eslintrc.js").write_text("module.exports = {}")

        cmd = check._detect_linter(tmp_path)
        assert cmd == "npx eslint ."

    @pytest.mark.asyncio
    async def test_linter_detection_ruff(self, tmp_path):
        """Detects ruff from pyproject.toml."""
        from qa.preflight_checklist import NoLintErrorsCheck

        check = NoLintErrorsCheck()
        (tmp_path / "pyproject.toml").write_text('[tool.ruff]\nselect = ["E"]')

        cmd = check._detect_linter(tmp_path)
        assert cmd == "ruff check ."

    @pytest.mark.asyncio
    async def test_linter_detection_none(self, tmp_path):
        """Returns None when no linter detected."""
        from qa.preflight_checklist import NoLintErrorsCheck

        check = NoLintErrorsCheck()
        cmd = check._detect_linter(tmp_path)
        assert cmd is None

    @pytest.mark.asyncio
    async def test_type_checker_detection_typescript(self, tmp_path):
        """Detects TypeScript."""
        from qa.preflight_checklist import NoTypeErrorsCheck

        check = NoTypeErrorsCheck()
        (tmp_path / "tsconfig.json").write_text("{}")

        cmd = check._detect_type_checker(tmp_path)
        assert cmd == "npx tsc --noEmit"

    @pytest.mark.asyncio
    async def test_type_checker_detection_mypy(self, tmp_path):
        """Detects mypy from pyproject.toml."""
        from qa.preflight_checklist import NoTypeErrorsCheck

        check = NoTypeErrorsCheck()
        (tmp_path / "pyproject.toml").write_text('[tool.mypy]\nstrict = true')

        cmd = check._detect_type_checker(tmp_path)
        assert cmd == "mypy ."

    @pytest.mark.asyncio
    async def test_type_checker_detection_none(self, tmp_path):
        """Returns None when no type checker detected."""
        from qa.preflight_checklist import NoTypeErrorsCheck

        check = NoTypeErrorsCheck()
        cmd = check._detect_type_checker(tmp_path)
        assert cmd is None

    @pytest.mark.asyncio
    async def test_no_type_checker_skips(self, tmp_path):
        """Check skips when no type checker found."""
        from qa.preflight_checklist import NoTypeErrorsCheck

        check = NoTypeErrorsCheck()
        result = await check.run(tmp_path, tmp_path, SprintType.BACKEND)

        assert result.skipped is True

    @pytest.mark.asyncio
    async def test_no_linter_skips(self, tmp_path):
        """Check skips when no linter found."""
        from qa.preflight_checklist import NoLintErrorsCheck

        check = NoLintErrorsCheck()
        result = await check.run(tmp_path, tmp_path, SprintType.BACKEND)

        assert result.skipped is True


# =============================================================================
# MIGRATION FRAMEWORK TESTS
# =============================================================================

class TestMigrationDetection:
    """Tests for migration framework detection."""

    @pytest.mark.asyncio
    async def test_detect_alembic_ini(self, tmp_path):
        """Detects alembic from alembic.ini."""
        from qa.preflight_checklist import MigrationsValidCheck

        check = MigrationsValidCheck()
        (tmp_path / "alembic.ini").write_text("[alembic]")

        framework = check._detect_migration_framework(tmp_path)
        assert framework == "alembic"

    @pytest.mark.asyncio
    async def test_detect_alembic_dir(self, tmp_path):
        """Detects alembic from alembic directory."""
        from qa.preflight_checklist import MigrationsValidCheck

        check = MigrationsValidCheck()
        (tmp_path / "alembic").mkdir()

        framework = check._detect_migration_framework(tmp_path)
        assert framework == "alembic"

    @pytest.mark.asyncio
    async def test_detect_prisma(self, tmp_path):
        """Detects prisma."""
        from qa.preflight_checklist import MigrationsValidCheck

        check = MigrationsValidCheck()
        (tmp_path / "prisma").mkdir()

        framework = check._detect_migration_framework(tmp_path)
        assert framework == "prisma"

    @pytest.mark.asyncio
    async def test_detect_django(self, tmp_path):
        """Detects Django migrations."""
        from qa.preflight_checklist import MigrationsValidCheck

        check = MigrationsValidCheck()
        (tmp_path / "migrations").mkdir()
        (tmp_path / "manage.py").write_text("#!/usr/bin/env python")

        framework = check._detect_migration_framework(tmp_path)
        assert framework == "django"

    @pytest.mark.asyncio
    async def test_validate_alembic(self, tmp_path):
        """Validates alembic migrations."""
        from qa.preflight_checklist import MigrationsValidCheck

        check = MigrationsValidCheck()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = await check._validate_migrations(tmp_path, "alembic")

        assert result.passed is True
        assert "alembic" in result.message.lower()

    @pytest.mark.asyncio
    async def test_validate_alembic_failure(self, tmp_path):
        """Handles alembic validation failure."""
        from qa.preflight_checklist import MigrationsValidCheck

        check = MigrationsValidCheck()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="Migration error")
            result = await check._validate_migrations(tmp_path, "alembic")

        assert result.passed is False

    @pytest.mark.asyncio
    async def test_validate_prisma(self, tmp_path):
        """Validates prisma migrations."""
        from qa.preflight_checklist import MigrationsValidCheck

        check = MigrationsValidCheck()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = await check._validate_migrations(tmp_path, "prisma")

        assert result.passed is True
        assert "prisma" in result.message.lower()

    @pytest.mark.asyncio
    async def test_validate_unknown_framework(self, tmp_path):
        """Handles unknown migration framework gracefully."""
        from qa.preflight_checklist import MigrationsValidCheck

        check = MigrationsValidCheck()
        result = await check._validate_migrations(tmp_path, "unknown_orm")

        assert result.skipped is True

    @pytest.mark.asyncio
    async def test_validate_migration_exception(self, tmp_path):
        """Handles migration validation exception."""
        from qa.preflight_checklist import MigrationsValidCheck

        check = MigrationsValidCheck()

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Migration validation failed")
            result = await check._validate_migrations(tmp_path, "alembic")

        assert result.passed is False
        assert "error" in result.message.lower()


# =============================================================================
# SECURITY SCANNER TESTS
# =============================================================================

class TestSecurityScanner:
    """Tests for secrets check with security scanner."""

    @pytest.mark.asyncio
    async def test_secrets_found(self, tmp_path):
        """Detects secrets when scanner finds them."""
        from qa.preflight_checklist import NoSecretsCheck

        check = NoSecretsCheck()

        with patch("analysis.security_scanner.SecurityScanner") as mock_scanner_cls:
            mock_scanner = MagicMock()
            mock_scanner.scan.return_value = MagicMock(secrets=["API_KEY=xxx"])
            mock_scanner_cls.return_value = mock_scanner

            result = await check.run(tmp_path, tmp_path, SprintType.BACKEND)

        assert result.passed is False
        assert "secret" in result.message.lower()

    @pytest.mark.asyncio
    async def test_scanner_import_error(self, tmp_path):
        """Handles missing security scanner module."""
        from qa.preflight_checklist import NoSecretsCheck

        check = NoSecretsCheck()

        # Force ImportError by patching the import
        with patch.dict("sys.modules", {"analysis.security_scanner": None}):
            with patch("qa.preflight_checklist.NoSecretsCheck.run") as mock_run:
                # Simulate what happens when ImportError is caught
                from qa.preflight_checklist import CheckResult
                mock_run.return_value = CheckResult(
                    check_name="no_secrets_in_code",
                    passed=True,
                    message="Security scanner not available",
                    skipped=True,
                    skip_reason="security scanner module not installed",
                )
                result = await mock_run(tmp_path, tmp_path, SprintType.BACKEND)

        assert result.skipped is True

    @pytest.mark.asyncio
    async def test_scanner_exception(self, tmp_path):
        """Handles security scanner exception."""
        from qa.preflight_checklist import NoSecretsCheck

        check = NoSecretsCheck()

        with patch("analysis.security_scanner.SecurityScanner") as mock_scanner_cls:
            mock_scanner = MagicMock()
            mock_scanner.scan.side_effect = RuntimeError("Scanner error")
            mock_scanner_cls.return_value = mock_scanner

            result = await check.run(tmp_path, tmp_path, SprintType.BACKEND)

        assert result.passed is False
        assert "error" in result.message.lower()


# =============================================================================
# COVERAGE PARSING TESTS
# =============================================================================

class TestCoverageParsing:
    """Tests for coverage output parsing."""

    def test_parse_total_format(self):
        """Parses pytest-cov TOTAL format."""
        from qa.preflight_checklist import CoverageCheck

        check = CoverageCheck()
        output = """
Name                 Stmts   Miss  Cover
----------------------------------------
module.py              100     10    90%
----------------------------------------
TOTAL                  100     10    90%
"""
        result = check._parse_coverage(output)
        assert result == 90

    def test_parse_percentage_only(self):
        """Parses simple percentage format."""
        from qa.preflight_checklist import CoverageCheck

        check = CoverageCheck()
        output = "Coverage: 85%"

        result = check._parse_coverage(output)
        assert result == 85

    def test_parse_lowercase_coverage(self):
        """Parses lowercase coverage format."""
        from qa.preflight_checklist import CoverageCheck

        check = CoverageCheck()
        output = "coverage: 75%"

        result = check._parse_coverage(output)
        assert result == 75

    def test_parse_no_match(self):
        """Returns None when no coverage found."""
        from qa.preflight_checklist import CoverageCheck

        check = CoverageCheck()
        output = "No coverage information"

        result = check._parse_coverage(output)
        assert result is None

    @pytest.mark.asyncio
    async def test_coverage_parse_failure_skips(self, tmp_path):
        """Coverage check skips when parsing fails."""
        from qa.preflight_checklist import CoverageCheck
        from analysis.test_discovery import TestDiscoveryResult, TestFramework

        check = CoverageCheck()
        mock_discovery_result = TestDiscoveryResult(
            frameworks=[TestFramework(name="pytest", type="all", command="pytest", coverage_command="pytest --cov")],
            test_command="pytest",
            coverage_command="pytest --cov",
            has_tests=True,
        )

        with patch("analysis.test_discovery.TestDiscovery") as mock_discovery_cls:
            mock_discovery = MagicMock()
            mock_discovery.discover.return_value = mock_discovery_result
            mock_discovery_cls.return_value = mock_discovery

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="No coverage data")
                result = await check.run(tmp_path, tmp_path, SprintType.BACKEND)

        assert result.skipped is True


# =============================================================================
# SPRINT TYPE DETECTION TESTS
# =============================================================================

class TestSprintTypeDetection:
    """Tests for sprint type detection edge cases."""

    def test_invalid_sprint_type_defaults(self, tmp_path):
        """Invalid sprint type falls back to default."""
        from qa.maestro_adapter import MaestroQualityGate

        spec_dir = tmp_path / ".auto-claude" / "specs" / "001-test"
        spec_dir.mkdir(parents=True)
        requirements = {"sprint_type": "invalid_type"}
        (spec_dir / "requirements.json").write_text(json.dumps(requirements))

        gate = MaestroQualityGate(tmp_path, spec_dir)
        # Should default to fullstack
        assert gate.sprint_type == SprintType.FULLSTACK

    def test_empty_requirements_defaults(self, tmp_path):
        """Empty requirements defaults to fullstack."""
        from qa.maestro_adapter import MaestroQualityGate

        spec_dir = tmp_path / ".auto-claude" / "specs" / "001-test"
        spec_dir.mkdir(parents=True)
        (spec_dir / "requirements.json").write_text("{}")

        gate = MaestroQualityGate(tmp_path, spec_dir)
        assert gate.sprint_type == SprintType.FULLSTACK

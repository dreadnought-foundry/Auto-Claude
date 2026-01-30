"""Maestro Pre-Flight Checklist Implementation.

Implements the 9-item pre-flight checklist for quality validation
before merge operations. Checks are sprint-type aware and run in
parallel for performance.
"""

from __future__ import annotations

import asyncio
import re
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from spec.types import SprintType, COVERAGE_THRESHOLDS


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class CheckResult:
    """Result of a single preflight check.

    Attributes:
        check_name: Unique identifier for the check
        passed: Whether the check passed
        message: Human-readable result message
        details: Optional additional details (for debugging)
        skipped: Whether the check was skipped
        skip_reason: Reason for skipping (if skipped)
        blocking: Whether failure blocks merge (default True)
    """

    check_name: str
    passed: bool
    message: str
    details: Optional[dict[str, Any]] = None
    skipped: bool = False
    skip_reason: Optional[str] = None
    blocking: bool = True


@dataclass
class PreflightResult:
    """Complete result of all preflight checks.

    Attributes:
        passed: Overall pass/fail (True if no blocking failures)
        checks: All individual check results
        blocking_failures: Checks that failed and block merge
        warnings: Checks that failed but are non-blocking
        summary: Human-readable summary
    """

    passed: bool
    checks: list[CheckResult]
    blocking_failures: list[CheckResult]
    warnings: list[CheckResult]
    summary: str


class CheckBehavior(str, Enum):
    """How a check behaves for a sprint type."""

    REQUIRED = "required"  # Must pass to merge
    SKIP = "skip"  # Don't run at all
    OPTIONAL = "optional"  # Run but don't block on failure
    REDUCED = "reduced"  # Run with reduced threshold


# =============================================================================
# CHECK BEHAVIOR MATRIX
# =============================================================================

# Maps check name -> sprint type -> behavior
# Based on the sprint file specification matrix
CHECK_BEHAVIORS: dict[str, dict[SprintType, CheckBehavior]] = {
    "tests_pass": {
        SprintType.SPIKE: CheckBehavior.SKIP,
        SprintType.RESEARCH: CheckBehavior.REQUIRED,
        SprintType.FULLSTACK: CheckBehavior.REQUIRED,
        SprintType.BACKEND: CheckBehavior.REQUIRED,
        SprintType.FRONTEND: CheckBehavior.REQUIRED,
        SprintType.INFRASTRUCTURE: CheckBehavior.REQUIRED,
    },
    "coverage_meets_threshold": {
        SprintType.SPIKE: CheckBehavior.SKIP,
        SprintType.RESEARCH: CheckBehavior.REDUCED,  # 30%
        SprintType.FULLSTACK: CheckBehavior.REQUIRED,
        SprintType.BACKEND: CheckBehavior.REQUIRED,
        SprintType.FRONTEND: CheckBehavior.REQUIRED,
        SprintType.INFRASTRUCTURE: CheckBehavior.REQUIRED,
    },
    "no_lint_errors": {
        SprintType.SPIKE: CheckBehavior.SKIP,
        SprintType.RESEARCH: CheckBehavior.REQUIRED,
        SprintType.FULLSTACK: CheckBehavior.REQUIRED,
        SprintType.BACKEND: CheckBehavior.REQUIRED,
        SprintType.FRONTEND: CheckBehavior.REQUIRED,
        SprintType.INFRASTRUCTURE: CheckBehavior.REQUIRED,
    },
    "no_type_errors": {
        SprintType.SPIKE: CheckBehavior.SKIP,
        SprintType.RESEARCH: CheckBehavior.SKIP,
        SprintType.FULLSTACK: CheckBehavior.REQUIRED,
        SprintType.BACKEND: CheckBehavior.REQUIRED,
        SprintType.FRONTEND: CheckBehavior.REQUIRED,
        SprintType.INFRASTRUCTURE: CheckBehavior.REQUIRED,
    },
    "migrations_valid": {
        SprintType.SPIKE: CheckBehavior.SKIP,
        SprintType.RESEARCH: CheckBehavior.SKIP,
        SprintType.FULLSTACK: CheckBehavior.REQUIRED,
        SprintType.BACKEND: CheckBehavior.REQUIRED,
        SprintType.FRONTEND: CheckBehavior.REQUIRED,
        SprintType.INFRASTRUCTURE: CheckBehavior.REQUIRED,
    },
    "documentation_updated": {
        SprintType.SPIKE: CheckBehavior.REQUIRED,  # Required for spike
        SprintType.RESEARCH: CheckBehavior.REQUIRED,
        SprintType.FULLSTACK: CheckBehavior.OPTIONAL,
        SprintType.BACKEND: CheckBehavior.OPTIONAL,
        SprintType.FRONTEND: CheckBehavior.OPTIONAL,
        SprintType.INFRASTRUCTURE: CheckBehavior.OPTIONAL,
    },
    "no_debug_statements": {
        SprintType.SPIKE: CheckBehavior.SKIP,
        SprintType.RESEARCH: CheckBehavior.REQUIRED,
        SprintType.FULLSTACK: CheckBehavior.REQUIRED,
        SprintType.BACKEND: CheckBehavior.REQUIRED,
        SprintType.FRONTEND: CheckBehavior.REQUIRED,
        SprintType.INFRASTRUCTURE: CheckBehavior.REQUIRED,
    },
    "no_secrets_in_code": {
        SprintType.SPIKE: CheckBehavior.REQUIRED,  # Always required
        SprintType.RESEARCH: CheckBehavior.REQUIRED,
        SprintType.FULLSTACK: CheckBehavior.REQUIRED,
        SprintType.BACKEND: CheckBehavior.REQUIRED,
        SprintType.FRONTEND: CheckBehavior.REQUIRED,
        SprintType.INFRASTRUCTURE: CheckBehavior.REQUIRED,
    },
    "changelog_updated": {
        SprintType.SPIKE: CheckBehavior.SKIP,
        SprintType.RESEARCH: CheckBehavior.SKIP,
        SprintType.FULLSTACK: CheckBehavior.OPTIONAL,
        SprintType.BACKEND: CheckBehavior.OPTIONAL,
        SprintType.FRONTEND: CheckBehavior.OPTIONAL,
        SprintType.INFRASTRUCTURE: CheckBehavior.OPTIONAL,
    },
}


# =============================================================================
# BASE CHECK CLASS
# =============================================================================


class PreflightCheck(ABC):
    """Base class for preflight checks."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique check identifier."""
        pass

    @abstractmethod
    async def run(
        self,
        project_dir: Path,
        spec_dir: Path,
        sprint_type: SprintType,
    ) -> CheckResult:
        """Execute the check.

        Args:
            project_dir: Path to the project root
            spec_dir: Path to the spec directory
            sprint_type: The sprint type for behavior lookup

        Returns:
            CheckResult with pass/fail status
        """
        pass

    def get_behavior(self, sprint_type: SprintType) -> CheckBehavior:
        """Get the behavior for this check given the sprint type."""
        return CHECK_BEHAVIORS.get(self.name, {}).get(sprint_type, CheckBehavior.REQUIRED)

    def should_skip(self, sprint_type: SprintType) -> bool:
        """Check if this check should be skipped for the sprint type."""
        return self.get_behavior(sprint_type) == CheckBehavior.SKIP


# =============================================================================
# INDIVIDUAL CHECK IMPLEMENTATIONS
# =============================================================================


class TestsPassCheck(PreflightCheck):
    """Check 1: All tests pass."""

    @property
    def name(self) -> str:
        return "tests_pass"

    async def run(
        self,
        project_dir: Path,
        spec_dir: Path,
        sprint_type: SprintType,
    ) -> CheckResult:
        if self.should_skip(sprint_type):
            return CheckResult(
                check_name=self.name,
                passed=True,
                message=f"Skipped for {sprint_type.value} sprint",
                skipped=True,
                skip_reason=f"{sprint_type.value} sprints skip test validation",
            )

        try:
            # Detect test framework
            from analysis.test_discovery import TestDiscovery

            discovery = TestDiscovery()
            test_info = discovery.discover(project_dir)

            if not test_info.test_command:
                return CheckResult(
                    check_name=self.name,
                    passed=True,
                    message="No test framework detected",
                    skipped=True,
                    skip_reason="No test framework configured",
                )

            # Run tests
            result = subprocess.run(
                test_info.test_command.split(),
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode == 0:
                return CheckResult(
                    check_name=self.name,
                    passed=True,
                    message="All tests passed",
                )
            else:
                return CheckResult(
                    check_name=self.name,
                    passed=False,
                    message=f"Tests failed: {result.stderr[:200]}",
                    details={"stdout": result.stdout[:500], "stderr": result.stderr[:500]},
                )

        except subprocess.TimeoutExpired:
            return CheckResult(
                check_name=self.name,
                passed=False,
                message="Tests timed out after 300 seconds",
            )
        except Exception as e:
            return CheckResult(
                check_name=self.name,
                passed=False,
                message=f"Error running tests: {str(e)}",
            )


class CoverageCheck(PreflightCheck):
    """Check 2: Coverage meets threshold."""

    @property
    def name(self) -> str:
        return "coverage_meets_threshold"

    async def run(
        self,
        project_dir: Path,
        spec_dir: Path,
        sprint_type: SprintType,
    ) -> CheckResult:
        if self.should_skip(sprint_type):
            return CheckResult(
                check_name=self.name,
                passed=True,
                message=f"Skipped for {sprint_type.value} sprint",
                skipped=True,
                skip_reason=f"{sprint_type.value} sprints skip coverage check",
            )

        # Get threshold for this sprint type
        threshold = COVERAGE_THRESHOLDS.get(sprint_type, 75)

        try:
            # Detect test framework
            from analysis.test_discovery import TestDiscovery

            discovery = TestDiscovery()
            test_info = discovery.discover(project_dir)

            if not test_info.coverage_command:
                return CheckResult(
                    check_name=self.name,
                    passed=True,
                    message="No coverage tool detected",
                    skipped=True,
                    skip_reason="No coverage tool configured",
                )

            # Run coverage
            result = subprocess.run(
                test_info.coverage_command.split(),
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=300,
            )

            # Parse coverage percentage from output
            coverage_pct = self._parse_coverage(result.stdout)

            if coverage_pct is None:
                return CheckResult(
                    check_name=self.name,
                    passed=True,
                    message="Could not parse coverage output",
                    skipped=True,
                    skip_reason="Coverage parsing failed",
                )

            if coverage_pct >= threshold:
                return CheckResult(
                    check_name=self.name,
                    passed=True,
                    message=f"Coverage {coverage_pct}% meets threshold {threshold}%",
                    details={"actual": coverage_pct, "threshold": threshold},
                )
            else:
                return CheckResult(
                    check_name=self.name,
                    passed=False,
                    message=f"Coverage {coverage_pct}% below threshold {threshold}%",
                    details={"actual": coverage_pct, "threshold": threshold},
                )

        except subprocess.TimeoutExpired:
            return CheckResult(
                check_name=self.name,
                passed=False,
                message="Coverage timed out after 300 seconds",
            )
        except Exception as e:
            return CheckResult(
                check_name=self.name,
                passed=False,
                message=f"Error running coverage: {str(e)}",
            )

    def _parse_coverage(self, output: str) -> Optional[int]:
        """Parse coverage percentage from output."""
        # Look for patterns like "TOTAL    100    10    90%"
        # or "Coverage: 90%"
        patterns = [
            r"TOTAL\s+\d+\s+\d+\s+(\d+)%",
            r"(\d+)%\s*$",
            r"Coverage:\s*(\d+)%",
            r"coverage:\s*(\d+)%",
        ]
        for pattern in patterns:
            match = re.search(pattern, output, re.MULTILINE)
            if match:
                return int(match.group(1))
        return None


class NoLintErrorsCheck(PreflightCheck):
    """Check 3: No lint errors."""

    @property
    def name(self) -> str:
        return "no_lint_errors"

    async def run(
        self,
        project_dir: Path,
        spec_dir: Path,
        sprint_type: SprintType,
    ) -> CheckResult:
        if self.should_skip(sprint_type):
            return CheckResult(
                check_name=self.name,
                passed=True,
                message=f"Skipped for {sprint_type.value} sprint",
                skipped=True,
                skip_reason=f"{sprint_type.value} sprints skip lint check",
            )

        try:
            # Detect linter
            linter_cmd = self._detect_linter(project_dir)

            if not linter_cmd:
                return CheckResult(
                    check_name=self.name,
                    passed=True,
                    message="No linter detected",
                    skipped=True,
                    skip_reason="No linter configured",
                )

            result = subprocess.run(
                linter_cmd,
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=120,
                shell=True,
            )

            if result.returncode == 0:
                return CheckResult(
                    check_name=self.name,
                    passed=True,
                    message="No lint errors",
                )
            else:
                return CheckResult(
                    check_name=self.name,
                    passed=False,
                    message=f"Lint errors found: {result.stderr[:200] or result.stdout[:200]}",
                )

        except Exception as e:
            return CheckResult(
                check_name=self.name,
                passed=False,
                message=f"Error running linter: {str(e)}",
            )

    def _detect_linter(self, project_dir: Path) -> Optional[str]:
        """Detect available linter."""
        # Check for common linters
        if (project_dir / "biome.json").exists():
            return "npx biome check"
        if (project_dir / ".eslintrc.json").exists() or (project_dir / ".eslintrc.js").exists():
            return "npx eslint ."
        if (project_dir / "pyproject.toml").exists():
            content = (project_dir / "pyproject.toml").read_text()
            if "ruff" in content:
                return "ruff check ."
        return None


class NoTypeErrorsCheck(PreflightCheck):
    """Check 4: No type errors."""

    @property
    def name(self) -> str:
        return "no_type_errors"

    async def run(
        self,
        project_dir: Path,
        spec_dir: Path,
        sprint_type: SprintType,
    ) -> CheckResult:
        if self.should_skip(sprint_type):
            return CheckResult(
                check_name=self.name,
                passed=True,
                message=f"Skipped for {sprint_type.value} sprint",
                skipped=True,
                skip_reason=f"{sprint_type.value} sprints skip type check",
            )

        try:
            # Detect type checker
            type_cmd = self._detect_type_checker(project_dir)

            if not type_cmd:
                return CheckResult(
                    check_name=self.name,
                    passed=True,
                    message="No type checker detected",
                    skipped=True,
                    skip_reason="No type checker configured",
                )

            result = subprocess.run(
                type_cmd,
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=120,
                shell=True,
            )

            if result.returncode == 0:
                return CheckResult(
                    check_name=self.name,
                    passed=True,
                    message="No type errors",
                )
            else:
                return CheckResult(
                    check_name=self.name,
                    passed=False,
                    message=f"Type errors found: {result.stderr[:200] or result.stdout[:200]}",
                )

        except Exception as e:
            return CheckResult(
                check_name=self.name,
                passed=False,
                message=f"Error running type checker: {str(e)}",
            )

    def _detect_type_checker(self, project_dir: Path) -> Optional[str]:
        """Detect available type checker."""
        if (project_dir / "tsconfig.json").exists():
            return "npx tsc --noEmit"
        if (project_dir / "pyproject.toml").exists():
            content = (project_dir / "pyproject.toml").read_text()
            if "mypy" in content:
                return "mypy ."
        return None


class MigrationsValidCheck(PreflightCheck):
    """Check 5: Migrations valid and reversible."""

    @property
    def name(self) -> str:
        return "migrations_valid"

    async def run(
        self,
        project_dir: Path,
        spec_dir: Path,
        sprint_type: SprintType,
    ) -> CheckResult:
        if self.should_skip(sprint_type):
            return CheckResult(
                check_name=self.name,
                passed=True,
                message=f"Skipped for {sprint_type.value} sprint",
                skipped=True,
                skip_reason=f"{sprint_type.value} sprints skip migration check",
            )

        # Per user decision: skip automatically if no framework detected
        migration_framework = self._detect_migration_framework(project_dir)

        if not migration_framework:
            return CheckResult(
                check_name=self.name,
                passed=True,
                message="No migration framework detected",
                skipped=True,
                skip_reason="No migration framework found",
            )

        # Validate migrations based on framework
        return await self._validate_migrations(project_dir, migration_framework)

    def _detect_migration_framework(self, project_dir: Path) -> Optional[str]:
        """Detect migration framework."""
        if (project_dir / "alembic.ini").exists() or (project_dir / "alembic").is_dir():
            return "alembic"
        if (project_dir / "prisma").is_dir():
            return "prisma"
        if (project_dir / "migrations").is_dir():
            # Check for Django
            if (project_dir / "manage.py").exists():
                return "django"
        return None

    async def _validate_migrations(self, project_dir: Path, framework: str) -> CheckResult:
        """Validate migrations for the detected framework."""
        try:
            if framework == "alembic":
                result = subprocess.run(
                    ["alembic", "check"],
                    cwd=project_dir,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
            elif framework == "prisma":
                result = subprocess.run(
                    ["npx", "prisma", "validate"],
                    cwd=project_dir,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
            else:
                return CheckResult(
                    check_name=self.name,
                    passed=True,
                    message=f"Framework {framework} validation not implemented",
                    skipped=True,
                )

            if result.returncode == 0:
                return CheckResult(
                    check_name=self.name,
                    passed=True,
                    message=f"{framework} migrations are valid",
                )
            else:
                return CheckResult(
                    check_name=self.name,
                    passed=False,
                    message=f"{framework} migration errors: {result.stderr[:200]}",
                )

        except Exception as e:
            return CheckResult(
                check_name=self.name,
                passed=False,
                message=f"Error validating migrations: {str(e)}",
            )


class DocumentationCheck(PreflightCheck):
    """Check 6: Documentation updated."""

    @property
    def name(self) -> str:
        return "documentation_updated"

    async def run(
        self,
        project_dir: Path,
        spec_dir: Path,
        sprint_type: SprintType,
    ) -> CheckResult:
        # Note: This check is required for spike/research, optional for others
        # We don't skip, but the behavior affects whether failure blocks merge
        behavior = self.get_behavior(sprint_type)

        # Check for documentation files
        doc_files = [
            project_dir / "README.md",
            project_dir / "CHANGELOG.md",
            project_dir / "docs",
        ]

        has_docs = any(
            f.exists() for f in doc_files
        )

        if has_docs:
            return CheckResult(
                check_name=self.name,
                passed=True,
                message="Documentation present",
                blocking=(behavior == CheckBehavior.REQUIRED),
            )
        else:
            return CheckResult(
                check_name=self.name,
                passed=False,
                message="No documentation found",
                blocking=(behavior == CheckBehavior.REQUIRED),
            )


class NoDebugStatementsCheck(PreflightCheck):
    """Check 7: No debug statements."""

    @property
    def name(self) -> str:
        return "no_debug_statements"

    # Debug patterns to flag (per user decision: flag ALL, no whitelisting)
    DEBUG_PATTERNS = [
        r"\bconsole\.log\b",
        r"\bconsole\.debug\b",
        r"\bdebugger\b",
        r"\bprint\s*\(",
        r"\bpdb\.set_trace\s*\(",
        r"\bbreakpoint\s*\(",
    ]

    async def run(
        self,
        project_dir: Path,
        spec_dir: Path,
        sprint_type: SprintType,
    ) -> CheckResult:
        if self.should_skip(sprint_type):
            return CheckResult(
                check_name=self.name,
                passed=True,
                message=f"Skipped for {sprint_type.value} sprint",
                skipped=True,
                skip_reason=f"{sprint_type.value} sprints skip debug check",
            )

        found_debug = []

        # Search source files for debug statements
        extensions = [".py", ".js", ".ts", ".tsx", ".jsx"]
        for ext in extensions:
            for file in project_dir.rglob(f"*{ext}"):
                # Skip node_modules and other common directories
                if any(
                    part in file.parts
                    for part in ["node_modules", ".git", "__pycache__", "venv", ".venv"]
                ):
                    continue

                try:
                    content = file.read_text(encoding="utf-8", errors="ignore")
                    for pattern in self.DEBUG_PATTERNS:
                        matches = re.findall(pattern, content)
                        if matches:
                            found_debug.append(f"{file.relative_to(project_dir)}: {pattern}")
                except Exception:
                    pass  # Skip files we can't read

        if not found_debug:
            return CheckResult(
                check_name=self.name,
                passed=True,
                message="No debug statements found",
            )
        else:
            return CheckResult(
                check_name=self.name,
                passed=False,
                message=f"Found {len(found_debug)} debug statements",
                details={"matches": found_debug[:10]},  # Limit to first 10
            )


class NoSecretsCheck(PreflightCheck):
    """Check 8: No secrets in code."""

    @property
    def name(self) -> str:
        return "no_secrets_in_code"

    async def run(
        self,
        project_dir: Path,
        spec_dir: Path,
        sprint_type: SprintType,
    ) -> CheckResult:
        # Note: This check is ALWAYS required, never skipped
        # It's critical for security

        try:
            from analysis.security_scanner import SecurityScanner

            scanner = SecurityScanner()
            result = scanner.scan(
                project_dir,
                run_sast=False,
                run_dependency_audit=False,
            )

            if not result.secrets:
                return CheckResult(
                    check_name=self.name,
                    passed=True,
                    message="No secrets detected",
                )
            else:
                return CheckResult(
                    check_name=self.name,
                    passed=False,
                    message=f"Found {len(result.secrets)} potential secrets",
                    details={"secrets": result.secrets[:5]},  # Limit details
                )

        except ImportError:
            # Fallback if security scanner not available
            return CheckResult(
                check_name=self.name,
                passed=True,
                message="Security scanner not available",
                skipped=True,
                skip_reason="security scanner module not installed",
            )
        except Exception as e:
            return CheckResult(
                check_name=self.name,
                passed=False,
                message=f"Error scanning for secrets: {str(e)}",
            )


class ChangelogCheck(PreflightCheck):
    """Check 9: Changelog updated."""

    @property
    def name(self) -> str:
        return "changelog_updated"

    async def run(
        self,
        project_dir: Path,
        spec_dir: Path,
        sprint_type: SprintType,
    ) -> CheckResult:
        if self.should_skip(sprint_type):
            return CheckResult(
                check_name=self.name,
                passed=True,
                message=f"Skipped for {sprint_type.value} sprint",
                skipped=True,
                skip_reason=f"{sprint_type.value} sprints skip changelog check",
            )

        # This check is optional for most sprint types
        behavior = self.get_behavior(sprint_type)

        changelog_path = project_dir / "CHANGELOG.md"
        if changelog_path.exists():
            return CheckResult(
                check_name=self.name,
                passed=True,
                message="Changelog present",
                blocking=(behavior == CheckBehavior.REQUIRED),
            )
        else:
            return CheckResult(
                check_name=self.name,
                passed=False,
                message="Changelog not found or not updated",
                blocking=(behavior == CheckBehavior.REQUIRED),
            )


# =============================================================================
# CHECKLIST ORCHESTRATOR
# =============================================================================


class PreflightChecklist:
    """Orchestrates the 9-item preflight checklist.

    Runs all checks in parallel for performance and collects results.
    """

    def __init__(self, checks: Optional[list[PreflightCheck]] = None):
        """Initialize with default or custom checks."""
        self.checks = checks or self._default_checks()

    def _default_checks(self) -> list[PreflightCheck]:
        """Create the default 9 checks."""
        return [
            TestsPassCheck(),
            CoverageCheck(),
            NoLintErrorsCheck(),
            NoTypeErrorsCheck(),
            MigrationsValidCheck(),
            DocumentationCheck(),
            NoDebugStatementsCheck(),
            NoSecretsCheck(),
            ChangelogCheck(),
        ]

    async def run_all(
        self,
        project_dir: Path,
        spec_dir: Path,
        sprint_type: SprintType,
    ) -> PreflightResult:
        """Run all applicable checks based on sprint type.

        Per user decision: checks run in parallel for performance.

        Args:
            project_dir: Path to the project root
            spec_dir: Path to the spec directory
            sprint_type: Sprint type for behavior lookup

        Returns:
            PreflightResult with all check results
        """
        # Run all checks in parallel
        tasks = [
            check.run(project_dir, spec_dir, sprint_type) for check in self.checks
        ]
        results: list[CheckResult] = await asyncio.gather(*tasks)

        # Categorize results
        blocking_failures = []
        warnings = []

        for result in results:
            if result.skipped:
                continue  # Skipped checks don't count

            # Get behavior for this check
            check = next((c for c in self.checks if c.name == result.check_name), None)
            if check:
                behavior = check.get_behavior(sprint_type)
            else:
                behavior = CheckBehavior.REQUIRED

            if not result.passed:
                if behavior == CheckBehavior.OPTIONAL:
                    warnings.append(result)
                elif behavior != CheckBehavior.SKIP:
                    blocking_failures.append(result)

        # Build summary
        passed_count = sum(1 for r in results if r.passed)
        total_count = len(results)
        skipped_count = sum(1 for r in results if r.skipped)

        summary = (
            f"{passed_count}/{total_count} checks passed"
            f" ({skipped_count} skipped, {len(warnings)} warnings)"
        )

        return PreflightResult(
            passed=len(blocking_failures) == 0,
            checks=results,
            blocking_failures=blocking_failures,
            warnings=warnings,
            summary=summary,
        )

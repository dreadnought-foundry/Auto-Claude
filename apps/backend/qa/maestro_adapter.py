"""Maestro Quality Gate Adapter.

Adapts Maestro's pre-flight checklist for integration with Auto-Claude's
merge pipeline. Provides sprint-type aware quality gate enforcement.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import yaml

from spec.requirements import load_requirements
from spec.types import SprintType, DEFAULT_TYPE

from .preflight_checklist import (
    PreflightChecklist,
    PreflightResult,
    CheckResult,
)


# Default configuration
DEFAULT_CONFIG: dict[str, Any] = {
    "version": "1.0",
    "checks": {
        "tests_pass": {"enabled": True},
        "coverage_meets_threshold": {"enabled": True},
        "no_lint_errors": {"enabled": True},
        "no_type_errors": {"enabled": True},
        "migrations_valid": {"enabled": True},
        "documentation_updated": {"enabled": True},
        "no_debug_statements": {"enabled": True},
        "no_secrets_in_code": {"enabled": True},
        "changelog_updated": {"enabled": True},
    },
    "settings": {
        "block_on_failure": True,
        "allow_skip_with_flag": True,
        "verbose_output": False,
    },
}


class MaestroQualityGate:
    """Adapter that integrates Maestro's pre-flight checklist into Auto-Claude.

    This is the main interface used by the merge pipeline. It:
    1. Detects sprint type from requirements.json
    2. Loads configuration from .auto-claude/maestro.yaml
    3. Runs the pre-flight checklist
    4. Determines if merge should be allowed

    Usage:
        gate = MaestroQualityGate(project_dir, spec_dir)
        result = await gate.run_quality_gate()
        if gate.can_merge(result):
            # proceed with merge
        else:
            print(gate.format_failure_message(result))
    """

    def __init__(
        self,
        project_dir: Path,
        spec_dir: Path,
        config_path: Optional[Path] = None,
    ):
        """Initialize the quality gate.

        Args:
            project_dir: Path to the project root
            spec_dir: Path to the spec directory
            config_path: Optional custom config path (default: .auto-claude/maestro.yaml)
        """
        self.project_dir = Path(project_dir)
        self.spec_dir = Path(spec_dir)

        # Load configuration
        self._config: Optional[dict[str, Any]] = None
        self._config_path = config_path or (self.project_dir / ".auto-claude" / "maestro.yaml")

        # Sprint type (lazy loaded)
        self._sprint_type: Optional[SprintType] = None

        # Checklist runner
        self.checklist = PreflightChecklist()

    @property
    def config(self) -> dict[str, Any]:
        """Get configuration, loading from file if needed."""
        if self._config is None:
            self._config = self._load_config()
        return self._config

    @property
    def sprint_type(self) -> SprintType:
        """Get sprint type from requirements.json or default."""
        if self._sprint_type is None:
            self._sprint_type = self._detect_sprint_type()
        return self._sprint_type

    def _load_config(self) -> dict[str, Any]:
        """Load configuration from file or use defaults."""
        if self._config_path.exists():
            try:
                with open(self._config_path, encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                    if config:
                        # Merge with defaults to ensure all keys exist
                        return self._merge_config(DEFAULT_CONFIG, config)
            except Exception:
                pass  # Fall back to defaults

        return DEFAULT_CONFIG.copy()

    def _merge_config(self, base: dict, override: dict) -> dict:
        """Deep merge override into base config."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        return result

    def _detect_sprint_type(self) -> SprintType:
        """Detect sprint type from requirements.json."""
        reqs = load_requirements(self.spec_dir)

        if reqs and reqs.get("sprint_type"):
            try:
                return SprintType(reqs["sprint_type"])
            except ValueError:
                pass  # Invalid type, use default

        return DEFAULT_TYPE

    async def run_quality_gate(self) -> PreflightResult:
        """Execute the quality gate checks.

        Runs all 9 pre-flight checks based on the detected sprint type.

        Returns:
            PreflightResult with all check results
        """
        return await self.checklist.run_all(
            project_dir=self.project_dir,
            spec_dir=self.spec_dir,
            sprint_type=self.sprint_type,
        )

    def can_merge(self, result: PreflightResult) -> bool:
        """Determine if merge should be allowed based on results.

        Args:
            result: Result from run_quality_gate()

        Returns:
            True if merge should proceed, False if blocked
        """
        # Check if blocking is disabled in config
        if not self.config.get("settings", {}).get("block_on_failure", True):
            return True

        # Allow if passed or no blocking failures
        return result.passed or len(result.blocking_failures) == 0

    def format_failure_message(self, result: PreflightResult) -> str:
        """Format a user-friendly error message for blocked merges.

        Args:
            result: Result from run_quality_gate()

        Returns:
            Formatted error message string
        """
        lines = []
        lines.append("")
        lines.append("=" * 70)
        lines.append("  QUALITY GATE FAILED - Merge Blocked")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"Sprint Type: {self.sprint_type.value}")
        lines.append(f"Summary: {result.summary}")
        lines.append("")

        if result.blocking_failures:
            lines.append("BLOCKING FAILURES:")
            lines.append("-" * 40)
            for failure in result.blocking_failures:
                lines.append(f"  ✗ {failure.check_name}")
                lines.append(f"    {failure.message}")
                if failure.details:
                    for key, value in failure.details.items():
                        if isinstance(value, list):
                            lines.append(f"    {key}:")
                            for item in value[:5]:  # Limit items shown
                                lines.append(f"      - {item}")
                        else:
                            lines.append(f"    {key}: {value}")
                lines.append("")

        if result.warnings:
            lines.append("WARNINGS (non-blocking):")
            lines.append("-" * 40)
            for warning in result.warnings:
                lines.append(f"  ⚠ {warning.check_name}: {warning.message}")
            lines.append("")

        lines.append("=" * 70)
        lines.append("Fix the blocking failures above before merging.")
        lines.append("Use --skip-quality-gate to bypass (not recommended).")
        lines.append("=" * 70)
        lines.append("")

        return "\n".join(lines)

    def format_success_message(self, result: PreflightResult) -> str:
        """Format a success message when gate passes.

        Args:
            result: Result from run_quality_gate()

        Returns:
            Formatted success message string
        """
        lines = []
        lines.append("")
        lines.append("✓ Quality gate passed")
        lines.append(f"  {result.summary}")

        if result.warnings:
            lines.append(f"  ⚠ {len(result.warnings)} warnings (non-blocking)")

        return "\n".join(lines)


def run_quality_gate_sync(
    project_dir: Path,
    spec_dir: Path,
) -> tuple[bool, str]:
    """Synchronous wrapper for running the quality gate.

    Convenience function for integration with synchronous code paths.

    Args:
        project_dir: Path to the project root
        spec_dir: Path to the spec directory

    Returns:
        Tuple of (can_merge: bool, message: str)
    """
    import asyncio

    gate = MaestroQualityGate(project_dir, spec_dir)

    # Run the async gate
    result = asyncio.run(gate.run_quality_gate())

    can_merge = gate.can_merge(result)
    if can_merge:
        message = gate.format_success_message(result)
    else:
        message = gate.format_failure_message(result)

    return can_merge, message

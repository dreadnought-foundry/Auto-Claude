"""
Postmortem Generator
====================

Generates Maestro-format postmortem reports after spec completion.
Aggregates metrics, patterns, and learnings into a structured report.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agents.metrics import ExecutionMetrics, collect_execution_metrics
from analysis.patterns import PatternExtractor, extract_patterns


@dataclass
class PostmortemData:
    """All data needed to generate a postmortem."""

    metrics: ExecutionMetrics
    agent_contributions: list[dict[str, Any]] = field(default_factory=list)
    what_went_well: list[str] = field(default_factory=list)
    what_could_improve: list[str] = field(default_factory=list)
    patterns_discovered: list[dict[str, Any]] = field(default_factory=list)
    learnings: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)


class PostmortemGenerator:
    """Generates postmortem reports for completed specs."""

    def __init__(self, project_dir: Path, spec_dir: Path):
        """
        Initialize the postmortem generator.

        Args:
            project_dir: Project root directory
            spec_dir: Spec directory for the completed build
        """
        self.project_dir = Path(project_dir)
        self.spec_dir = Path(spec_dir)
        self.sprint_type = self._detect_sprint_type()

    def _detect_sprint_type(self) -> str:
        """Detect sprint type from spec."""
        plan_file = self.spec_dir / "implementation_plan.json"
        if plan_file.exists():
            try:
                plan = json.loads(plan_file.read_text())
                return plan.get("workflow_type", "fullstack")
            except (json.JSONDecodeError, OSError):
                pass

        # Try requirements.json
        req_file = self.spec_dir / "requirements.json"
        if req_file.exists():
            try:
                req = json.loads(req_file.read_text())
                return req.get("sprint_type", "fullstack")
            except (json.JSONDecodeError, OSError):
                pass

        return "fullstack"

    def collect_metrics(self) -> ExecutionMetrics:
        """
        Collect execution metrics from the spec.

        Returns:
            ExecutionMetrics with aggregated data
        """
        return collect_execution_metrics(self.spec_dir, self.project_dir)

    def collect_agent_contributions(self) -> list[dict[str, Any]]:
        """
        Collect per-agent contribution data.

        Returns:
            List of agent contribution dicts
        """
        contributions = []

        # Load attempt history to get agent data
        memory_dir = self.spec_dir / "memory"
        attempt_file = memory_dir / "attempt_history.json"

        if attempt_file.exists():
            try:
                data = json.loads(attempt_file.read_text())
                attempts = data.get("attempts", [])

                # Group by agent type
                agent_data: dict[str, dict] = {}
                for attempt in attempts:
                    agent = attempt.get("agent_type", "unknown")
                    if agent not in agent_data:
                        agent_data[agent] = {
                            "tasks": 0,
                            "files": [],
                            "duration": 0,
                        }
                    agent_data[agent]["tasks"] += 1

                # Format as contribution records
                for agent, data in agent_data.items():
                    contributions.append(
                        {
                            "agent": agent.replace("_", " ").title(),
                            "tasks": data["tasks"],
                            "files": f"{len(data['files'])} files",
                            "time": "N/A",
                        }
                    )

            except (json.JSONDecodeError, OSError):
                pass

        return contributions

    def analyze_what_went_well(self) -> list[str]:
        """
        Analyze and generate 'what went well' items.

        Returns:
            List of success items
        """
        successes = []
        metrics = self.collect_metrics()

        # Success: All subtasks completed
        if metrics.total_subtasks > 0 and metrics.completed_subtasks == metrics.total_subtasks:
            successes.append(
                f"All {metrics.total_subtasks} subtasks completed successfully"
            )

        # Success: No rework cycles
        if metrics.rework_cycles == 0:
            successes.append("Build passed QA on first iteration")
        elif metrics.rework_cycles == 1:
            successes.append("Build completed with minimal rework")

        # Success: Coverage improved
        if metrics.coverage_delta > 0:
            successes.append(f"Test coverage improved by {metrics.coverage_delta}%")

        # Extract from insights
        pattern_data = extract_patterns(self.spec_dir, self.project_dir)
        successes.extend(pattern_data.get("what_worked", []))

        # Ensure at least one item
        if not successes:
            successes.append("Build completed successfully")

        return successes

    def analyze_what_could_improve(self) -> list[str]:
        """
        Analyze and generate improvement suggestions.

        Returns:
            List of improvement items
        """
        improvements = []
        metrics = self.collect_metrics()

        # Improvement: Had rework cycles
        if metrics.rework_cycles >= 1:
            improvements.append(
                f"Required {metrics.rework_cycles + 1} QA iterations - "
                "consider more upfront testing"
            )

        # Improvement: Low coverage delta
        if metrics.coverage_delta < 0:
            improvements.append(
                f"Test coverage decreased by {abs(metrics.coverage_delta)}%"
            )

        # Extract from insights
        pattern_data = extract_patterns(self.spec_dir, self.project_dir)
        improvements.extend(pattern_data.get("what_didnt_work", []))

        return improvements

    def collect_patterns(self) -> list[dict[str, Any]]:
        """
        Collect discovered patterns.

        Returns:
            List of pattern dicts
        """
        pattern_data = extract_patterns(self.spec_dir, self.project_dir)
        return pattern_data.get("patterns", [])

    def generate_learnings(self) -> list[str]:
        """
        Generate learnings from the build.

        Returns:
            List of learning strings
        """
        pattern_data = extract_patterns(self.spec_dir, self.project_dir)
        learnings = pattern_data.get("learnings", [])

        # Add generated learnings based on metrics
        metrics = self.collect_metrics()
        if metrics.rework_cycles > 0 and metrics.rework_cycles <= 2:
            learnings.append(
                "**Process**: QA review catches issues early - continue test-first approach"
            )

        return learnings

    def generate_action_items(self) -> list[str]:
        """
        Generate action items for follow-up.

        Returns:
            List of action item strings
        """
        pattern_data = extract_patterns(self.spec_dir, self.project_dir)
        return pattern_data.get("action_items", [])

    def generate(self) -> PostmortemData:
        """
        Generate complete postmortem data.

        Returns:
            PostmortemData with all sections populated
        """
        return PostmortemData(
            metrics=self.collect_metrics(),
            agent_contributions=self.collect_agent_contributions(),
            what_went_well=self.analyze_what_went_well(),
            what_could_improve=self.analyze_what_could_improve(),
            patterns_discovered=self.collect_patterns(),
            learnings=self.generate_learnings(),
            action_items=self.generate_action_items(),
        )


async def generate_postmortem(project_dir: Path, spec_dir: Path) -> PostmortemData:
    """
    Async entry point for postmortem generation.

    Args:
        project_dir: Project root directory
        spec_dir: Spec directory

    Returns:
        PostmortemData with all sections populated
    """
    generator = PostmortemGenerator(project_dir, spec_dir)
    return generator.generate()

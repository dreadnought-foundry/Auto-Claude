"""
Pattern Extraction
==================

Extracts reusable patterns from completed builds for postmortem reports
and future reference. Analyzes code changes, session insights, and
approach outcomes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PatternDiscovery:
    """A reusable pattern discovered during the build."""

    pattern_type: str  # code_pattern, architecture, testing, library, config
    description: str
    files: list[str] = field(default_factory=list)
    frequency: int = 1
    reusable: bool = True
    tags: list[str] = field(default_factory=list)


@dataclass
class ApproachOutcome:
    """What worked vs what didn't during the build."""

    approach: str
    worked: bool
    context: str
    alternative_tried: str | None = None


class PatternExtractor:
    """Extracts patterns from build execution."""

    def __init__(self, spec_dir: Path, project_dir: Path):
        """
        Initialize the pattern extractor.

        Args:
            spec_dir: Spec directory with session insights
            project_dir: Project root directory
        """
        self.spec_dir = Path(spec_dir)
        self.project_dir = Path(project_dir)

    def _load_insights(self) -> list[dict[str, Any]]:
        """Load all session insight files."""
        insights = []
        memory_dir = self.spec_dir / "memory"

        if not memory_dir.exists():
            return insights

        for insight_file in memory_dir.glob("session_insights_*.json"):
            try:
                data = json.loads(insight_file.read_text())
                insights.append(data)
            except (json.JSONDecodeError, OSError):
                continue

        return insights

    def extract_code_patterns(self) -> list[PatternDiscovery]:
        """
        Extract code patterns from session insights.

        Returns:
            List of discovered patterns
        """
        patterns = []
        insights = self._load_insights()

        for insight in insights:
            # Extract patterns_used from insight
            patterns_used = insight.get("patterns_used", [])
            for p in patterns_used:
                if isinstance(p, dict):
                    pattern = PatternDiscovery(
                        pattern_type="code_pattern",
                        description=p.get("name", "Unknown pattern"),
                        files=p.get("files", []),
                        reusable=True,
                    )
                    patterns.append(pattern)
                elif isinstance(p, str):
                    pattern = PatternDiscovery(
                        pattern_type="code_pattern",
                        description=p,
                        reusable=True,
                    )
                    patterns.append(pattern)

        return patterns

    def extract_approach_outcomes(
        self,
    ) -> tuple[list[ApproachOutcome], list[ApproachOutcome]]:
        """
        Extract what approaches worked vs didn't work.

        Returns:
            Tuple of (worked_list, didnt_work_list)
        """
        worked = []
        didnt_work = []
        insights = self._load_insights()

        for insight in insights:
            # Extract what_worked
            for item in insight.get("what_worked", []):
                outcome = ApproachOutcome(
                    approach=item if isinstance(item, str) else str(item),
                    worked=True,
                    context="Session insight",
                )
                worked.append(outcome)

            # Extract what_didnt_work
            for item in insight.get("what_didnt_work", []):
                outcome = ApproachOutcome(
                    approach=item if isinstance(item, str) else str(item),
                    worked=False,
                    context="Session insight",
                )
                didnt_work.append(outcome)

        return worked, didnt_work

    def extract_learnings(self) -> list[str]:
        """
        Generate learnings from session insights.

        Returns:
            List of learning strings
        """
        learnings = []
        insights = self._load_insights()

        for insight in insights:
            for learning in insight.get("learnings", []):
                if isinstance(learning, str) and learning not in learnings:
                    learnings.append(learning)

        return learnings

    def generate_action_items(self) -> list[str]:
        """
        Generate action items based on patterns and outcomes.

        Returns:
            List of suggested action items
        """
        action_items = []
        insights = self._load_insights()

        for insight in insights:
            # Action items from insights
            for action in insight.get("action_items", []):
                if isinstance(action, str) and action not in action_items:
                    action_items.append(action)

            # Generate action items from what didn't work
            for item in insight.get("what_didnt_work", []):
                if isinstance(item, str):
                    action = f"Review: {item}"
                    if action not in action_items:
                        action_items.append(action)

        return action_items


def extract_patterns(spec_dir: Path, project_dir: Path) -> dict[str, Any]:
    """
    Main entry point for pattern extraction.

    Args:
        spec_dir: Spec directory
        project_dir: Project root directory

    Returns:
        Dict with patterns, what_worked, what_didnt_work, learnings
    """
    extractor = PatternExtractor(spec_dir, project_dir)

    patterns = extractor.extract_code_patterns()
    worked, didnt_work = extractor.extract_approach_outcomes()
    learnings = extractor.extract_learnings()
    action_items = extractor.generate_action_items()

    return {
        "patterns": [
            {
                "type": p.pattern_type,
                "description": p.description,
                "files": p.files,
                "reusable": p.reusable,
            }
            for p in patterns
        ],
        "what_worked": [o.approach for o in worked],
        "what_didnt_work": [o.approach for o in didnt_work],
        "learnings": learnings,
        "action_items": action_items,
    }

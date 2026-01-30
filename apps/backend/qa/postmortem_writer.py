"""
Postmortem Markdown Writer
==========================

Renders PostmortemData to Maestro-compatible Markdown format.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .postmortem import PostmortemData


def _format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds <= 0:
        return "N/A"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)

    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m"
    else:
        return f"{int(seconds)}s"


class PostmortemWriter:
    """Writes postmortem reports in Markdown format."""

    def __init__(self, data: PostmortemData, spec_name: str):
        """
        Initialize the postmortem writer.

        Args:
            data: PostmortemData to render
            spec_name: Name of the spec for the title
        """
        self.data = data
        self.spec_name = spec_name

    def _format_summary_table(self) -> str:
        """Format the summary metrics table."""
        metrics = self.data.metrics
        duration = _format_duration(metrics.duration_seconds)

        # Format timestamps
        started = metrics.started_at if metrics.started_at else "N/A"
        completed = metrics.completed_at if metrics.completed_at else "N/A"

        # Format coverage delta
        if metrics.coverage_delta > 0:
            coverage = f"+{metrics.coverage_delta}%"
        elif metrics.coverage_delta < 0:
            coverage = f"{metrics.coverage_delta}%"
        else:
            coverage = "N/A"

        lines = [
            "| Metric | Value |",
            "|--------|-------|",
            f"| Started | {started} |",
            f"| Completed | {completed} |",
            f"| Duration | {duration} |",
            f"| Tests Added | {metrics.tests_added} |",
            f"| Coverage Delta | {coverage} |",
            f"| Files Changed | {metrics.files_changed} |",
            f"| Agents Used | {len(metrics.agents_used)} |",
            f"| Rework Cycles | {metrics.rework_cycles} |",
        ]

        return "\n".join(lines)

    def _format_agent_contributions(self) -> str:
        """Format the agent contributions table."""
        if not self.data.agent_contributions:
            return "_No agent contribution data available._"

        lines = [
            "| Agent | Tasks | Files Created/Modified | Time |",
            "|-------|-------|------------------------|------|",
        ]

        for contrib in self.data.agent_contributions:
            agent = contrib.get("agent", "Unknown")
            tasks = contrib.get("tasks", 0)
            files = contrib.get("files", "N/A")
            time = contrib.get("time", "N/A")
            lines.append(f"| {agent} | {tasks} | {files} | {time} |")

        return "\n".join(lines)

    def _format_list_section(self, items: list[str | dict[str, Any]]) -> str:
        """Format a bulleted list section."""
        if not items:
            return "_None identified._"

        lines = []
        for item in items:
            if isinstance(item, dict):
                # Pattern or complex item
                desc = item.get("description", str(item))
                lines.append(f"- {desc}")
            else:
                lines.append(f"- {item}")

        return "\n".join(lines)

    def _format_patterns(self) -> str:
        """Format the patterns discovered section."""
        if not self.data.patterns_discovered:
            return "_No patterns identified._"

        lines = []
        for pattern in self.data.patterns_discovered:
            if isinstance(pattern, dict):
                ptype = pattern.get("type", "pattern")
                desc = pattern.get("description", "Unknown pattern")
                lines.append(f"- **{ptype}**: {desc}")
            else:
                lines.append(f"- {pattern}")

        return "\n".join(lines)

    def _format_learnings(self) -> str:
        """Format the learnings section."""
        if not self.data.learnings:
            return "_No learnings captured._"

        lines = []
        for i, learning in enumerate(self.data.learnings, 1):
            lines.append(f"{i}. {learning}")

        return "\n".join(lines)

    def _format_action_items(self) -> str:
        """Format the action items section."""
        if not self.data.action_items:
            return "_No action items._"

        lines = []
        for item in self.data.action_items:
            lines.append(f"- [ ] {item}")

        return "\n".join(lines)

    def render(self) -> str:
        """
        Render the postmortem to Markdown.

        Returns:
            Complete Markdown string
        """
        sections = [
            f"## Sprint Postmortem: {self.spec_name}",
            "",
            "### Summary",
            "",
            self._format_summary_table(),
            "",
            "### Agent Contributions",
            "",
            self._format_agent_contributions(),
            "",
            "### What Went Well",
            "",
            self._format_list_section(self.data.what_went_well),
            "",
            "### What Could Improve",
            "",
            self._format_list_section(self.data.what_could_improve),
            "",
            "### Patterns Discovered",
            "",
            self._format_patterns(),
            "",
            "### Learnings",
            "",
            self._format_learnings(),
            "",
            "### Action Items",
            "",
            self._format_action_items(),
        ]

        return "\n".join(sections)

    def write(self, output_path: Path) -> Path:
        """
        Write the postmortem to a file.

        Args:
            output_path: Path to write the Markdown file

        Returns:
            Path to the written file
        """
        output_path = Path(output_path)
        output_path.write_text(self.render())
        return output_path


def write_postmortem(
    data: PostmortemData,
    spec_dir: Path,
    spec_name: str,
) -> Path:
    """
    Write postmortem to spec directory.

    Args:
        data: PostmortemData to write
        spec_dir: Spec directory to write to
        spec_name: Name of the spec

    Returns:
        Path to the written file
    """
    spec_dir = Path(spec_dir)
    output_path = spec_dir / f"{spec_name}_postmortem.md"

    writer = PostmortemWriter(data, spec_name)
    return writer.write(output_path)

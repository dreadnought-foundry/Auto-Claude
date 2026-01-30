"""
Epic Management Module
======================

Manages epic metadata, lifecycle, and spec associations.
Epics are OPTIONAL - specs work without epics.

Epics group related specs into strategic initiatives, with:
- Success criteria tracking
- Auto-completion detection when all specs done
- Human-readable markdown storage
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
import json


class EpicStatus(str, Enum):
    """Epic status values."""

    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


@dataclass
class SuccessCriterion:
    """A single success criterion for an epic."""

    description: str
    completed: bool = False
    completed_at: Optional[str] = None


@dataclass
class EpicSpec:
    """Reference to a spec within an epic."""

    spec_number: int
    title: str
    status: str = "pending"  # pending, in_progress, done


@dataclass
class Epic:
    """
    Represents an Epic - a high-level organizational unit for related specs.

    Epics are stored as markdown files in .auto-claude/epics/.
    """

    number: int
    title: str
    description: str
    status: EpicStatus = EpicStatus.ACTIVE
    success_criteria: list[SuccessCriterion] = field(default_factory=list)
    specs: list[EpicSpec] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None

    @property
    def folder_name(self) -> str:
        """Get the folder-safe name for this epic."""
        return f"{self.number:03d}-{self._slugify(self.title)}"

    @property
    def file_path(self) -> str:
        """Get the filename for this epic."""
        return f"{self.folder_name}.md"

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert text to kebab-case slug."""
        # Convert to lowercase
        slug = text.lower()
        # Replace spaces and underscores with hyphens
        slug = re.sub(r"[\s_]+", "-", slug)
        # Remove special characters
        slug = re.sub(r"[^a-z0-9-]", "", slug)
        # Remove multiple consecutive hyphens
        slug = re.sub(r"-+", "-", slug)
        # Remove leading/trailing hyphens
        slug = slug.strip("-")
        return slug or "unnamed"

    def add_spec(self, spec_number: int, title: str, status: str = "pending") -> None:
        """Add a spec to this epic."""
        self.specs.append(EpicSpec(spec_number=spec_number, title=title, status=status))

    def update_spec_status(self, spec_number: int, status: str) -> bool:
        """Update a spec's status within this epic."""
        for spec in self.specs:
            if spec.spec_number == spec_number:
                spec.status = status
                return True
        return False

    def remove_spec(self, spec_number: int) -> bool:
        """Remove a spec from this epic."""
        original_len = len(self.specs)
        self.specs = [s for s in self.specs if s.spec_number != spec_number]
        return len(self.specs) < original_len

    def check_complete(self) -> bool:
        """
        Check if all specs and success criteria are complete.

        An epic is complete when:
        1. It has at least one spec
        2. All specs have status "done"
        3. All success criteria are marked completed (if any exist)
        """
        if not self.specs:
            return False

        all_specs_done = all(s.status == "done" for s in self.specs)
        all_criteria_met = (
            all(c.completed for c in self.success_criteria)
            if self.success_criteria
            else True
        )
        return all_specs_done and all_criteria_met

    def to_markdown(self) -> str:
        """Serialize epic to markdown format."""
        lines = []

        # Header
        lines.append(f"# Epic {self.number}: {self.title}")
        lines.append("")

        # Overview section
        lines.append("## Overview")
        lines.append(self.description)
        lines.append("")

        # Success criteria section
        if self.success_criteria:
            lines.append("## Success Criteria")
            for criterion in self.success_criteria:
                checkbox = "[x]" if criterion.completed else "[ ]"
                lines.append(f"- {checkbox} {criterion.description}")
            lines.append("")

        # Specs section
        if self.specs:
            lines.append("## Specs")
            lines.append("| Spec | Title | Status |")
            lines.append("|------|-------|--------|")
            for spec in self.specs:
                lines.append(
                    f"| {spec.spec_number:03d} | {spec.title} | {spec.status} |"
                )
            lines.append("")

        # Metadata footer (as HTML comment for parsing)
        lines.append("---")
        metadata = {
            "status": self.status.value,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }
        lines.append(f"<!-- metadata: {json.dumps(metadata)} -->")

        return "\n".join(lines)

    @classmethod
    def from_markdown(cls, content: str, number: int) -> "Epic":
        """Parse epic from markdown content."""
        lines = content.strip().split("\n")

        # Parse title from first header
        title = "Untitled"
        for line in lines:
            if line.startswith("# Epic"):
                # Format: "# Epic N: Title"
                match = re.match(r"#\s*Epic\s*\d+:\s*(.+)", line)
                if match:
                    title = match.group(1).strip()
                break

        # Parse overview/description
        description = ""
        in_overview = False
        for line in lines:
            if line.strip() == "## Overview":
                in_overview = True
                continue
            if in_overview:
                if line.startswith("## "):
                    break
                if line.strip():
                    description = line.strip() if not description else description
                    break

        # Parse success criteria
        success_criteria = []
        in_criteria = False
        for line in lines:
            if line.strip() == "## Success Criteria":
                in_criteria = True
                continue
            if in_criteria:
                if line.startswith("## "):
                    break
                match = re.match(r"-\s*\[([ xX])\]\s*(.+)", line)
                if match:
                    completed = match.group(1).lower() == "x"
                    desc = match.group(2).strip()
                    success_criteria.append(
                        SuccessCriterion(description=desc, completed=completed)
                    )

        # Parse specs table
        specs = []
        in_specs = False
        header_seen = False
        for line in lines:
            if line.strip() == "## Specs":
                in_specs = True
                continue
            if in_specs:
                if line.startswith("## ") or line.startswith("---"):
                    break
                # Skip table header and separator rows
                if line.startswith("|"):
                    # Check if this is the header row (first row with |)
                    if not header_seen and "Title" in line and "Status" in line:
                        header_seen = True
                        continue
                    # Check if this is the separator row (contains ---)
                    if "---" in line:
                        continue
                    # This is a data row
                    parts = [p.strip() for p in line.split("|")[1:-1]]
                    if len(parts) >= 3:
                        try:
                            spec_num = int(parts[0])
                            spec_title = parts[1]
                            spec_status = parts[2]
                            specs.append(
                                EpicSpec(
                                    spec_number=spec_num,
                                    title=spec_title,
                                    status=spec_status,
                                )
                            )
                        except ValueError:
                            continue

        # Parse metadata from comment
        status = EpicStatus.ACTIVE
        created_at = datetime.now().isoformat()
        completed_at = None

        for line in lines:
            if line.startswith("<!-- metadata:"):
                try:
                    json_str = line.replace("<!-- metadata:", "")
                    json_str = json_str.replace("-->", "").strip()
                    metadata = json.loads(json_str)
                    status = EpicStatus(metadata.get("status", "active"))
                    created_at = metadata.get("created_at", created_at)
                    completed_at = metadata.get("completed_at")
                except (json.JSONDecodeError, ValueError):
                    pass
                break

        return cls(
            number=number,
            title=title,
            description=description,
            status=status,
            success_criteria=success_criteria,
            specs=specs,
            created_at=created_at,
            completed_at=completed_at,
        )

    def save(self, epics_dir: Path) -> Path:
        """Save epic to markdown file."""
        file_path = epics_dir / self.file_path
        file_path.write_text(self.to_markdown(), encoding="utf-8")
        return file_path

    @classmethod
    def load(cls, file_path: Path) -> Optional["Epic"]:
        """Load epic from markdown file."""
        if not file_path.exists():
            return None
        try:
            content = file_path.read_text(encoding="utf-8")
            # Extract number from filename (e.g., "001-user-auth.md" -> 1)
            number = int(file_path.name[:3])
            return cls.from_markdown(content, number)
        except (OSError, ValueError):
            return None

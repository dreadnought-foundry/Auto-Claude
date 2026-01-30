"""
Registry Module
===============

Central registry for tracking all specs and epics in a project.
The registry is stored in .auto-claude/registry.json.

Features:
- Unique ID generation for specs and epics
- Quick lookup of spec/epic status
- Epic-spec relationship tracking
- Human-readable JSON storage
- Migration from existing specs on first run
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .epic import Epic

logger = logging.getLogger(__name__)

REGISTRY_VERSION = "1.0"
REGISTRY_FILENAME = "registry.json"


@dataclass
class SpecEntry:
    """Registry entry for a spec."""

    number: int
    title: str
    status: str  # pending, in_progress, complete
    epic_number: Optional[int] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None


@dataclass
class EpicEntry:
    """Registry entry for an epic."""

    number: int
    title: str
    status: str  # active, completed, archived
    spec_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None


@dataclass
class Counters:
    """Auto-increment counters for IDs."""

    next_epic: int = 1
    next_spec: int = 1


class Registry:
    """
    Central registry for specs and epics.

    The registry provides:
    - Unique ID generation for specs and epics
    - Quick lookup of spec/epic status
    - Epic-spec relationship tracking
    - Human-readable JSON storage
    """

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self.auto_claude_dir = self.project_dir / ".auto-claude"
        self.registry_path = self.auto_claude_dir / REGISTRY_FILENAME
        self.version = REGISTRY_VERSION
        self.epics: dict[int, EpicEntry] = {}
        self.specs: dict[int, SpecEntry] = {}
        self.counters = Counters()

        self._load()

    def _load(self) -> None:
        """Load registry from disk."""
        if not self.registry_path.exists():
            # First time - scan existing specs to populate
            self._scan_existing_specs()
            return

        try:
            data = json.loads(self.registry_path.read_text(encoding="utf-8"))
            self.version = data.get("version", REGISTRY_VERSION)

            # Load epics
            for num_str, epic_data in data.get("epics", {}).items():
                self.epics[int(num_str)] = EpicEntry(
                    number=epic_data["number"],
                    title=epic_data["title"],
                    status=epic_data["status"],
                    spec_count=epic_data.get("spec_count", 0),
                    created_at=epic_data.get("created_at", datetime.now().isoformat()),
                    completed_at=epic_data.get("completed_at"),
                )

            # Load specs
            for num_str, spec_data in data.get("specs", {}).items():
                self.specs[int(num_str)] = SpecEntry(
                    number=spec_data["number"],
                    title=spec_data["title"],
                    status=spec_data["status"],
                    epic_number=spec_data.get("epic_number"),
                    created_at=spec_data.get("created_at", datetime.now().isoformat()),
                    completed_at=spec_data.get("completed_at"),
                )

            # Load counters
            counters_data = data.get("counters", {})
            self.counters = Counters(
                next_epic=counters_data.get("nextEpic", 1),
                next_spec=counters_data.get("nextSpec", 1),
            )
        except (OSError, json.JSONDecodeError, KeyError) as e:
            logger.warning("Failed to load registry, rebuilding: %s", e)
            # Corrupted registry - rebuild from filesystem
            self._rebuild_from_filesystem()

    def _scan_existing_specs(self) -> None:
        """Scan existing specs to initialize registry (migration path)."""
        specs_dir = self.auto_claude_dir / "specs"
        if not specs_dir.exists():
            return

        max_spec_num = 0
        for folder in specs_dir.iterdir():
            if not folder.is_dir():
                continue
            try:
                # Parse spec number from folder name (e.g., "001-feature-name")
                num = int(folder.name[:3])
                name = folder.name[4:] if len(folder.name) > 4 else "unnamed"
                status = self._detect_spec_status(folder)

                self.specs[num] = SpecEntry(
                    number=num,
                    title=name,
                    status=status,
                )
                max_spec_num = max(max_spec_num, num)
            except ValueError:
                continue

        self.counters.next_spec = max_spec_num + 1
        self.save()

    def _detect_spec_status(self, spec_dir: Path) -> str:
        """Detect spec status from filesystem."""
        # Check for completion markers
        if (spec_dir / "qa_report.md").exists():
            return "complete"
        if (spec_dir / "implementation_plan.json").exists():
            return "in_progress"
        return "pending"

    def _rebuild_from_filesystem(self) -> None:
        """Rebuild registry from filesystem state."""
        self.epics = {}
        self.specs = {}
        self.counters = Counters()
        self._scan_existing_specs()
        self._scan_existing_epics()
        self.save()

    def _scan_existing_epics(self) -> None:
        """Scan existing epics to populate registry."""
        epics_dir = self.auto_claude_dir / "epics"
        if not epics_dir.exists():
            return

        max_epic_num = 0
        for file in epics_dir.glob("*.md"):
            try:
                num = int(file.name[:3])
                # Parse epic file to get details
                from .epic import Epic

                epic = Epic.load(file)
                if epic:
                    self.epics[num] = EpicEntry(
                        number=num,
                        title=epic.title,
                        status=epic.status.value,
                        spec_count=len(epic.specs),
                        created_at=epic.created_at,
                        completed_at=epic.completed_at,
                    )
                max_epic_num = max(max_epic_num, num)
            except ValueError:
                continue

        self.counters.next_epic = max_epic_num + 1

    def save(self) -> None:
        """Save registry to disk."""
        data = {
            "version": self.version,
            "epics": {
                str(n): {
                    "number": e.number,
                    "title": e.title,
                    "status": e.status,
                    "spec_count": e.spec_count,
                    "created_at": e.created_at,
                    "completed_at": e.completed_at,
                }
                for n, e in self.epics.items()
            },
            "specs": {
                str(n): {
                    "number": s.number,
                    "title": s.title,
                    "status": s.status,
                    "epic_number": s.epic_number,
                    "created_at": s.created_at,
                    "completed_at": s.completed_at,
                }
                for n, s in self.specs.items()
            },
            "counters": {
                "nextEpic": self.counters.next_epic,
                "nextSpec": self.counters.next_spec,
            },
        }

        self.auto_claude_dir.mkdir(parents=True, exist_ok=True)
        self.registry_path.write_text(
            json.dumps(data, indent=2, default=str), encoding="utf-8"
        )

    # Epic operations
    def allocate_epic_number(self) -> int:
        """Allocate the next epic number."""
        num = self.counters.next_epic
        self.counters.next_epic += 1
        self.save()
        return num

    def register_epic(self, epic: "Epic") -> None:
        """Register a new epic."""
        self.epics[epic.number] = EpicEntry(
            number=epic.number,
            title=epic.title,
            status=epic.status.value,
            spec_count=len(epic.specs),
            created_at=epic.created_at,
            completed_at=epic.completed_at,
        )
        self.save()

    def update_epic(self, epic_number: int, **kwargs) -> bool:
        """Update an epic entry."""
        if epic_number not in self.epics:
            return False
        for key, value in kwargs.items():
            if hasattr(self.epics[epic_number], key):
                setattr(self.epics[epic_number], key, value)
        self.save()
        return True

    def get_epic(self, epic_number: int) -> Optional[EpicEntry]:
        """Get an epic entry."""
        return self.epics.get(epic_number)

    def list_epics(self, status: Optional[str] = None) -> list[EpicEntry]:
        """List epics, optionally filtered by status."""
        epics = list(self.epics.values())
        if status:
            epics = [e for e in epics if e.status == status]
        return sorted(epics, key=lambda e: e.number)

    # Spec operations
    def allocate_spec_number(self) -> int:
        """Allocate the next spec number."""
        num = self.counters.next_spec
        self.counters.next_spec += 1
        self.save()
        return num

    def register_spec(
        self, spec_number: int, title: str, epic_number: Optional[int] = None
    ) -> None:
        """Register a new spec."""
        self.specs[spec_number] = SpecEntry(
            number=spec_number,
            title=title,
            status="pending",
            epic_number=epic_number,
        )

        # Update epic's spec count if associated
        if epic_number and epic_number in self.epics:
            self.epics[epic_number].spec_count += 1

        self.save()

    def update_spec_status(self, spec_number: int, status: str) -> bool:
        """Update a spec's status."""
        if spec_number not in self.specs:
            return False

        old_status = self.specs[spec_number].status
        self.specs[spec_number].status = status

        if status == "complete" and old_status != "complete":
            self.specs[spec_number].completed_at = datetime.now().isoformat()

        self.save()
        return True

    def get_spec(self, spec_number: int) -> Optional[SpecEntry]:
        """Get a spec entry."""
        return self.specs.get(spec_number)

    def get_specs_for_epic(self, epic_number: int) -> list[SpecEntry]:
        """Get all specs associated with an epic."""
        return [s for s in self.specs.values() if s.epic_number == epic_number]

    def assign_spec_to_epic(self, spec_number: int, epic_number: int) -> bool:
        """Assign a spec to an epic."""
        if spec_number not in self.specs:
            return False
        if epic_number not in self.epics:
            return False

        # Remove from old epic if any
        old_epic = self.specs[spec_number].epic_number
        if old_epic and old_epic in self.epics:
            self.epics[old_epic].spec_count -= 1

        # Assign to new epic
        self.specs[spec_number].epic_number = epic_number
        self.epics[epic_number].spec_count += 1

        self.save()
        return True

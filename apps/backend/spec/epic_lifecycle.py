"""
Epic Lifecycle Module
=====================

Monitors spec completions and auto-completes epics when all specs are done.

Auto-complete rules:
1. All specs in the epic must have status "done"
2. All success criteria must be marked complete
3. Epic must have at least one spec
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from .epic import Epic, EpicStatus
from .registry import Registry


class EpicLifecycleManager:
    """
    Manages epic lifecycle events and auto-completion detection.

    Auto-complete rules:
    1. All specs in the epic must have status "done"
    2. All success criteria must be marked complete
    3. Epic must have at least one spec
    """

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self.epics_dir = self.project_dir / ".auto-claude" / "epics"
        self.registry = Registry(project_dir)

    def on_spec_completed(self, spec_number: int) -> Optional[int]:
        """
        Called when a spec is completed.

        Checks if the spec's epic should be auto-completed.

        Args:
            spec_number: The completed spec number

        Returns:
            Epic number if an epic was auto-completed, None otherwise
        """
        # Update registry
        self.registry.update_spec_status(spec_number, "complete")

        # Check if spec belongs to an epic
        spec_entry = self.registry.get_spec(spec_number)
        if not spec_entry or not spec_entry.epic_number:
            return None

        epic_number = spec_entry.epic_number

        # Load the full epic to check completion
        epic = self._load_epic(epic_number)
        if not epic:
            return None

        # Update the spec status in the epic
        epic.update_spec_status(spec_number, "done")
        epic.save(self.epics_dir)

        # Check if epic should auto-complete
        if epic.check_complete():
            return self.complete_epic(epic_number)

        return None

    def complete_epic(self, epic_number: int) -> Optional[int]:
        """
        Mark an epic as completed.

        Args:
            epic_number: The epic to complete

        Returns:
            Epic number if successful, None otherwise
        """
        epic = self._load_epic(epic_number)
        if not epic:
            return None

        epic.status = EpicStatus.COMPLETED
        epic.completed_at = datetime.now().isoformat()
        epic.save(self.epics_dir)

        self.registry.update_epic(
            epic_number,
            status="completed",
            completed_at=epic.completed_at,
        )

        return epic_number

    def check_epic_completion(self, epic_number: int) -> dict:
        """
        Check the completion status of an epic.

        Returns:
            Dict with completion details:
            - epic_number: The epic number
            - title: Epic title
            - status: Current status
            - specs: {completed, total, progress}
            - criteria: {completed, total, progress}
            - can_complete: Boolean indicating if epic can be completed
        """
        epic = self._load_epic(epic_number)
        if not epic:
            return {"error": "Epic not found"}

        specs_done = sum(1 for s in epic.specs if s.status == "done")
        specs_total = len(epic.specs)
        criteria_done = sum(1 for c in epic.success_criteria if c.completed)
        criteria_total = len(epic.success_criteria)

        return {
            "epic_number": epic_number,
            "title": epic.title,
            "status": epic.status.value,
            "specs": {
                "completed": specs_done,
                "total": specs_total,
                "progress": specs_done / specs_total if specs_total > 0 else 0,
            },
            "criteria": {
                "completed": criteria_done,
                "total": criteria_total,
                "progress": criteria_done / criteria_total if criteria_total > 0 else 0,
            },
            "can_complete": epic.check_complete(),
        }

    def _load_epic(self, epic_number: int) -> Optional[Epic]:
        """Load an epic by number."""
        if not self.epics_dir.exists():
            return None

        for file in self.epics_dir.glob("*.md"):
            if file.name.startswith(f"{epic_number:03d}-"):
                return Epic.load(file)

        return None


def get_lifecycle_manager(project_dir: Path) -> EpicLifecycleManager:
    """Factory function to get a lifecycle manager."""
    return EpicLifecycleManager(project_dir)

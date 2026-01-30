"""Maestro state file persistence.

Handles reading and writing sprint state files in Maestro format.
Uses atomic writes to prevent corruption.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# State file naming pattern: .claude/sprint-{N}-state.json
STATE_FILE_PATTERN = "sprint-{sprint}-state.json"
STATE_DIR = ".claude"


@dataclass
class PhaseRecord:
    """Record of a phase's execution."""

    started: Optional[str] = None
    completed: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize to dict, omitting None values."""
        result = {}
        if self.started:
            result["started"] = self.started
        if self.completed:
            result["completed"] = self.completed
        return result

    @classmethod
    def from_dict(cls, data: dict) -> PhaseRecord:
        """Deserialize from dict."""
        return cls(
            started=data.get("started"),
            completed=data.get("completed"),
        )


@dataclass
class MaestroState:
    """Maestro sprint state."""

    sprint: int
    type: str  # SprintType value (backend, frontend, etc.)
    current_phase: Optional[str] = None
    started: Optional[str] = None
    phases: dict[str, PhaseRecord] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "sprint": self.sprint,
            "type": self.type,
            "current_phase": self.current_phase,
            "started": self.started,
            "phases": {k: v.to_dict() for k, v in self.phases.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> MaestroState:
        """Deserialize from dict."""
        phases = {}
        for phase_id, phase_data in data.get("phases", {}).items():
            phases[phase_id] = PhaseRecord.from_dict(phase_data)

        return cls(
            sprint=data.get("sprint", 0),
            type=data.get("type", "fullstack"),
            current_phase=data.get("current_phase"),
            started=data.get("started"),
            phases=phases,
        )


def get_state_file_path(project_dir: Path, sprint_number: int) -> Path:
    """Get the path to the state file for a sprint.

    Args:
        project_dir: Project root directory
        sprint_number: Sprint number

    Returns:
        Path to state file (.claude/sprint-N-state.json)
    """
    return project_dir / STATE_DIR / STATE_FILE_PATTERN.format(sprint=sprint_number)


def load_state(project_dir: Path, sprint_number: int) -> Optional[MaestroState]:
    """Load state from file with graceful degradation.

    Args:
        project_dir: Project root directory
        sprint_number: Sprint number

    Returns:
        MaestroState or None if file missing/corrupt
    """
    state_file = get_state_file_path(project_dir, sprint_number)

    if not state_file.exists():
        return None

    try:
        with open(state_file, encoding="utf-8") as f:
            content = f.read()
            if not content.strip():
                return None
            data = json.loads(content)
        return MaestroState.from_dict(data)
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as e:
        # Log error but don't crash - graceful degradation
        print(f"Warning: Failed to load maestro state: {e}", file=sys.stderr)
        return None


def save_state(project_dir: Path, state: MaestroState) -> bool:
    """Save state to file atomically.

    Uses temp file + atomic rename to prevent corruption.

    Args:
        project_dir: Project root directory
        state: State to save

    Returns:
        True if saved successfully
    """
    state_file = get_state_file_path(project_dir, state.sprint)

    try:
        # Ensure .claude directory exists
        state_file.parent.mkdir(parents=True, exist_ok=True)

        # Write to temp file first
        fd, tmp_path = tempfile.mkstemp(
            dir=state_file.parent,
            prefix=".maestro_state_",
            suffix=".tmp",
        )

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state.to_dict(), f, indent=2, ensure_ascii=False)

            # Atomic rename
            os.replace(tmp_path, state_file)
            return True

        except Exception:
            # Clean up temp file on failure
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    except OSError as e:
        print(f"Warning: Failed to save maestro state: {e}", file=sys.stderr)
        return False


def get_timestamp() -> str:
    """Get current timestamp in ISO format with timezone."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

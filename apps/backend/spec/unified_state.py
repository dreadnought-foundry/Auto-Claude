"""Unified state operations for project-level task state.

Provides read/write access to the unified task state format that both
Maestro (Claude Code workflow) and Auto Claude (autonomous agent pipeline)
can use.

State Location: {project}/.claude/task-state.json

This module is designed to be duplicated in Maestro scripts (~/.claude/scripts/)
to avoid cross-repository dependencies while maintaining identical behavior.

Usage:
    from spec.unified_state import load_state, save_state, upsert_task, get_task

    # Get project state
    state = load_state(project_root)

    # Add or update a task
    upsert_task({
        "id": "5",
        "title": "Add user auth",
        "pipeline": "maestro",
        "status": "in_progress",
        "phase": "2",
        "step": "2.3",
    }, project_root)

    # Get a specific task
    task = get_task("5", project_root)
"""

from __future__ import annotations

import fcntl
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

# Schema version - increment when breaking changes are made
UNIFIED_STATE_VERSION = "1.0"

# State file name
STATE_FILE_NAME = "task-state.json"

# Project markers to detect project root
PROJECT_MARKERS = [".git", ".auto-claude", "package.json", "pyproject.toml", ".claude"]


def find_project_root(start_path: Path | None = None) -> Path | None:
    """Walk up directory tree to find project root.

    Looks for common project markers (.git, .auto-claude, package.json, etc.)
    and returns the first directory containing one of these markers.

    Args:
        start_path: Starting directory to search from. Defaults to cwd.

    Returns:
        Path to project root, or None if no project markers found.
    """
    current = (start_path or Path.cwd()).resolve()

    while current != current.parent:
        if any((current / marker).exists() for marker in PROJECT_MARKERS):
            return current
        current = current.parent

    return None


def get_state_path(project_root: Path | None = None) -> Path:
    """Get unified state path for project.

    If a project root is provided or detected, returns the path to
    {project}/.claude/task-state.json. Otherwise falls back to
    ~/.claude/task-state.json for non-project contexts.

    Creates the .claude directory if it doesn't exist.

    Args:
        project_root: Project root path. If None, will attempt to detect.

    Returns:
        Path to the task-state.json file.
    """
    if project_root is None:
        project_root = find_project_root()

    if project_root:
        state_dir = project_root / ".claude"
        state_dir.mkdir(exist_ok=True)
        return state_dir / STATE_FILE_NAME

    # Fallback for non-project contexts
    fallback_dir = Path.home() / ".claude"
    fallback_dir.mkdir(exist_ok=True)
    return fallback_dir / STATE_FILE_NAME


def _empty_state(project_root: Path | None = None) -> dict[str, Any]:
    """Create an empty state structure."""
    return {
        "version": UNIFIED_STATE_VERSION,
        "projectRoot": str(project_root or find_project_root() or ""),
        "tasks": [],
        "lastUpdated": datetime.now().isoformat(),
    }


def load_state(project_root: Path | None = None) -> dict[str, Any]:
    """Load unified state with file locking.

    Loads the task state from {project}/.claude/task-state.json with
    shared file locking to prevent corruption from concurrent reads.

    If the file doesn't exist or is corrupt, returns an empty state.

    Args:
        project_root: Project root path. If None, will attempt to detect.

    Returns:
        Dictionary containing version, projectRoot, tasks, and lastUpdated.
    """
    state_path = get_state_path(project_root)

    if not state_path.exists():
        return _empty_state(project_root)

    try:
        with open(state_path, encoding="utf-8") as f:
            # Shared lock for reading
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                return json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except (json.JSONDecodeError, OSError) as e:
        # Log warning but return empty state
        print(f"Warning: Failed to load state from {state_path}: {e}", file=sys.stderr)
        return _empty_state(project_root)


def save_state(state: dict[str, Any], project_root: Path | None = None) -> bool:
    """Save unified state atomically with file locking.

    Writes the state to a temporary file first, then atomically renames
    to the target path. Uses exclusive file locking to prevent concurrent
    write corruption.

    Args:
        state: State dictionary to save.
        project_root: Project root path. If None, will attempt to detect.

    Returns:
        True if save succeeded, False otherwise.
    """
    state_path = get_state_path(project_root)

    # Update timestamp
    state["lastUpdated"] = datetime.now().isoformat()

    try:
        # Write to temp file first for atomic operation
        fd, tmp_path = tempfile.mkstemp(
            dir=state_path.parent, prefix=".task_state_", suffix=".tmp"
        )

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                # Exclusive lock for writing
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    json.dump(state, f, indent=2, ensure_ascii=False)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            # Atomic rename
            os.replace(tmp_path, state_path)
            return True
        except Exception:
            # Clean up temp file on failure
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
    except OSError as e:
        print(f"Warning: Failed to save state to {state_path}: {e}", file=sys.stderr)
        return False


def get_task(task_id: str, project_root: Path | None = None) -> dict[str, Any] | None:
    """Get a task by ID.

    Args:
        task_id: The task ID to find.
        project_root: Project root path. If None, will attempt to detect.

    Returns:
        Task dictionary if found, None otherwise.
    """
    state = load_state(project_root)
    for task in state.get("tasks", []):
        if task.get("id") == task_id:
            return task
    return None


def upsert_task(task: dict[str, Any], project_root: Path | None = None) -> bool:
    """Insert or update a task.

    If a task with the same ID exists, it will be replaced.
    Otherwise, the task is appended to the tasks list.

    Args:
        task: Task dictionary to insert/update. Must have an "id" field.
        project_root: Project root path. If None, will attempt to detect.

    Returns:
        True if operation succeeded, False otherwise.
    """
    state = load_state(project_root)
    tasks = state.get("tasks", [])
    task_id = task.get("id")

    # Find and update existing task
    for i, t in enumerate(tasks):
        if t.get("id") == task_id:
            tasks[i] = task
            state["tasks"] = tasks
            return save_state(state, project_root)

    # Insert new task
    tasks.append(task)
    state["tasks"] = tasks
    return save_state(state, project_root)


def delete_task(task_id: str, project_root: Path | None = None) -> bool:
    """Delete a task by ID.

    Args:
        task_id: The task ID to delete.
        project_root: Project root path. If None, will attempt to detect.

    Returns:
        True if operation succeeded, False otherwise.
    """
    state = load_state(project_root)
    tasks = [t for t in state.get("tasks", []) if t.get("id") != task_id]
    state["tasks"] = tasks
    return save_state(state, project_root)


def get_tasks_by_pipeline(
    pipeline: str, project_root: Path | None = None
) -> list[dict[str, Any]]:
    """Get all tasks for a specific pipeline type.

    Args:
        pipeline: Pipeline type ("maestro" or "autonomous").
        project_root: Project root path. If None, will attempt to detect.

    Returns:
        List of tasks matching the pipeline type.
    """
    state = load_state(project_root)
    return [t for t in state.get("tasks", []) if t.get("pipeline") == pipeline]


def get_active_tasks(project_root: Path | None = None) -> list[dict[str, Any]]:
    """Get all active (in_progress) tasks.

    Args:
        project_root: Project root path. If None, will attempt to detect.

    Returns:
        List of tasks with status "in_progress".
    """
    state = load_state(project_root)
    return [t for t in state.get("tasks", []) if t.get("status") == "in_progress"]


def create_maestro_task(
    sprint_num: int,
    title: str,
    sprint_file: str,
    project_root: Path,
    sprint_type: str | None = None,
    epic_number: int | None = None,
) -> dict[str, Any]:
    """Create a new Maestro task in unified format.

    Args:
        sprint_num: Sprint number.
        title: Sprint title.
        sprint_file: Relative path to sprint.md file.
        project_root: Project root path.
        sprint_type: Sprint type (fullstack, backend, etc.).
        epic_number: Epic number if part of an epic.

    Returns:
        The created task dictionary.
    """
    task = {
        "id": str(sprint_num),
        "title": title,
        "pipeline": "maestro",
        "status": "in_progress",
        "phase": "1",
        "step": "1.1",
        "completedSteps": [],
        "sprintFile": sprint_file,
        "created": datetime.now().isoformat(),
        "started": datetime.now().isoformat(),
        "sprintType": sprint_type,
        "epicNumber": epic_number,
        "workflowVersion": "3.0",
    }

    upsert_task(task, project_root)
    return task


def create_autonomous_task(
    spec_id: str,
    title: str,
    spec_dir: str,
    project_root: Path,
    sprint_type: str | None = None,
) -> dict[str, Any]:
    """Create an autonomous pipeline task in unified format.

    Args:
        spec_id: Spec ID (e.g., "001").
        title: Task title.
        spec_dir: Relative path to spec directory.
        project_root: Project root path.
        sprint_type: Sprint type for coverage thresholds.

    Returns:
        The created task dictionary.
    """
    task = {
        "id": spec_id,
        "title": title,
        "pipeline": "autonomous",
        "status": "pending",
        "phase": "planning",
        "subtasks": [],
        "specDir": spec_dir,
        "created": datetime.now().isoformat(),
        "sprintType": sprint_type or "fullstack",
    }

    upsert_task(task, project_root)
    return task


def update_maestro_progress(
    sprint_num: int,
    phase: str,
    step: str,
    completed_steps: list[str],
    project_root: Path,
) -> bool:
    """Update progress for a Maestro task.

    Args:
        sprint_num: Sprint number.
        phase: Current phase number as string.
        step: Current step (e.g., "2.3").
        completed_steps: List of completed step IDs.
        project_root: Project root path.

    Returns:
        True if update succeeded, False otherwise.
    """
    task = get_task(str(sprint_num), project_root)
    if not task:
        return False

    task["phase"] = phase
    task["step"] = step
    task["completedSteps"] = completed_steps

    return upsert_task(task, project_root)


def update_autonomous_progress(
    spec_id: str,
    phase: str,
    subtasks: list[dict[str, Any]],
    current_subtask: str | None,
    project_root: Path,
) -> bool:
    """Update progress for an autonomous task.

    Args:
        spec_id: Spec ID.
        phase: Current phase (planning, coding, qa_review, etc.).
        subtasks: List of subtask dictionaries.
        current_subtask: ID of current subtask.
        project_root: Project root path.

    Returns:
        True if update succeeded, False otherwise.
    """
    task = get_task(spec_id, project_root)
    if not task:
        return False

    task["phase"] = phase
    task["subtasks"] = subtasks
    task["currentSubtask"] = current_subtask

    # Derive status from phase and subtasks
    if subtasks:
        if all(s.get("status") == "completed" for s in subtasks):
            task["status"] = "completed"
            task["completed"] = datetime.now().isoformat()
        elif any(s.get("status") == "failed" for s in subtasks):
            task["status"] = "failed"
        elif any(s.get("status") == "in_progress" for s in subtasks):
            task["status"] = "in_progress"
            if not task.get("started"):
                task["started"] = datetime.now().isoformat()

    return upsert_task(task, project_root)


def complete_task(task_id: str, project_root: Path) -> bool:
    """Mark a task as completed.

    Args:
        task_id: Task ID to complete.
        project_root: Project root path.

    Returns:
        True if update succeeded, False otherwise.
    """
    task = get_task(task_id, project_root)
    if not task:
        return False

    task["status"] = "completed"
    task["completed"] = datetime.now().isoformat()

    return upsert_task(task, project_root)


def fail_task(task_id: str, project_root: Path, error: str | None = None) -> bool:
    """Mark a task as failed.

    Args:
        task_id: Task ID to fail.
        project_root: Project root path.
        error: Optional error message.

    Returns:
        True if update succeeded, False otherwise.
    """
    task = get_task(task_id, project_root)
    if not task:
        return False

    task["status"] = "failed"
    if error:
        task["error"] = error

    return upsert_task(task, project_root)

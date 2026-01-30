"""
Agent Metrics Collection
========================

Collects and aggregates execution metrics from agent sessions.
Used by postmortem generation and analytics.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class SessionMetrics:
    """Metrics from a single agent session."""

    agent_type: str
    session_num: int
    subtask_id: str | None
    started_at: datetime
    ended_at: datetime | None = None
    success: bool = False
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class ExecutionMetrics:
    """Aggregated metrics from a complete spec execution."""

    spec_name: str
    sprint_type: str
    started_at: str
    completed_at: str
    duration_seconds: float
    total_subtasks: int
    completed_subtasks: int
    phases_count: int
    agents_used: set[str]
    tests_added: int
    coverage_delta: float
    files_changed: int
    commits_count: int
    rework_cycles: int


@dataclass
class AgentContribution:
    """Tracks what each agent type contributed."""

    agent_type: str
    tasks_completed: int
    files_created: list[str]
    files_modified: list[str]
    sessions_count: int
    duration_seconds: float


class MetricsCollector:
    """Collects metrics throughout spec execution."""

    def __init__(self, spec_dir: Path, project_dir: Path):
        """
        Initialize the metrics collector.

        Args:
            spec_dir: Spec directory for this build
            project_dir: Project root directory
        """
        self.spec_dir = Path(spec_dir)
        self.project_dir = Path(project_dir)
        self._sessions: list[SessionMetrics] = []

    def record_session_start(
        self, agent_type: str, session_num: int, subtask_id: str | None = None
    ) -> SessionMetrics:
        """
        Record the start of an agent session.

        Args:
            agent_type: Type of agent (planner, coder, qa_reviewer, qa_fixer)
            session_num: Session number
            subtask_id: Optional subtask being worked on

        Returns:
            SessionMetrics record to update on completion
        """
        session = SessionMetrics(
            agent_type=agent_type,
            session_num=session_num,
            subtask_id=subtask_id,
            started_at=datetime.now(timezone.utc),
        )
        self._sessions.append(session)
        return session

    def record_session_end(
        self,
        session: SessionMetrics,
        success: bool,
        files_changed: list[str],
    ) -> None:
        """
        Record the end of an agent session.

        Args:
            session: Session record from record_session_start
            success: Whether the session was successful
            files_changed: List of files created or modified
        """
        session.ended_at = datetime.now(timezone.utc)
        session.success = success
        session.files_modified = files_changed

    def aggregate_metrics(self) -> ExecutionMetrics:
        """
        Aggregate metrics from all recorded sessions.

        Returns:
            ExecutionMetrics with aggregated data
        """
        agents_used = {s.agent_type for s in self._sessions}

        # Calculate duration
        if self._sessions:
            first_start = min(s.started_at for s in self._sessions)
            last_end = max(
                s.ended_at or s.started_at for s in self._sessions
            )
            duration = (last_end - first_start).total_seconds()
        else:
            duration = 0
            first_start = datetime.now(timezone.utc)
            last_end = first_start

        return ExecutionMetrics(
            spec_name=self.spec_dir.name,
            sprint_type="fullstack",
            started_at=first_start.isoformat(),
            completed_at=last_end.isoformat(),
            duration_seconds=duration,
            total_subtasks=0,
            completed_subtasks=0,
            phases_count=0,
            agents_used=agents_used,
            tests_added=0,
            coverage_delta=0.0,
            files_changed=0,
            commits_count=0,
            rework_cycles=0,
        )

    def save_metrics(self) -> Path:
        """
        Save metrics to spec directory.

        Returns:
            Path to saved metrics file
        """
        metrics_file = self.spec_dir / "execution_metrics.json"
        data = {
            "sessions": [
                {
                    "agent_type": s.agent_type,
                    "session_num": s.session_num,
                    "subtask_id": s.subtask_id,
                    "started_at": s.started_at.isoformat(),
                    "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                    "success": s.success,
                    "files_created": s.files_created,
                    "files_modified": s.files_modified,
                }
                for s in self._sessions
            ],
        }
        metrics_file.write_text(json.dumps(data, indent=2))
        return metrics_file

    def load_metrics(self) -> ExecutionMetrics | None:
        """
        Load previously saved metrics.

        Returns:
            ExecutionMetrics or None if not found
        """
        metrics_file = self.spec_dir / "execution_metrics.json"
        if not metrics_file.exists():
            return None
        try:
            data = json.loads(metrics_file.read_text())
            # Reconstruct sessions and aggregate
            self._sessions = []
            for s_data in data.get("sessions", []):
                session = SessionMetrics(
                    agent_type=s_data["agent_type"],
                    session_num=s_data["session_num"],
                    subtask_id=s_data.get("subtask_id"),
                    started_at=datetime.fromisoformat(s_data["started_at"]),
                    ended_at=(
                        datetime.fromisoformat(s_data["ended_at"])
                        if s_data.get("ended_at")
                        else None
                    ),
                    success=s_data.get("success", False),
                    files_created=s_data.get("files_created", []),
                    files_modified=s_data.get("files_modified", []),
                )
                self._sessions.append(session)
            return self.aggregate_metrics()
        except (json.JSONDecodeError, KeyError, TypeError):
            return None


def collect_execution_metrics(spec_dir: Path, project_dir: Path) -> ExecutionMetrics:
    """
    Collect all execution metrics post-hoc from existing files.

    This is the main entry point for collecting metrics from a completed spec.
    It aggregates data from implementation_plan.json, attempt_history.json,
    and other sources.

    Args:
        spec_dir: Spec directory
        project_dir: Project root directory

    Returns:
        ExecutionMetrics with all available data
    """
    spec_dir = Path(spec_dir)
    project_dir = Path(project_dir)

    # Defaults for graceful degradation
    spec_name = spec_dir.name
    sprint_type = "fullstack"
    started_at = ""
    completed_at = ""
    duration_seconds = 0.0
    total_subtasks = 0
    completed_subtasks = 0
    phases_count = 0
    agents_used: set[str] = set()
    tests_added = 0
    coverage_delta = 0.0
    files_changed = 0
    commits_count = 0
    rework_cycles = 0

    # Load implementation plan
    plan_file = spec_dir / "implementation_plan.json"
    if plan_file.exists():
        try:
            plan = json.loads(plan_file.read_text())

            # Get sprint type
            sprint_type = plan.get("workflow_type", "fullstack")

            # Count phases and subtasks
            phases = plan.get("phases", [])
            phases_count = len(phases)

            for phase in phases:
                subtasks = phase.get("subtasks", [])
                total_subtasks += len(subtasks)
                for subtask in subtasks:
                    if subtask.get("status") == "completed":
                        completed_subtasks += 1

            # Get QA iteration history for rework cycles
            qa_history = plan.get("qa_iteration_history", [])
            for iteration in qa_history:
                if iteration.get("status") == "rejected":
                    rework_cycles += 1

            # Get timestamps from QA signoff
            qa_signoff = plan.get("qa_signoff", {})
            if qa_signoff.get("timestamp"):
                completed_at = qa_signoff["timestamp"]

        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    # Load attempt history
    memory_dir = spec_dir / "memory"
    attempt_file = memory_dir / "attempt_history.json"
    if attempt_file.exists():
        try:
            attempts_data = json.loads(attempt_file.read_text())
            attempts = attempts_data.get("attempts", [])

            for attempt in attempts:
                agent = attempt.get("agent_type")
                if agent:
                    agents_used.add(agent)

                # Track first attempt as start time
                if attempt.get("started_at") and not started_at:
                    started_at = attempt["started_at"]

        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    # Calculate duration if we have timestamps
    if started_at and completed_at:
        try:
            start_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
            duration_seconds = (end_dt - start_dt).total_seconds()
        except (ValueError, TypeError):
            pass

    return ExecutionMetrics(
        spec_name=spec_name,
        sprint_type=sprint_type,
        started_at=started_at,
        completed_at=completed_at,
        duration_seconds=duration_seconds,
        total_subtasks=total_subtasks,
        completed_subtasks=completed_subtasks,
        phases_count=phases_count,
        agents_used=agents_used,
        tests_added=tests_added,
        coverage_delta=coverage_delta,
        files_changed=files_changed,
        commits_count=commits_count,
        rework_cycles=rework_cycles,
    )

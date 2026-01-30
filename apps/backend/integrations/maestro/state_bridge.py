"""Maestro State Bridge.

Bridges Auto-Claude task state with Maestro workflow phases
for unified progress tracking.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Callable, Optional

from .phase_mapping import (
    MaestroPhase,
    get_phase_for_stage,
)
from .state_file import (
    MaestroState,
    PhaseRecord,
    get_timestamp,
    load_state,
    save_state,
)


# Event callback type: (state, new_phase, previous_phase) -> Any
StateChangeCallback = Callable[[MaestroState, str, Optional[str]], Any]


class MaestroStateBridge:
    """
    Bridges Auto-Claude stage transitions to Maestro workflow phases.

    This class:
    - Tracks the current Maestro phase based on Auto-Claude stage
    - Persists state to .claude/sprint-{N}-state.json
    - Emits events on state changes for observability
    - Handles graceful degradation if state file is missing/corrupt

    Usage:
        bridge = MaestroStateBridge(project_dir, sprint_number=42, sprint_type="backend")

        # Register callbacks for state changes
        bridge.on_state_change(lambda state, phase, prev: print(f"Phase: {phase}"))

        # Transition to a new stage
        await bridge.transition_to_stage("planning")
        await bridge.transition_to_stage("implementation")
        await bridge.complete_current_phase()
    """

    def __init__(
        self,
        project_dir: Path,
        sprint_number: int,
        sprint_type: str = "fullstack",
    ):
        """
        Initialize the state bridge.

        Args:
            project_dir: Project root directory
            sprint_number: Sprint number for state file naming
            sprint_type: Sprint type (backend, frontend, etc.)
        """
        self.project_dir = Path(project_dir)
        self.sprint_number = sprint_number
        self.sprint_type = sprint_type
        self._callbacks: list[StateChangeCallback] = []
        self._state: Optional[MaestroState] = None
        self._initialized = False

    @property
    def state(self) -> Optional[MaestroState]:
        """Get current state (lazy load from file)."""
        if self._state is None and not self._initialized:
            self._state = load_state(self.project_dir, self.sprint_number)
            self._initialized = True
        return self._state

    @property
    def current_phase(self) -> Optional[str]:
        """Get current Maestro phase."""
        return self.state.current_phase if self.state else None

    @property
    def is_active(self) -> bool:
        """Check if sprint state exists and is active."""
        return self.state is not None and self.state.current_phase is not None

    def on_state_change(self, callback: StateChangeCallback) -> None:
        """
        Register a callback for state changes.

        Callback receives: (state, new_phase, previous_phase)

        Args:
            callback: Function to call on state changes
        """
        self._callbacks.append(callback)

    async def initialize(self) -> bool:
        """
        Initialize state file for a new sprint.

        Creates the initial state file if it doesn't exist.
        Safe to call multiple times (idempotent).

        Returns:
            True if initialized successfully
        """
        if self._state is not None:
            return True  # Already initialized

        # Try loading existing state first
        self._state = load_state(self.project_dir, self.sprint_number)
        self._initialized = True

        if self._state is not None:
            return True  # Loaded existing state

        # Create new state
        self._state = MaestroState(
            sprint=self.sprint_number,
            type=self.sprint_type,
            started=get_timestamp(),
        )

        return await self._save_state_async()

    async def transition_to_stage(self, stage: str) -> bool:
        """
        Transition to a new Auto-Claude stage.

        Maps the stage to a Maestro phase and updates state.

        Args:
            stage: Auto-Claude stage name (e.g., "planning", "implementation")

        Returns:
            True if transition successful
        """
        maestro_phase = get_phase_for_stage(stage)
        if maestro_phase is None:
            return False  # Unknown stage, ignore

        return await self.transition_to_phase(maestro_phase.value)

    async def transition_to_phase(self, phase: str) -> bool:
        """
        Transition to a specific Maestro phase.

        Args:
            phase: Maestro phase ID (e.g., "1.1", "2.3")

        Returns:
            True if transition successful
        """
        # Ensure state exists
        if self._state is None:
            await self.initialize()

        if self._state is None:
            return False  # Failed to initialize

        previous_phase = self._state.current_phase

        # Complete previous phase if different
        if previous_phase and previous_phase != phase:
            if previous_phase in self._state.phases:
                self._state.phases[previous_phase].completed = get_timestamp()

        # Start new phase
        self._state.current_phase = phase

        if phase not in self._state.phases:
            self._state.phases[phase] = PhaseRecord()

        if self._state.phases[phase].started is None:
            self._state.phases[phase].started = get_timestamp()

        # Save and emit event
        success = await self._save_state_async()

        if success:
            await self._emit_state_change(phase, previous_phase)

        return success

    async def complete_current_phase(self) -> bool:
        """
        Mark the current phase as completed.

        Returns:
            True if completed successfully
        """
        if self._state is None or self._state.current_phase is None:
            return False

        phase = self._state.current_phase

        if phase in self._state.phases:
            self._state.phases[phase].completed = get_timestamp()

        return await self._save_state_async()

    async def complete_sprint(self) -> bool:
        """
        Mark the sprint as complete.

        Transitions to phase 6.1 and completes it.

        Returns:
            True if completed successfully
        """
        await self.transition_to_phase(MaestroPhase.COMPLETE_UPDATE.value)
        await self.complete_current_phase()
        return True

    def get_phase_history(self) -> dict[str, dict]:
        """
        Get the history of all phase transitions.

        Returns:
            Dict of phase_id -> {started, completed}
        """
        if self._state is None:
            return {}

        return {
            phase_id: record.to_dict()
            for phase_id, record in self._state.phases.items()
        }

    async def _save_state_async(self) -> bool:
        """Save state asynchronously (non-blocking)."""
        if self._state is None:
            return False

        # Run file I/O in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            save_state,
            self.project_dir,
            self._state,
        )

    async def _emit_state_change(
        self,
        new_phase: str,
        previous_phase: Optional[str],
    ) -> None:
        """Emit state change event to all callbacks."""
        for callback in self._callbacks:
            try:
                result = callback(self._state, new_phase, previous_phase)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                print(f"Warning: State change callback error: {e}", file=sys.stderr)


def create_state_bridge(
    project_dir: Path,
    sprint_number: int,
    sprint_type: str = "fullstack",
) -> MaestroStateBridge:
    """
    Create a MaestroStateBridge instance.

    Args:
        project_dir: Project root directory
        sprint_number: Sprint number
        sprint_type: Sprint type (from spec/types.py)

    Returns:
        Configured MaestroStateBridge
    """
    return MaestroStateBridge(project_dir, sprint_number, sprint_type)

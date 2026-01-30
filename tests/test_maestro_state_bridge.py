"""Tests for Maestro state bridge integration.

Tests the state synchronization between Auto-Claude execution stages
and Maestro workflow phases.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from integrations.maestro.phase_mapping import (
    AutoClaudeStage,
    MaestroPhase,
    get_phase_for_stage,
    get_phase_info,
    STAGE_TO_PHASE,
    PhaseInfo,
)
from integrations.maestro.state_file import (
    MaestroState,
    PhaseRecord,
    load_state,
    save_state,
    get_state_file_path,
    get_timestamp,
)
from integrations.maestro.state_bridge import (
    MaestroStateBridge,
    create_state_bridge,
)
from integrations.maestro.events import emit_maestro_phase, MAESTRO_MARKER_PREFIX


class TestPhaseMapping:
    """Tests for Auto-Claude stage to Maestro phase mapping."""

    def test_all_stages_have_mappings(self):
        """Every AutoClaudeStage should map to a MaestroPhase."""
        for stage in AutoClaudeStage:
            assert stage in STAGE_TO_PHASE, f"Missing mapping for {stage}"

    def test_planning_maps_to_1_1(self):
        """Planning stage maps to phase 1.1."""
        assert get_phase_for_stage("planning") == MaestroPhase.PLANNING_READ

    def test_discovery_maps_to_1_2(self):
        """Discovery stage maps to phase 1.2."""
        assert get_phase_for_stage("discovery") == MaestroPhase.PLANNING_DESIGN

    def test_clarification_maps_to_1_3(self):
        """Clarification stage maps to phase 1.3."""
        assert get_phase_for_stage("clarification") == MaestroPhase.PLANNING_CLARIFY

    def test_implementation_maps_to_2_2(self):
        """Implementation stage maps to phase 2.2."""
        assert get_phase_for_stage("implementation") == MaestroPhase.TDD_IMPLEMENT

    def test_test_writing_maps_to_2_1(self):
        """Test writing stage maps to phase 2.1."""
        assert get_phase_for_stage("test_writing") == MaestroPhase.TDD_WRITE_TESTS

    def test_test_running_maps_to_2_3(self):
        """Test running stage maps to phase 2.3."""
        assert get_phase_for_stage("test_running") == MaestroPhase.TDD_RUN_TESTS

    def test_test_fixing_maps_to_2_4(self):
        """Test fixing stage maps to phase 2.4."""
        assert get_phase_for_stage("test_fixing") == MaestroPhase.TDD_FIX_FAILURES

    def test_validation_maps_to_3_1(self):
        """Validation stage maps to phase 3.1."""
        assert get_phase_for_stage("validation") == MaestroPhase.VAL_VERIFY

    def test_review_maps_to_3_2(self):
        """Review stage maps to phase 3.2."""
        assert get_phase_for_stage("review") == MaestroPhase.VAL_REVIEW

    def test_refactoring_maps_to_3_3(self):
        """Refactoring stage maps to phase 3.3."""
        assert get_phase_for_stage("refactoring") == MaestroPhase.VAL_REFACTOR

    def test_documentation_maps_to_4_1(self):
        """Documentation stage maps to phase 4.1."""
        assert get_phase_for_stage("documentation") == MaestroPhase.DOC_EXAMPLES

    def test_commit_maps_to_5_1(self):
        """Commit stage maps to phase 5.1."""
        assert get_phase_for_stage("commit") == MaestroPhase.COMMIT

    def test_complete_maps_to_6_1(self):
        """Complete stage maps to phase 6.1."""
        assert get_phase_for_stage("complete") == MaestroPhase.COMPLETE_UPDATE

    def test_unknown_stage_returns_none(self):
        """Unknown stages return None."""
        assert get_phase_for_stage("unknown_stage") is None
        assert get_phase_for_stage("") is None
        assert get_phase_for_stage("INVALID") is None

    def test_case_insensitive_stage_lookup(self):
        """Stage lookup is case-insensitive."""
        assert get_phase_for_stage("PLANNING") == MaestroPhase.PLANNING_READ
        assert get_phase_for_stage("Planning") == MaestroPhase.PLANNING_READ
        assert get_phase_for_stage("IMPLEMENTATION") == MaestroPhase.TDD_IMPLEMENT

    def test_maestro_phase_values(self):
        """MaestroPhase enum has correct string values."""
        assert MaestroPhase.PLANNING_READ.value == "1.1"
        assert MaestroPhase.TDD_IMPLEMENT.value == "2.2"
        assert MaestroPhase.COMMIT.value == "5.1"
        assert MaestroPhase.COMPLETE_UPDATE.value == "6.1"

    def test_get_phase_info_returns_metadata(self):
        """get_phase_info returns PhaseInfo for valid phases."""
        info = get_phase_info(MaestroPhase.PLANNING_READ)
        assert info is not None
        assert isinstance(info, PhaseInfo)
        assert info.main_phase == 1
        assert info.sub_step == 1

    def test_get_phase_info_for_all_phases(self):
        """All mapped phases have info."""
        for phase in STAGE_TO_PHASE.values():
            info = get_phase_info(phase)
            assert info is not None, f"Missing info for {phase}"


class TestPhaseRecord:
    """Tests for PhaseRecord dataclass."""

    def test_empty_record(self):
        """Empty record has None values."""
        record = PhaseRecord()
        assert record.started is None
        assert record.completed is None

    def test_to_dict_empty(self):
        """Empty record serializes to empty dict."""
        record = PhaseRecord()
        assert record.to_dict() == {}

    def test_to_dict_with_started(self):
        """Record with started serializes correctly."""
        record = PhaseRecord(started="2026-01-29T10:00:00Z")
        assert record.to_dict() == {"started": "2026-01-29T10:00:00Z"}

    def test_to_dict_complete(self):
        """Complete record serializes all fields."""
        record = PhaseRecord(
            started="2026-01-29T10:00:00Z",
            completed="2026-01-29T10:30:00Z",
        )
        d = record.to_dict()
        assert d["started"] == "2026-01-29T10:00:00Z"
        assert d["completed"] == "2026-01-29T10:30:00Z"

    def test_from_dict_empty(self):
        """Empty dict creates empty record."""
        record = PhaseRecord.from_dict({})
        assert record.started is None
        assert record.completed is None

    def test_from_dict_complete(self):
        """Dict with all fields creates complete record."""
        record = PhaseRecord.from_dict({
            "started": "2026-01-29T10:00:00Z",
            "completed": "2026-01-29T10:30:00Z",
        })
        assert record.started == "2026-01-29T10:00:00Z"
        assert record.completed == "2026-01-29T10:30:00Z"


class TestMaestroState:
    """Tests for MaestroState dataclass."""

    def test_minimal_state(self):
        """State with only required fields."""
        state = MaestroState(sprint=42, type="backend")
        assert state.sprint == 42
        assert state.type == "backend"
        assert state.current_phase is None
        assert state.started is None
        assert state.phases == {}

    def test_to_dict(self):
        """State serializes to dict correctly."""
        state = MaestroState(
            sprint=42,
            type="backend",
            current_phase="2.3",
            started="2026-01-29T10:00:00Z",
            phases={
                "1.1": PhaseRecord(
                    started="2026-01-29T10:00:00Z",
                    completed="2026-01-29T10:05:00Z",
                ),
                "2.3": PhaseRecord(started="2026-01-29T10:30:00Z"),
            },
        )
        d = state.to_dict()
        assert d["sprint"] == 42
        assert d["type"] == "backend"
        assert d["current_phase"] == "2.3"
        assert d["started"] == "2026-01-29T10:00:00Z"
        assert "1.1" in d["phases"]
        assert d["phases"]["1.1"]["completed"] == "2026-01-29T10:05:00Z"

    def test_from_dict(self):
        """State deserializes from dict correctly."""
        data = {
            "sprint": 42,
            "type": "backend",
            "current_phase": "2.3",
            "started": "2026-01-29T10:00:00Z",
            "phases": {
                "1.1": {"started": "2026-01-29T10:00:00Z", "completed": "2026-01-29T10:05:00Z"},
            },
        }
        state = MaestroState.from_dict(data)
        assert state.sprint == 42
        assert state.type == "backend"
        assert state.current_phase == "2.3"
        assert "1.1" in state.phases
        assert state.phases["1.1"].completed == "2026-01-29T10:05:00Z"

    def test_from_dict_defaults(self):
        """Missing fields get defaults."""
        state = MaestroState.from_dict({})
        assert state.sprint == 0
        assert state.type == "fullstack"
        assert state.current_phase is None
        assert state.phases == {}


class TestStateFilePersistence:
    """Tests for state file I/O."""

    def test_get_state_file_path(self, tmp_path):
        """State file path follows pattern."""
        path = get_state_file_path(tmp_path, 42)
        assert path == tmp_path / ".claude" / "sprint-42-state.json"

    def test_save_creates_directory(self, tmp_path):
        """Save creates .claude directory if needed."""
        state = MaestroState(sprint=1, type="backend")
        assert save_state(tmp_path, state)
        assert (tmp_path / ".claude").exists()
        assert (tmp_path / ".claude" / "sprint-1-state.json").exists()

    def test_save_and_load_roundtrip(self, tmp_path):
        """Save then load returns equivalent state."""
        original = MaestroState(
            sprint=42,
            type="backend",
            current_phase="2.3",
            started="2026-01-29T10:00:00Z",
            phases={
                "1.1": PhaseRecord(
                    started="2026-01-29T10:00:00Z",
                    completed="2026-01-29T10:05:00Z",
                ),
            },
        )
        assert save_state(tmp_path, original)
        loaded = load_state(tmp_path, 42)

        assert loaded is not None
        assert loaded.sprint == 42
        assert loaded.type == "backend"
        assert loaded.current_phase == "2.3"
        assert "1.1" in loaded.phases
        assert loaded.phases["1.1"].completed == "2026-01-29T10:05:00Z"

    def test_load_missing_file_returns_none(self, tmp_path):
        """Loading non-existent file returns None."""
        result = load_state(tmp_path, 99)
        assert result is None

    def test_load_corrupt_json_returns_none(self, tmp_path):
        """Loading corrupt JSON returns None (graceful degradation)."""
        state_file = tmp_path / ".claude" / "sprint-1-state.json"
        state_file.parent.mkdir(parents=True)
        state_file.write_text("not valid json {{{")

        result = load_state(tmp_path, 1)
        assert result is None

    def test_load_empty_file_returns_none(self, tmp_path):
        """Loading empty file returns None."""
        state_file = tmp_path / ".claude" / "sprint-1-state.json"
        state_file.parent.mkdir(parents=True)
        state_file.write_text("")

        result = load_state(tmp_path, 1)
        assert result is None

    def test_atomic_write_on_error(self, tmp_path):
        """Failed write doesn't corrupt existing file."""
        state = MaestroState(sprint=1, type="backend", current_phase="1.1")
        save_state(tmp_path, state)

        # Verify original saved
        original_content = (tmp_path / ".claude" / "sprint-1-state.json").read_text()

        # Simulate write failure by making directory read-only
        # Skip this test on Windows where permissions work differently
        import platform
        if platform.system() != "Windows":
            import os
            import stat
            claude_dir = tmp_path / ".claude"
            original_mode = claude_dir.stat().st_mode
            try:
                claude_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)
                # This should fail
                new_state = MaestroState(sprint=1, type="frontend", current_phase="2.2")
                result = save_state(tmp_path, new_state)
                assert result is False
                # Restore permissions and verify original is intact
                claude_dir.chmod(original_mode)
                assert (tmp_path / ".claude" / "sprint-1-state.json").read_text() == original_content
            finally:
                claude_dir.chmod(original_mode)

    def test_get_timestamp_format(self):
        """Timestamp is ISO format with timezone."""
        ts = get_timestamp()
        assert "T" in ts
        # Should contain timezone info (Z or +00:00)
        assert ts.endswith("Z") or "+" in ts or "-" in ts[-6:]


class TestMaestroStateBridge:
    """Tests for MaestroStateBridge class."""

    @pytest.fixture
    def bridge(self, tmp_path):
        """Create a bridge for testing."""
        return MaestroStateBridge(tmp_path, sprint_number=1, sprint_type="backend")

    @pytest.mark.asyncio
    async def test_initialize_creates_state(self, bridge, tmp_path):
        """Initialize creates state file."""
        result = await bridge.initialize()
        assert result is True
        assert bridge.state is not None
        assert bridge.state.sprint == 1
        assert bridge.state.type == "backend"
        assert bridge.state.started is not None

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, bridge):
        """Initialize is idempotent."""
        await bridge.initialize()
        original_started = bridge.state.started
        await bridge.initialize()
        assert bridge.state.started == original_started

    @pytest.mark.asyncio
    async def test_transition_to_stage(self, bridge):
        """Transition to stage updates current phase."""
        await bridge.initialize()
        result = await bridge.transition_to_stage("planning")
        assert result is True
        assert bridge.current_phase == "1.1"

    @pytest.mark.asyncio
    async def test_transition_records_timestamp(self, bridge):
        """Transition records start timestamp."""
        await bridge.initialize()
        await bridge.transition_to_stage("planning")
        assert "1.1" in bridge.state.phases
        assert bridge.state.phases["1.1"].started is not None

    @pytest.mark.asyncio
    async def test_transition_completes_previous_phase(self, bridge):
        """Transitioning to new stage completes previous."""
        await bridge.initialize()
        await bridge.transition_to_stage("planning")
        await bridge.transition_to_stage("implementation")

        assert bridge.current_phase == "2.2"
        assert bridge.state.phases["1.1"].completed is not None

    @pytest.mark.asyncio
    async def test_transition_unknown_stage_returns_false(self, bridge):
        """Unknown stage returns False, no state change."""
        await bridge.initialize()
        await bridge.transition_to_stage("planning")
        original_phase = bridge.current_phase

        result = await bridge.transition_to_stage("unknown_stage")
        assert result is False
        assert bridge.current_phase == original_phase

    @pytest.mark.asyncio
    async def test_complete_current_phase(self, bridge):
        """Complete marks current phase as done."""
        await bridge.initialize()
        await bridge.transition_to_stage("planning")
        result = await bridge.complete_current_phase()

        assert result is True
        assert bridge.state.phases["1.1"].completed is not None

    @pytest.mark.asyncio
    async def test_complete_sprint(self, bridge):
        """Complete sprint transitions to 6.1."""
        await bridge.initialize()
        await bridge.transition_to_stage("planning")
        result = await bridge.complete_sprint()

        assert result is True
        assert "6.1" in bridge.state.phases

    @pytest.mark.asyncio
    async def test_get_phase_history(self, bridge):
        """Phase history returns all transitions."""
        await bridge.initialize()
        await bridge.transition_to_stage("planning")
        await bridge.transition_to_stage("implementation")

        history = bridge.get_phase_history()
        assert "1.1" in history
        assert "2.2" in history
        assert history["1.1"]["completed"] is not None

    @pytest.mark.asyncio
    async def test_callback_invoked_on_transition(self, bridge):
        """Callbacks are invoked on state change."""
        events = []

        def callback(state, phase, prev):
            events.append((phase, prev))

        bridge.on_state_change(callback)
        await bridge.initialize()
        await bridge.transition_to_stage("planning")

        assert len(events) == 1
        assert events[0][0] == "1.1"
        assert events[0][1] is None

    @pytest.mark.asyncio
    async def test_multiple_callbacks(self, bridge):
        """Multiple callbacks all invoked."""
        events1 = []
        events2 = []

        bridge.on_state_change(lambda s, p, prev: events1.append(p))
        bridge.on_state_change(lambda s, p, prev: events2.append(p))

        await bridge.initialize()
        await bridge.transition_to_stage("planning")

        assert len(events1) == 1
        assert len(events2) == 1

    @pytest.mark.asyncio
    async def test_async_callback_supported(self, bridge):
        """Async callbacks are awaited."""
        events = []

        async def async_callback(state, phase, prev):
            events.append(phase)

        bridge.on_state_change(async_callback)
        await bridge.initialize()
        await bridge.transition_to_stage("planning")

        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_callback_error_doesnt_break_transition(self, bridge):
        """Callback errors don't break state transitions."""
        def bad_callback(state, phase, prev):
            raise ValueError("Callback error")

        bridge.on_state_change(bad_callback)
        await bridge.initialize()
        result = await bridge.transition_to_stage("planning")

        # Should still succeed despite callback error
        assert result is True
        assert bridge.current_phase == "1.1"

    @pytest.mark.asyncio
    async def test_state_persists_across_instances(self, tmp_path):
        """State persists and loads in new bridge instance."""
        bridge1 = MaestroStateBridge(tmp_path, sprint_number=1, sprint_type="backend")
        await bridge1.initialize()
        await bridge1.transition_to_stage("implementation")

        # Create new bridge instance
        bridge2 = MaestroStateBridge(tmp_path, sprint_number=1, sprint_type="backend")
        # Access state property to trigger load
        assert bridge2.current_phase == "2.2"

    def test_is_active_false_initially(self, bridge):
        """is_active is False before initialization."""
        assert bridge.is_active is False

    @pytest.mark.asyncio
    async def test_is_active_true_after_transition(self, bridge):
        """is_active is True after phase transition."""
        await bridge.initialize()
        await bridge.transition_to_stage("planning")
        assert bridge.is_active is True


class TestCreateStateBridge:
    """Tests for create_state_bridge factory function."""

    def test_creates_bridge(self, tmp_path):
        """Factory creates configured bridge."""
        bridge = create_state_bridge(tmp_path, sprint_number=42, sprint_type="frontend")
        assert isinstance(bridge, MaestroStateBridge)
        assert bridge.sprint_number == 42
        assert bridge.sprint_type == "frontend"

    def test_default_sprint_type(self, tmp_path):
        """Default sprint type is fullstack."""
        bridge = create_state_bridge(tmp_path, sprint_number=1)
        assert bridge.sprint_type == "fullstack"


class TestMaestroEvents:
    """Tests for Maestro event emission."""

    def test_emit_maestro_phase_format(self, capsys):
        """Event has correct marker and JSON payload."""
        emit_maestro_phase(
            phase="2.3",
            previous_phase="2.2",
            sprint=42,
            sprint_type="backend",
        )
        captured = capsys.readouterr()
        assert MAESTRO_MARKER_PREFIX in captured.out

        # Parse the JSON payload
        json_str = captured.out.strip().replace(MAESTRO_MARKER_PREFIX, "")
        payload = json.loads(json_str)
        assert payload["phase"] == "2.3"
        assert payload["previous"] == "2.2"
        assert payload["sprint"] == 42
        assert payload["type"] == "backend"

    def test_emit_without_previous(self, capsys):
        """Event works without previous phase."""
        emit_maestro_phase(phase="1.1", sprint=1, sprint_type="backend")
        captured = capsys.readouterr()

        json_str = captured.out.strip().replace(MAESTRO_MARKER_PREFIX, "")
        payload = json.loads(json_str)
        assert payload["phase"] == "1.1"
        assert "previous" not in payload

    def test_marker_prefix_value(self):
        """Marker prefix is correct."""
        assert MAESTRO_MARKER_PREFIX == "__MAESTRO_STATE__:"


class TestStateBridgeWithEvents:
    """Tests for state bridge event emission integration."""

    @pytest.mark.asyncio
    async def test_bridge_emits_stdout_events(self, tmp_path, capsys):
        """Bridge emits events to stdout on transitions."""
        bridge = MaestroStateBridge(tmp_path, sprint_number=42, sprint_type="backend")

        # Add stdout event callback
        from integrations.maestro.events import emit_maestro_phase

        def emit_callback(state, phase, prev):
            emit_maestro_phase(
                phase=phase,
                previous_phase=prev,
                sprint=state.sprint,
                sprint_type=state.type,
            )

        bridge.on_state_change(emit_callback)

        await bridge.initialize()
        await bridge.transition_to_stage("planning")

        captured = capsys.readouterr()
        assert MAESTRO_MARKER_PREFIX in captured.out
        assert '"phase": "1.1"' in captured.out

"""Maestro Integration Module.

Provides state synchronization between Auto-Claude execution
and Maestro workflow phases.
"""

from .phase_mapping import (
    AutoClaudeStage,
    MaestroPhase,
    PhaseInfo,
    get_phase_for_stage,
    get_phase_info,
    STAGE_TO_PHASE,
)
from .state_file import (
    MaestroState,
    PhaseRecord,
    load_state,
    save_state,
    get_state_file_path,
    get_timestamp,
)
from .state_bridge import (
    MaestroStateBridge,
    create_state_bridge,
)
from .events import (
    emit_maestro_phase,
    MAESTRO_MARKER_PREFIX,
)

__all__ = [
    # Phase mapping
    "AutoClaudeStage",
    "MaestroPhase",
    "PhaseInfo",
    "get_phase_for_stage",
    "get_phase_info",
    "STAGE_TO_PHASE",
    # State file
    "MaestroState",
    "PhaseRecord",
    "load_state",
    "save_state",
    "get_state_file_path",
    "get_timestamp",
    # State bridge
    "MaestroStateBridge",
    "create_state_bridge",
    # Events
    "emit_maestro_phase",
    "MAESTRO_MARKER_PREFIX",
]

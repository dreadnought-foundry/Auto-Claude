"""Maestro state change events.

Emits structured events to stdout for frontend parsing.
Protocol: __MAESTRO_STATE__:{"phase":"2.3","previous":"2.2",...}
"""

import json
from typing import Optional

# Maestro event marker for stdout protocol
MAESTRO_MARKER_PREFIX = "__MAESTRO_STATE__:"


def emit_maestro_phase(
    phase: str,
    previous_phase: Optional[str] = None,
    sprint: int = 0,
    sprint_type: str = "fullstack",
) -> None:
    """
    Emit a Maestro state change event to stdout.

    Protocol: __MAESTRO_STATE__:{"phase":"2.3","previous":"2.2",...}

    Args:
        phase: Current Maestro phase ID (e.g., "1.1", "2.3")
        previous_phase: Previous phase ID (if any)
        sprint: Sprint number
        sprint_type: Sprint type (backend, frontend, etc.)
    """
    payload: dict = {
        "phase": phase,
        "sprint": sprint,
        "type": sprint_type,
    }

    if previous_phase:
        payload["previous"] = previous_phase

    try:
        print(f"{MAESTRO_MARKER_PREFIX}{json.dumps(payload)}", flush=True)
    except (OSError, UnicodeEncodeError):
        pass  # Silent on I/O failure

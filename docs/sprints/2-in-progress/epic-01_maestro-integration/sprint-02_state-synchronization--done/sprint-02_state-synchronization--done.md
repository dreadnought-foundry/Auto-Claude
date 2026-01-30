---
sprint: 2
title: "State Synchronization"
type: backend
epic: 1
status: done
created: 2026-01-29T17:03:42Z
started: 2026-01-29T17:26:49Z
completed: 2026-01-30
hours: null
workflow_version: "3.5.0"



---

# Sprint 2: State Synchronization

## Overview

| Field | Value |
|-------|-------|
| Sprint | 2 |
| Title | State Synchronization |
| Type | backend |
| Epic | 1 |
| Status | Planning |
| Created | 2026-01-29 |
| Started | - |
| Completed | - |

## Goal

Bridge Auto-Claude task state with Maestro workflow phases for unified progress tracking.

## Background

Auto-Claude and Maestro each track work state independently. Auto-Claude uses stages like "planning", "implementation", "validation". Maestro uses phases like "1.1", "2.3", "5.1". Without synchronization, users can't answer "what phase is my work in?" consistently.

This sprint creates a state bridge that maps Auto-Claude stages to Maestro phases, enabling:
- `/sprint-status` to show Maestro phase alongside Auto-Claude status
- Audit trail of phase transitions with timestamps
- Foundation for future phase enforcement

**Prerequisite**: Sprint Type Foundation (completed on `feature/maestro-sprint-types` branch)

## Requirements

### Functional Requirements

- [ ] Create MaestroStateBridge module
- [ ] Map Auto-Claude stages to Maestro phases
- [ ] Create/update Maestro state file on stage transitions
- [ ] Record timestamps for each phase transition
- [ ] Emit events on state changes for observability
- [ ] Support reading state from file on restart

### Non-Functional Requirements

- [ ] State sync is async and non-blocking
- [ ] State file format compatible with Maestro's `.claude/sprint-state.json`
- [ ] Graceful degradation if state file is missing/corrupt

## Dependencies

- **Sprints**: Sprint Type Foundation (DONE - on `feature/maestro-sprint-types`)
- **External**: Auto-Claude core event system

## Scope

### In Scope

- State bridge module
- Phase mapping configuration
- State file read/write
- Event emission on transitions
- Unit tests

### Out of Scope

- Enforcement of phase order (advisory only for now)
- UI visualization of phases
- Integration with Linear

## Technical Approach

1. Create `apps/backend/integrations/maestro/state_bridge.py`
2. Create `apps/backend/integrations/maestro/phase_mapping.py` with stage→phase map
3. Hook into Auto-Claude's stage transition events
4. Write state to `.claude/sprint-{N}-state.json` in Maestro format

## Phase Mapping

| Auto-Claude Stage | Maestro Phase | Description |
|-------------------|---------------|-------------|
| planning | 1.1 | Read sprint file |
| discovery | 1.2 | Architecture design |
| clarification | 1.3 | Clarify requirements |
| test_writing | 2.1 | Write tests |
| implementation | 2.2 | Implement feature |
| test_running | 2.3 | Run tests |
| test_fixing | 2.4 | Fix failures |
| validation | 3.1 | Verify migrations |
| review | 3.2 | Quality review |
| refactoring | 3.3 | Refactor code |
| documentation | 4.1 | Update docs |
| commit | 5.1 | Stage and commit |
| complete | 6.1 | Sprint complete |

## Tasks

### Phase 1: Planning
- [ ] Review Auto-Claude event system
- [ ] Identify all stage transition points
- [ ] Design state file format

### Phase 2: Implementation
- [ ] Write tests for state bridge
- [ ] Write tests for phase mapping
- [ ] Implement MaestroStateBridge class
- [ ] Implement phase mapping
- [ ] Implement state file read/write
- [ ] Hook into stage transition events
- [ ] Add event emission

### Phase 3: Validation
- [ ] Test with full spec execution
- [ ] Test state persistence across restarts
- [ ] Test corrupt/missing state file handling
- [ ] Run Auto-Claude test suite

### Phase 4: Documentation
- [ ] Document phase mapping
- [ ] Document state file format
- [ ] Add integration guide

## Acceptance Criteria

- [ ] State file created when spec starts
- [ ] Phase updates on each Auto-Claude stage transition
- [ ] Timestamps recorded for each phase
- [ ] State persists across agent restarts
- [ ] Events emitted for observability
- [ ] Graceful handling of missing/corrupt state
- [ ] All tests passing with 85% coverage
- [ ] Code reviewed

## State File Format

```json
{
  "sprint": 42,
  "type": "backend",
  "current_phase": "2.3",
  "started": "2026-01-29T10:00:00Z",
  "phases": {
    "1.1": {"started": "2026-01-29T10:00:00Z", "completed": "2026-01-29T10:05:00Z"},
    "1.2": {"started": "2026-01-29T10:05:00Z", "completed": "2026-01-29T10:20:00Z"},
    "2.1": {"started": "2026-01-29T10:20:00Z", "completed": "2026-01-29T10:45:00Z"},
    "2.2": {"started": "2026-01-29T10:45:00Z", "completed": "2026-01-29T12:30:00Z"},
    "2.3": {"started": "2026-01-29T12:30:00Z", "completed": null}
  }
}
```

## Notes

Created: 2026-01-29
Migrated from: maestro Sprint 10
Target Files:
- `apps/backend/integrations/maestro/state_bridge.py` (new)
- `apps/backend/integrations/maestro/phase_mapping.py` (new)
- `apps/backend/integrations/maestro/state_file.py` (new)
- `apps/backend/core/events.py` (modify)

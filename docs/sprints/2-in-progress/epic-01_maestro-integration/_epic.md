---
epic: 1
title: "Maestro Integration"
status: planning
created: 2026-01-29
started: null
completed: null
---

# Epic 1: Maestro Integration

## Overview

Integrate Maestro's workflow enforcement capabilities into Auto-Claude's autonomous multi-agent framework. This creates a "Conductor and Orchestra" model where Maestro defines WHAT gets built and HOW GOOD it needs to be, while Auto-Claude handles WHO builds it and executes autonomously with parallel agents.

**Key Value**: Auto-Claude excels at execution (parallel agents, autonomous builds). Maestro excels at process enforcement (quality gates, step progression, postmortems). Together they create a system that builds fast AND builds right.

## Vision Documents

See the original proposal in the maestro repository:
- Vision: https://github.com/dreadnought-foundry/claude-maestro/blob/main/docs/proposals/maestro-auto-claude-vision.md
- Technical Proposal: https://github.com/dreadnought-foundry/claude-maestro/blob/main/docs/proposals/maestro-auto-claude-integration-proposal.md

## Success Criteria

- [ ] Auto-Claude specs accept `type` field with 6 sprint types
- [ ] Coverage validation uses type-specific thresholds (spike=0%, backend=85%)
- [ ] Maestro's 9-item pre-flight checklist integrated into Auto-Claude QA pipeline
- [ ] Workflow state syncs between Auto-Claude stages and Maestro phases
- [ ] Postmortems auto-generated after spec completion
- [ ] Optional epic/sprint hierarchy available in Auto-Claude

## Sprints

| Sprint | Title | Status | Depends On |
|--------|-------|--------|------------|
| 0 | Sprint Type Foundation | **DONE** | - |
| 1 | Quality Gate Integration | planned | Sprint 0 |
| 2 | State Synchronization | planned | Sprint 0 |
| 3 | Postmortem Generation | planned | Sprint 2 |
| 4 | Epic Sprint Hierarchy | planned | Sprint 0 |

## Execution Plan

```
Phase 0 (COMPLETE):
  └── Sprint Type Foundation [DONE - 10.2h]
      Branch: feature/maestro-sprint-types

Phase 1 (Parallel - ready now):
  ├── Sprint 1: Quality Gate Integration [~10h]
  ├── Sprint 2: State Synchronization    [~8h]
  └── Sprint 4: Epic Sprint Hierarchy    [~8h]

Phase 2 (Sequential - after Sprint 2):
  └── Sprint 3: Postmortem Generation    [~8h]
```

**Optimal path:** ~10h (parallel) + 8h = **~18h remaining**

## Completed Work

### Sprint Type Foundation (DONE)
Implemented on `feature/maestro-sprint-types` branch before epic migration.

- **Branch**: `feature/maestro-sprint-types`
- **Commit**: 4be5314f
- **Duration**: 10.2 hours
- **Files**:
  - `apps/backend/spec/types.py` - Type enum, coverage thresholds
  - `apps/backend/spec_contract.json` - Schema extension
  - `tests/test_sprint_types.py` - 43 unit tests

## Notes

Created: 2026-01-29
Migrated from: github.com/dreadnought-foundry/claude-maestro (Epic 2)

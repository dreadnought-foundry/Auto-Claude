---
sprint: 4
title: "Epic Sprint Hierarchy"
type: backend
epic: 1
status: planning
created: 2026-01-29T17:03:42Z
started: null
completed: null
hours: null
workflow_version: "3.5.0"
---

# Sprint 4: Epic Sprint Hierarchy

## Overview

| Field | Value |
|-------|-------|
| Sprint | 4 |
| Title | Epic Sprint Hierarchy |
| Type | backend |
| Epic | 1 |
| Status | Planning |
| Created | 2026-01-29 |
| Started | - |
| Completed | - |

## Goal

Add optional Maestro-style epic/sprint work organization to Auto-Claude, enabling self-contained project management without external tools.

## Background

Auto-Claude currently relies on Linear for work organization. Some users prefer a self-contained system without external dependencies. Maestro's epic/sprint hierarchy provides:
- Epics group related specs
- Registry tracks all completed work
- Epic auto-completes when all specs done
- Searchable history of past work

This is an optional feature - users can continue using Linear or other external tools.

## Requirements

### Functional Requirements

- [ ] Add epic field to spec schema
- [ ] Create epic metadata file format
- [ ] Create registry for tracking completed specs
- [ ] Detect when epic is complete (all specs done)
- [ ] CLI commands: epic-new, epic-list, epic-status, epic-complete
- [ ] Link specs to epics via `--epic=N` flag

### Non-Functional Requirements

- [ ] Epic/sprint is optional - works without it
- [ ] Compatible with existing Linear integration
- [ ] Registry file is human-readable JSON

## Dependencies

- **Sprints**: Sprint Type Foundation (DONE - on `feature/maestro-sprint-types`)
- **External**: None

## Scope

### In Scope

- Epic schema and metadata files
- Registry for completed work
- Epic lifecycle management
- CLI commands for epic operations
- Unit tests

### Out of Scope

- Migration from Linear (manual process)
- Epic analytics/reporting (future)
- Epic templates

## Technical Approach

1. Create `apps/backend/spec/epic.py` with Epic class
2. Create `apps/backend/spec/registry.py` for work registry
3. Create `apps/backend/spec/epic_lifecycle.py` for completion detection
4. Add CLI commands in `apps/backend/cli/epic_commands.py`
5. Store epics in `.auto-claude/epics/` directory

## Tasks

### Phase 1: Planning
- [ ] Design epic file format
- [ ] Design registry schema
- [ ] Plan CLI command interface

### Phase 2: Implementation
- [ ] Write tests for Epic class
- [ ] Write tests for registry
- [ ] Write tests for epic lifecycle
- [ ] Implement Epic class
- [ ] Implement registry read/write
- [ ] Implement epic completion detection
- [ ] Add --epic flag to spec creation
- [ ] Implement CLI commands:
  - [ ] epic-new
  - [ ] epic-list
  - [ ] epic-status
  - [ ] epic-complete

### Phase 3: Validation
- [ ] Test full epic lifecycle
- [ ] Test epic completion detection
- [ ] Test without epic (standalone specs)
- [ ] Run Auto-Claude test suite

### Phase 4: Documentation
- [ ] Document epic file format
- [ ] Document CLI commands
- [ ] Add examples and use cases
- [ ] Update Auto-Claude README

## Acceptance Criteria

- [ ] Specs can be grouped into epics via `--epic=N`
- [ ] Registry tracks all completed specs
- [ ] Epic auto-detects completion when all specs done
- [ ] CLI commands work: epic-new, epic-list, epic-status, epic-complete
- [ ] Works without epic (standalone specs still work)
- [ ] All tests passing with 85% coverage
- [ ] Code reviewed

## Epic File Format

```markdown
# Epic {N}: {Title}

## Overview
{Description of the strategic initiative}

## Success Criteria
- [ ] {Measurable outcome}

## Specs
| Spec | Title | Status |
|------|-------|--------|
| 42 | User Notifications | done |
| 43 | Email Integration | in-progress |
| 44 | Push Notifications | planned |

## Notes
Created: {date}
```

## Registry Format

```json
{
  "version": "1.0",
  "epics": {
    "1": {
      "title": "User Engagement",
      "status": "in-progress",
      "specs": [42, 43, 44],
      "completedSpecs": 1,
      "created": "2026-01-15",
      "completed": null
    }
  },
  "specs": {
    "42": {
      "title": "User Notifications",
      "type": "backend",
      "epic": 1,
      "status": "done",
      "created": "2026-01-20",
      "completed": "2026-01-22",
      "hours": 6.5
    }
  },
  "counters": {
    "nextEpic": 2,
    "nextSpec": 45
  }
}
```

## Notes

Created: 2026-01-29
Migrated from: maestro Sprint 12
Target Files:
- `apps/backend/spec/epic.py` (new)
- `apps/backend/spec/registry.py` (new)
- `apps/backend/spec/epic_lifecycle.py` (new)
- `apps/backend/cli/epic_commands.py` (new)
- `.auto-claude/registry.json` (new)
- `.auto-claude/epics/` (new directory)

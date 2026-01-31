---
epic: 2
title: "Unified Pipeline Architecture"
status: planning
created: 2026-01-30
started: null
completed: null
---

# Epic 2: Unified Pipeline Architecture

## Overview

Unify Maestro and Auto Claude's state systems into a single format, then integrate Maestro as an alternative pipeline option in Auto Claude's Kanban board. This enables token-efficient guided execution while using the same UI, tools, and quality gates.

## Problem Statement

Currently two separate state systems exist:
- **Maestro**: `~/.claude/sprint-state.json` (user-level, single global state)
- **Auto Claude**: `.auto-claude/specs/` (project-level, per-task state)

This prevents integration because:
1. Maestro can't track multiple projects simultaneously
2. State formats are incompatible
3. No sync mechanism exists

## Solution

1. **Sprint 5**: Create unified state format, make it project-level
2. **Sprint 6**: Add Maestro as Kanban pipeline option using unified state

## Success Criteria

- [ ] Single state format used by both Maestro and Auto Claude
- [ ] State stored per-project (`.claude/` or `.auto-claude/`)
- [ ] Maestro works standalone without Auto Claude
- [ ] Auto Claude works standalone without Maestro
- [ ] Kanban can display and manage Maestro pipeline tasks
- [ ] Multiple projects can have active sprints simultaneously
- [ ] Quality gates work for both pipeline types

## Sprints

| Sprint | Title | Type | Status |
|--------|-------|------|--------|
| 5 | Unified State System | backend | planning |
| 6 | Kanban Pipeline Integration | fullstack | planning |

## Architecture

```
Unified State: {project}/.claude/task-state.json
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ Maestro         │ │ Auto Claude     │ │ Both Together   │
│ (CLI only)      │ │ (Desktop app)   │ │                 │
├─────────────────┤ ├─────────────────┤ ├─────────────────┤
│ /sprint-start   │ │ Kanban UI       │ │ Kanban shows    │
│ /sprint-next    │ │ Autonomous      │ │ Maestro tasks   │
│ /sprint-status  │ │ pipeline        │ │ /sprint-next in │
│                 │ │                 │ │ Agent Terminal  │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

## Dependencies

- None (foundational work)

## Risks

| Risk | Mitigation |
|------|------------|
| Migration complexity | Provide backward compatibility, auto-migrate old state |
| Breaking existing workflows | Extensive testing, fallback to old format |
| State sync conflicts | Atomic writes, file locking |

## Notes

- Sprint 5 can ship independently - improves Maestro even without Kanban integration
- Sprint 6 depends on Sprint 5 completing first
- Both sprints should maintain backward compatibility

Created: 2026-01-30

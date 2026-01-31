# Sprint 5: Unified State System

## Overview

| Field | Value |
|-------|-------|
| Sprint | 5 |
| Title | Unified State System |
| Epic | 2 - Unified Pipeline Architecture |
| Status | Planning |
| Type | backend |
| Created | 2026-01-30 |
| Started | - |
| Completed | - |

## Goal

Create a unified state format that both Maestro and Auto Claude can read/write, stored per-project, enabling both systems to operate standalone or together.

## Background

### Current State (Two Systems)

**Maestro:**
```
~/.claude/sprint-state.json  (user-level, ONE global state)
├── sprint: 5
├── phase: 2
├── step: "2.3"
├── completedSteps: [...]
└── timestamps
```

**Auto Claude:**
```
.auto-claude/specs/XXX/
├── spec.md
├── implementation_plan.json  (subtasks, phase)
├── qa_report.md
└── registry.json
```

### Problems

1. Maestro is user-level → can't track multiple projects
2. Different formats → no interoperability
3. Different granularity → Maestro has steps, Auto Claude has phases

### Solution

One unified format, stored per-project:

```json
{
  "version": "1.0",
  "tasks": [{
    "id": "005",
    "title": "Add user authentication",
    "pipeline": "maestro",
    "phase": "implementation",
    "step": "2.3",
    "status": "in_progress",
    "completedSteps": ["1.1", "1.2", "2.1", "2.2"],
    "sprintFile": "docs/sprints/sprint-05_user-auth/sprint.md",
    "created": "2026-01-30T10:00:00Z",
    "started": "2026-01-30T10:05:00Z"
  }]
}
```

## Requirements

### Functional Requirements

- [ ] Define unified state schema supporting both pipelines
- [ ] Migrate Maestro to use project-level state (`{project}/.claude/task-state.json`)
- [ ] Migrate Auto Claude to use unified format
- [ ] Maestro works standalone (no Auto Claude required)
- [ ] Auto Claude works standalone (no Maestro required)
- [ ] Multiple projects can have active tasks simultaneously
- [ ] Backward compatibility with existing state files

### Non-Functional Requirements

- [ ] Atomic writes to prevent corruption
- [ ] Schema versioning for future migrations
- [ ] Sub-second read/write performance
- [ ] File locking for concurrent access

## Dependencies

- **Sprints**: None (foundational)
- **External**: None

## Scope

### In Scope

- Unified state schema design
- Maestro script modifications for project-level state
- Auto Claude backend modifications for unified format
- Migration utilities for existing state
- Project root detection logic

### Out of Scope

- Kanban UI changes (Sprint 6)
- Pipeline selector UI (Sprint 6)
- New Maestro phases or steps
- Auto Claude autonomous pipeline changes

## Technical Approach

### Unified State Schema

```typescript
interface UnifiedTaskState {
  version: "1.0";
  projectRoot: string;
  tasks: Task[];
}

interface Task {
  id: string;                          // Unique task/sprint ID
  title: string;                       // Task description
  pipeline: "autonomous" | "maestro";  // Execution mode

  // Status tracking
  status: "pending" | "in_progress" | "blocked" | "completed" | "failed";
  phase: string;                       // Current phase name
  step?: string;                       // Maestro step (e.g., "2.3")
  completedSteps?: string[];           // Maestro completed steps

  // Subtasks (for autonomous pipeline)
  subtasks?: Subtask[];

  // References
  sprintFile?: string;                 // Path to sprint.md
  specDir?: string;                    // Path to spec directory

  // Timestamps
  created: string;
  started?: string;
  completed?: string;

  // Metadata
  sprintType?: SprintType;             // fullstack, backend, etc.
  coverageThreshold?: number;
}
```

### State Location

```
BEFORE:
~/.claude/
├── sprint-state.json       # Global (problem!)
└── sprint-steps.json       # Workflow definition

AFTER:
~/.claude/
└── sprint-steps.json       # Workflow definition (stays global)

{project}/
└── .claude/
    └── task-state.json     # Per-project unified state
```

### Project Detection

```python
def find_project_root(start_path: Path) -> Optional[Path]:
    """Walk up looking for project markers."""
    markers = ['.git', '.auto-claude', 'package.json', 'pyproject.toml', '.claude']
    current = start_path.resolve()
    while current != current.parent:
        if any((current / marker).exists() for marker in markers):
            return current
        current = current.parent
    return None

def get_state_path(project_root: Optional[Path] = None) -> Path:
    """Get unified state path for project."""
    if project_root is None:
        project_root = find_project_root(Path.cwd())
    if project_root:
        state_dir = project_root / '.claude'
        state_dir.mkdir(exist_ok=True)
        return state_dir / 'task-state.json'
    # Fallback for non-project contexts
    return Path.home() / '.claude' / 'task-state.json'
```

### Migration Strategy

1. **Read old format** → Detect if old Maestro state exists
2. **Convert to unified** → Map fields to new schema
3. **Write new format** → Atomic write to new location
4. **Keep old as backup** → Rename with `.backup` suffix

### Components to Modify

**Maestro (`~/.claude/scripts/`):**
| File | Changes |
|------|---------|
| `sprint_lifecycle.py` | Use `get_state_path()`, unified schema |
| `sprint_state.py` | New file - unified state operations |

**Auto Claude (`apps/backend/`):**
| File | Changes |
|------|---------|
| `spec/types.py` | Add `UnifiedTaskState` types |
| `spec/registry.py` | Read/write unified format |
| `qa/maestro_adapter.py` | Read from unified state |

**Auto Claude (`apps/frontend/`):**
| File | Changes |
|------|---------|
| `src/main/agent/agent-state.ts` | Read unified format |
| `src/renderer/stores/task-store.ts` | Map unified → UI state |

## Tasks

### Phase 1: Schema Design
- [ ] Finalize unified state schema (TypeScript + Python types)
- [ ] Document field mappings from both old formats
- [ ] Design migration utilities

### Phase 2: Maestro Migration
- [ ] Create `sprint_state.py` with unified state operations
- [ ] Add `find_project_root()` utility
- [ ] Modify `sprint_lifecycle.py` to use new state
- [ ] Update all Maestro commands to use project-level state
- [ ] Test: Maestro standalone with new format

### Phase 3: Auto Claude Migration
- [ ] Add unified types to `spec/types.py`
- [ ] Modify `registry.py` to read/write unified format
- [ ] Update `maestro_adapter.py` for new state location
- [ ] Update frontend state reading
- [ ] Test: Auto Claude standalone with new format

### Phase 4: Backward Compatibility
- [ ] Implement migration utility for old Maestro state
- [ ] Implement migration utility for old Auto Claude specs
- [ ] Auto-detect and migrate on first read
- [ ] Test: Migration from both old formats

### Phase 5: Testing & Validation
- [ ] Test: Maestro standalone (no Auto Claude)
- [ ] Test: Auto Claude standalone (no Maestro)
- [ ] Test: Multiple projects with active tasks
- [ ] Test: Concurrent access (file locking)
- [ ] Test: Corruption recovery

## Acceptance Criteria

- [ ] Unified state schema documented and implemented
- [ ] Maestro reads/writes `{project}/.claude/task-state.json`
- [ ] Auto Claude reads/writes same unified state
- [ ] `/sprint-start` works in any project directory
- [ ] Can have sprints active in multiple projects simultaneously
- [ ] Old state files auto-migrate on first access
- [ ] Maestro works without Auto Claude installed
- [ ] Auto Claude works without Maestro workflow
- [ ] All existing tests pass
- [ ] New tests cover unified state operations

## Open Questions

1. Should we support multiple active tasks per project? → **Yes**, unified format is an array
2. Where to store workflow definition (sprint-steps.json)? → **Keep global** in `~/.claude/`
3. How to handle conflicts if both systems write simultaneously? → **File locking** + atomic writes

## Notes

- This sprint enables Sprint 6 (Kanban integration) but is valuable standalone
- Backward compatibility is critical - don't break existing workflows
- Coverage threshold: 85% (backend sprint type)

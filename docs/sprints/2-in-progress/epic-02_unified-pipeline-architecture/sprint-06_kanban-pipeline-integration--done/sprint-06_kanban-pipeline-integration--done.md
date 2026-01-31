---
sprint: 6
title: "Kanban Pipeline Integration"
epic: 2
status: done
created: 2026-01-31T08:11:02Z
started: 2026-01-31T08:11:02Z
completed: 2026-01-31
hours: null
workflow_version: "3.5.0"


---

# Sprint 6: Kanban Pipeline Integration

## Overview

| Field | Value |
|-------|-------|
| Sprint | 6 |
| Title | Kanban Pipeline Integration |
| Epic | 2 - Unified Pipeline Architecture |
| Status | Planning |
| Type | fullstack |
| Created | 2026-01-30 |
| Started | - |
| Completed | - |

## Goal

Add Maestro as an alternative pipeline option in Auto Claude's Kanban board, allowing users to choose between autonomous execution (high token cost) or guided Maestro workflow (low token cost) while using the same UI.

## Background

With Sprint 5 complete, we have a unified state format that both Maestro and Auto Claude can read/write. This sprint adds the UI and execution layer to let users:

1. Create Kanban tasks with "Maestro" pipeline type
2. See Maestro tasks on the Kanban board with visual distinction
3. Execute Maestro workflow via Agent Terminal
4. Have quality gates enforced before completion

## Requirements

### Functional Requirements

- [ ] Pipeline type selector in task creation dialog (Autonomous / Maestro)
- [ ] Maestro tasks display on Kanban board with distinct visual indicator (🎯)
- [ ] Clicking Maestro task opens Agent Terminal with sprint context
- [ ] Kanban card progress reflects Maestro phase/step from unified state
- [ ] Quality gates run via `maestro_adapter.py` before task completion
- [ ] Autonomous pipeline behavior unchanged

### Non-Functional Requirements

- [ ] State sync < 2 second latency (file watcher)
- [ ] No performance regression for autonomous tasks
- [ ] Responsive UI during state updates

## Dependencies

- **Sprints**: Sprint 5 (Unified State System) - REQUIRED
- **External**: None

## Scope

### In Scope

- Pipeline type selector UI
- Visual indicators on Kanban cards
- File watcher for unified state changes
- Agent Terminal context injection
- Quality gate integration
- Phase-to-column mapping

### Out of Scope

- Changes to Maestro workflow steps
- Changes to autonomous pipeline execution
- New quality gate criteria
- Mobile/web UI

## Technical Approach

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Kanban Board UI                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ Planning │  │ Building │  │ Complete │              │
│  │          │  │          │  │          │              │
│  │ [Task A] │  │ [Task B] │  │          │              │
│  │ 🤖 Auto  │  │ 🎯 Maestro│  │          │              │
│  └──────────┘  └──────────┘  └──────────┘              │
└─────────────────────────────────────────────────────────┘
         │                               │
         ▼                               ▼
┌─────────────────┐             ┌─────────────────┐
│ Autonomous      │             │ Maestro         │
│ Executor        │             │ Executor        │
├─────────────────┤             ├─────────────────┤
│ spawnProcess()  │             │ openTerminal()  │
│ Python agents   │             │ Context inject  │
│ Auto phases     │             │ Human gates     │
└─────────────────┘             └─────────────────┘
         │                               │
         └───────────────┬───────────────┘
                         ▼
              ┌─────────────────┐
              │ Unified State   │
              │ .claude/        │
              │ task-state.json │
              └─────────────────┘
```

### Phase-to-Column Mapping

| Maestro Phase | Maestro Steps | Kanban Column |
|---------------|---------------|---------------|
| 1 - Planning | 1.1-1.4 | `planning` |
| 2 - Implementation | 2.1-2.4 | `in_progress` |
| 3 - Validation | 3.1-3.4 | `in_progress` |
| 4 - Documentation | 4.1 | `ai_review` |
| 5 - Commit | 5.1-5.2 | `ai_review` |
| 6 - Completion | 6.1-6.4 | `human_review` → `done` |

### Key Components

#### 1. Frontend Types (`src/shared/types/`)

```typescript
// project.ts
export type PipelineType = 'autonomous' | 'maestro';

export interface Task {
  // ... existing fields
  pipelineType: PipelineType;
  maestroPhase?: string;
  maestroStep?: string;
}
```

#### 2. Task Creation Dialog (`src/renderer/components/task/`)

Add pipeline selector:
```tsx
<RadioGroup value={pipelineType} onChange={setPipelineType}>
  <Radio value="autonomous" label="🤖 Autonomous" description="AI agents handle everything" />
  <Radio value="maestro" label="🎯 Maestro" description="Guided step-by-step workflow" />
</RadioGroup>
```

#### 3. Kanban Card (`src/renderer/components/kanban/`)

Visual indicator:
```tsx
<div className="pipeline-badge">
  {task.pipelineType === 'maestro' ? '🎯' : '🤖'}
</div>

{task.pipelineType === 'maestro' && (
  <div className="maestro-progress">
    Phase {task.maestroPhase} • Step {task.maestroStep}
  </div>
)}
```

#### 4. State Watcher (`src/main/agent/maestro-watcher.ts`)

```typescript
import { watch } from 'fs';

export function watchUnifiedState(projectPath: string, callback: (state: UnifiedTaskState) => void) {
  const statePath = path.join(projectPath, '.claude', 'task-state.json');

  watch(statePath, { persistent: true }, async (eventType) => {
    if (eventType === 'change') {
      const state = await readUnifiedState(statePath);
      callback(state);
    }
  });
}
```

#### 5. Maestro Executor (`src/main/agent/maestro-executor.ts`)

```typescript
export async function startMaestroExecution(taskId: string, projectPath: string) {
  // 1. Get task from unified state
  const task = await getTaskFromUnifiedState(taskId, projectPath);

  // 2. Open Agent Terminal
  const terminalId = await createTerminal(projectPath);

  // 3. Inject context
  await injectMaestroContext(terminalId, {
    sprintFile: task.sprintFile,
    currentPhase: task.phase,
    currentStep: task.step,
  });

  // 4. Focus terminal
  focusTerminal(terminalId);
}
```

#### 6. Quality Gate Integration

When Maestro task moved to `done`:
```typescript
async function onTaskMoveToDone(task: Task) {
  if (task.pipelineType === 'maestro') {
    const result = await runMaestroQualityGate(task);
    if (!result.passed) {
      // Block move, show failure message
      return { blocked: true, message: result.failureMessage };
    }
  }
  // Allow move
  return { blocked: false };
}
```

## Tasks

### Phase 1: Types & State Integration
- [ ] Add `PipelineType` to shared types
- [ ] Update task interfaces with Maestro fields
- [ ] Create state watcher for unified state file
- [ ] Add IPC channels for Maestro state updates

### Phase 2: Task Creation UI
- [ ] Add pipeline selector to TaskCreateDialog
- [ ] Create sprint file when Maestro task created
- [ ] Initialize unified state entry
- [ ] Test: Creating Maestro vs Autonomous tasks

### Phase 3: Kanban Display
- [ ] Add pipeline badge to Kanban cards (🤖/🎯)
- [ ] Show Maestro phase/step progress on cards
- [ ] Implement phase-to-column mapping
- [ ] Update card position when unified state changes
- [ ] Test: Cards move correctly with Maestro progress

### Phase 4: Execution
- [ ] Create `maestro-executor.ts`
- [ ] Implement terminal context injection
- [ ] Handle "Start" button click for Maestro tasks
- [ ] Test: Clicking Maestro task opens terminal with context

### Phase 5: Quality Gates
- [ ] Integrate quality gate check on move to "done"
- [ ] Show failure message if gates fail
- [ ] Block completion until gates pass
- [ ] Test: Quality gates enforce coverage threshold

### Phase 6: Testing & Polish
- [ ] Test autonomous pipeline unchanged
- [ ] Test Maestro pipeline end-to-end
- [ ] Test mixed board (both pipeline types)
- [ ] Performance testing (state sync latency)
- [ ] UI polish and edge cases

## Acceptance Criteria

- [ ] Can create Kanban task with "Maestro" pipeline type
- [ ] Maestro tasks show 🎯 badge, autonomous show 🤖
- [ ] Maestro task cards display current phase and step
- [ ] Clicking "Start" on Maestro task opens Agent Terminal
- [ ] Terminal has sprint context injected (file path, current step)
- [ ] Kanban card moves columns as Maestro advances phases
- [ ] Quality gates block completion if checks fail
- [ ] Autonomous pipeline behavior completely unchanged
- [ ] All tests passing
- [ ] Code reviewed

## Open Questions

1. ~~Should Maestro tasks auto-create sprint files?~~ → **Yes**, from task description
2. Should we show step-level detail in card? → **Yes**, show "Phase 2 • Step 2.3"
3. What happens if user drags Maestro card manually? → **Allow it**, but warn if skipping phases

## Notes

- This sprint depends entirely on Sprint 5 (unified state)
- Keep autonomous pipeline completely isolated from changes
- Coverage threshold: 75% (fullstack sprint type)
- Consider future enhancement: "Convert to Maestro" for stuck autonomous tasks

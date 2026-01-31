---
sprint: 7
title: "Maestro Auto-Start Terminal Integration"
type: fullstack
epic: null
status: in-progress
created: 2026-01-31T14:00:48Z
started: 2026-01-31T14:02:00Z
completed: null
hours: null
workflow_version: "3.1.0"

---

# Sprint 7: Maestro Auto-Start Terminal Integration

## Overview

| Field | Value |
|-------|-------|
| Sprint | 7 |
| Title | Maestro Auto-Start Terminal Integration |
| Type | fullstack |
| Epic | None |
| Status | Planning |
| Created | 2026-01-31 |
| Started | - |
| Completed | - |

## Goal

Enable Maestro pipeline tasks to auto-start via terminal with Claude Code and `/sprint-start N` command when clicking "Start".

## Background

Maestro pipeline tasks currently block when clicking "Start" with an error message telling users to use "Open Terminal" instead. The user experience should be seamless - clicking Start on a Maestro task should automatically:
1. Open a new terminal in the project directory
2. Invoke Claude Code
3. Send the `/sprint-start N` command after Claude loads

This makes Maestro tasks fully automated from the UI while still running through the terminal-based sprint workflow.

## Requirements

### Functional Requirements

- [ ] TASK_START handler auto-opens terminal for Maestro pipeline tasks
- [ ] Terminal invokes Claude Code automatically
- [ ] `/sprint-start N` command is sent after Claude initializes
- [ ] Sprint number is extracted from task metadata (sprintFile path)
- [ ] Terminal ID is tracked for the task

### Non-Functional Requirements

- [ ] Delay between Claude invoke and command send allows Claude to fully initialize
- [ ] Error handling for missing sprint file or invalid sprint number
- [ ] Consistent with existing maestro-handlers.ts patterns

## Dependencies

- **Sprints**: None
- **External**: TerminalManager, maestro-handlers.ts patterns already implemented

## Scope

### In Scope

- TASK_START handler modification for Maestro tasks
- execution-handlers.ts function signature update
- task/index.ts parameter passing update
- Sprint number extraction from sprintFile metadata

### Out of Scope

- Changes to TaskCard.tsx (already has Maestro support)
- TASK_UPDATE_STATUS handler (already blocks correctly)
- New IPC channels

## Technical Approach

1. Update `registerTaskExecutionHandlers` signature to accept `terminalManager`
2. Update `task/index.ts` to pass `terminalManager` to execution handlers
3. Replace the blocking error in TASK_START Maestro check with:
   - Extract sprint number from `task.metadata?.sprintFile` (e.g., `sprint-04_title.md` → 4)
   - Create terminal via `terminalManager.create()`
   - Invoke Claude via `terminalManager.invokeClaudeAsync()`
   - Send `/sprint-start N` command via `terminalManager.write()` after delay

## Tasks

### Phase 1: Planning
- [ ] Review requirements with stakeholder
- [ ] Design code architecture
- [ ] Clarify any ambiguous requirements

### Phase 2: Implementation
- [ ] Update execution-handlers.ts imports (TerminalManager, readSettingsFileAsync)
- [ ] Update registerTaskExecutionHandlers function signature
- [ ] Update task/index.ts to pass terminalManager
- [ ] Implement sprint number extraction helper
- [ ] Replace TASK_START Maestro block with auto-start logic
- [ ] Write tests (if applicable)

### Phase 3: Validation
- [ ] Test with actual Maestro task creation
- [ ] Verify terminal opens and Claude is invoked
- [ ] Verify /sprint-start command is sent
- [ ] Quality review

### Phase 4: Documentation
- [ ] Update relevant comments in code

## Acceptance Criteria

- [ ] Clicking "Start" on Maestro task opens terminal
- [ ] Claude Code is invoked in the terminal
- [ ] `/sprint-start N` command is sent after Claude loads
- [ ] Sprint number correctly extracted from sprintFile path
- [ ] No TypeScript errors
- [ ] Consistent with existing maestro-handlers.ts patterns

## Open Questions

- Should we notify the renderer about the terminal being opened?
- Should we track the terminal ID in task metadata?

## Notes

- maestro-handlers.ts already has `autoStartSprint` support in MAESTRO_OPEN_TERMINAL
- The 3-second delay for Claude initialization is already proven in maestro-handlers.ts
- YOLO mode setting affects dangerouslySkipPermissions flag

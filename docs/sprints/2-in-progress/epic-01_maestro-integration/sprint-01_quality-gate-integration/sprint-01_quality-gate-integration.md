---
sprint: 1
title: "Quality Gate Integration"
type: backend
epic: 1
status: in-progress
created: 2026-01-29T17:03:35Z
started: 2026-01-29T17:27:28Z
completed: null
hours: null
workflow_version: "3.5.0"

---

# Sprint 1: Quality Gate Integration

## Overview

| Field | Value |
|-------|-------|
| Sprint | 1 |
| Title | Quality Gate Integration |
| Type | backend |
| Epic | 1 |
| Status | Planning |
| Created | 2026-01-29 |
| Started | - |
| Completed | - |

## Goal

Integrate Maestro's 9-item pre-flight checklist into Auto-Claude's QA pipeline as a quality gate.

## Background

Auto-Claude has a QA pipeline that validates work before merge, but it lacks Maestro's structured pre-flight checklist. This sprint adds a MaestroQualityGate adapter that enforces type-specific coverage thresholds and runs 9 validation checks before allowing work to merge.

The quality gate is the core enforcement mechanism - it's what ensures "build right" alongside "build fast."

**Prerequisite**: Sprint Type Foundation (completed on `feature/maestro-sprint-types` branch)

## Requirements

### Functional Requirements

- [ ] Create `MaestroQualityGate` adapter class
- [ ] Implement 9-item pre-flight checklist
- [ ] Hook quality gate into existing QA pipeline
- [ ] Use sprint type to determine coverage threshold
- [ ] Block merge when gate fails with clear error messages
- [ ] Allow spike type to skip coverage check
- [ ] Allow research type to use reduced checklist (docs focus)

### Non-Functional Requirements

- [ ] Gate runs asynchronously to not block parallel agents
- [ ] Gate results cached to avoid redundant checks
- [ ] Clear, actionable error messages on failure

## Dependencies

- **Sprints**: Sprint Type Foundation (DONE - on `feature/maestro-sprint-types`)
- **External**: Auto-Claude QA pipeline (`apps/backend/qa/`)

## Scope

### In Scope

- MaestroQualityGate adapter
- 9-item pre-flight checklist implementation
- Integration with existing QA pipeline
- Type-specific gate behavior
- Unit and integration tests

### Out of Scope

- Workflow state tracking (Sprint 2)
- Postmortem generation (Sprint 3)
- Auto-fix capabilities (future enhancement)

## Technical Approach

1. Create `apps/backend/qa/maestro_adapter.py` with MaestroQualityGate class
2. Create `apps/backend/qa/preflight_checklist.py` with 9 check implementations
3. Modify `apps/backend/qa/pipeline.py` to call Maestro gate after existing checks
4. Add configuration in `.auto-claude/maestro.yaml` for gate settings

## Tasks

### Phase 1: Planning
- [ ] Review Auto-Claude QA pipeline architecture
- [ ] Design MaestroQualityGate interface
- [ ] Map checklist items to existing Auto-Claude checks where possible

### Phase 2: Implementation
- [ ] Write tests for MaestroQualityGate
- [ ] Write tests for each checklist item
- [ ] Implement MaestroQualityGate adapter
- [ ] Implement 9 pre-flight checklist items:
  - [ ] All tests pass
  - [ ] Coverage meets threshold
  - [ ] No lint errors
  - [ ] No type errors
  - [ ] Migrations valid and reversible
  - [ ] Documentation updated
  - [ ] No debug statements
  - [ ] No secrets in code
  - [ ] Changelog updated
- [ ] Hook into QA pipeline
- [ ] Add configuration file support

### Phase 3: Validation
- [ ] Test with each sprint type (6 types)
- [ ] Test gate failure scenarios
- [ ] Test gate bypass for spike type
- [ ] Run full Auto-Claude test suite

### Phase 4: Documentation
- [ ] Document quality gate configuration
- [ ] Add troubleshooting guide for common failures
- [ ] Update Auto-Claude README

## Acceptance Criteria

- [ ] QA pipeline runs 9-item checklist before merge
- [ ] Merge blocked when any checklist item fails
- [ ] Coverage threshold varies by sprint type
- [ ] Spike type skips coverage check entirely
- [ ] Research type uses reduced checklist (3 items)
- [ ] Error messages clearly indicate which check failed and why
- [ ] All tests passing with 85% coverage
- [ ] Code reviewed

## Pre-Flight Checklist Reference

| # | Check | Spike | Research | Others |
|---|-------|-------|----------|--------|
| 1 | All tests pass | Skip | Required | Required |
| 2 | Coverage meets threshold | Skip | 30% | Type-specific |
| 3 | No lint errors | Skip | Required | Required |
| 4 | No type errors | Skip | Skip | Required |
| 5 | Migrations valid | Skip | Skip | Required |
| 6 | Documentation updated | Required | Required | Optional |
| 7 | No debug statements | Skip | Required | Required |
| 8 | No secrets in code | Required | Required | Required |
| 9 | Changelog updated | Skip | Skip | Optional |

## Notes

Created: 2026-01-29
Migrated from: maestro Sprint 9
Target Files:
- `apps/backend/qa/maestro_adapter.py` (new)
- `apps/backend/qa/preflight_checklist.py` (new)
- `apps/backend/qa/pipeline.py` (modify)
- `.auto-claude/maestro.yaml` (new)

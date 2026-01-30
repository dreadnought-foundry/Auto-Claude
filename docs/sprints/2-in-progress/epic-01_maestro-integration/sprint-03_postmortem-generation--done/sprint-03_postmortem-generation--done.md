---
sprint: 3
title: "Postmortem Generation"
type: backend
epic: 1
status: done
created: 2026-01-29T17:03:42Z
started: 2026-01-30T09:36:01Z
completed: 2026-01-30
hours: null
workflow_version: "3.5.0"


---

# Sprint 3: Postmortem Generation

## Overview

| Field | Value |
|-------|-------|
| Sprint | 3 |
| Title | Postmortem Generation |
| Type | backend |
| Epic | 1 |
| Status | Planning |
| Created | 2026-01-29 |
| Started | - |
| Completed | - |

## Goal

Auto-generate Maestro-format postmortems after Auto-Claude completes a spec, capturing metrics, learnings, and patterns.

## Background

When Auto-Claude completes work, the execution data (which agents ran, what files changed, how long it took) is lost. Maestro's postmortem format captures this data in a structured way that enables:
- Learning from past sprints
- Identifying reusable patterns
- Tracking team velocity over time
- Continuous improvement through reflection

This sprint adds automatic postmortem generation that runs when a spec completes.

## Requirements

### Functional Requirements

- [ ] Create PostmortemGenerator class
- [ ] Collect execution metrics from Auto-Claude agents
- [ ] Build summary section (duration, tests, coverage, files)
- [ ] Build agent contributions section
- [ ] Generate "what went well" from successful patterns
- [ ] Generate "what could improve" from rework cycles
- [ ] Extract reusable patterns from code changes
- [ ] Generate learnings and action items
- [ ] Output postmortem in Markdown format

### Non-Functional Requirements

- [ ] Generation completes in < 30 seconds
- [ ] Postmortem is human-readable and useful
- [ ] Graceful handling of missing metrics

## Dependencies

- **Sprints**: Sprint 2 (State Synchronization) - needs phase timestamps
- **External**: Auto-Claude agent metrics

## Scope

### In Scope

- PostmortemGenerator module
- Metrics collection from agents
- Pattern extraction from diffs
- Markdown output writer
- Integration with spec completion flow

### Out of Scope

- Postmortem editing UI
- Pattern library management
- Cross-sprint analytics (future epic)

## Technical Approach

1. Create `apps/backend/qa/postmortem.py` with PostmortemGenerator class
2. Create `apps/backend/agents/metrics.py` for agent metric collection
3. Create `apps/backend/analysis/patterns.py` for pattern extraction
4. Hook into spec completion event to trigger generation
5. Write postmortem to `sprint-{N}_postmortem.md`

## Tasks

### Phase 1: Planning
- [ ] Review Auto-Claude agent data structures
- [ ] Design metrics collection interface
- [ ] Design postmortem output format

### Phase 2: Implementation
- [ ] Write tests for PostmortemGenerator
- [ ] Write tests for metrics collection
- [ ] Write tests for pattern extraction
- [ ] Implement metrics collector
- [ ] Implement PostmortemGenerator:
  - [ ] build_summary()
  - [ ] extract_agent_contributions()
  - [ ] analyze_successes()
  - [ ] analyze_issues()
  - [ ] extract_patterns()
  - [ ] generate_learnings()
  - [ ] suggest_actions()
- [ ] Implement pattern extractor
- [ ] Implement Markdown writer
- [ ] Hook into spec completion

### Phase 3: Validation
- [ ] Generate postmortem for test spec
- [ ] Verify all sections populated
- [ ] Test with multi-agent execution
- [ ] Test with failed/rework scenarios
- [ ] Run Auto-Claude test suite

### Phase 4: Documentation
- [ ] Document postmortem format
- [ ] Add examples of generated postmortems
- [ ] Document customization options

## Acceptance Criteria

- [ ] Postmortem auto-generated on spec completion
- [ ] Summary includes: duration, tests added, coverage delta, files changed
- [ ] Agent contributions tracked per session
- [ ] "What went well" section has at least 2 items
- [ ] "What could improve" populated when rework occurred
- [ ] Patterns section identifies reusable code
- [ ] Output is valid Markdown
- [ ] All tests passing with 85% coverage
- [ ] Code reviewed

## Postmortem Format

```markdown
## Sprint {N} Postmortem: {Title}

### Summary
| Metric | Value |
|--------|-------|
| Started | {timestamp} |
| Completed | {timestamp} |
| Duration | {hours} |
| Tests Added | {count} |
| Coverage Delta | {+X%} |
| Files Changed | {count} |
| Agents Used | {count} |
| Rework Cycles | {count} |

### Agent Contributions
| Agent | Tasks | Files Created/Modified | Time |
|-------|-------|----------------------|------|
| {name} | {tasks} | {files} | {time} |

### What Went Well
- {Positive outcome derived from execution data}

### What Could Improve
- {Issue identified from rework or failures}

### Patterns Discovered
- {Reusable pattern extracted from changes}

### Learnings
1. **Technical**: {insight}
2. **Process**: {insight}

### Action Items
- [ ] {Suggested follow-up}
```

## Notes

Created: 2026-01-29
Migrated from: maestro Sprint 11
Target Files:
- `apps/backend/qa/postmortem.py` (new)
- `apps/backend/qa/postmortem_writer.py` (new)
- `apps/backend/agents/metrics.py` (new)
- `apps/backend/analysis/patterns.py` (new)

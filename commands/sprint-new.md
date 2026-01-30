---
description: "Create a new sprint planning file from template"
allowed-tools: [Read, Write, Glob, Bash]
---

# Create Sprint $ARGUMENTS

Create a new sprint planning file for Sprint **$ARGUMENTS**.

## Instructions

### 1. Determine Sprint Number, Title, and Epic

**IMPORTANT**: Sprint numbers are now AUTO-ASSIGNED from registry.json unless explicitly specified.

Parse $ARGUMENTS:

**Option A - Auto-number (RECOMMENDED):**
- If just a title (e.g., "Photo Upload Feature"), auto-assign next sprint number
- If includes "--epic=N", link to epic N
- Example: "Photo Capture --epic=3" → Auto-assigns next number (e.g., Sprint 6), Title "Photo Capture", Epic 3

**Option B - Manual number (backwards compatibility):**
- If starts with number (e.g., "53 Photo Capture"), use "53" as number
- Example: "53 Photo Capture --epic=3" → Sprint 53, Title "Photo Capture", Epic 3
- **Warning**: Manual numbers may conflict with auto-assigned numbers!

**Auto-number workflow:**
```bash
# Get next sprint number from automation
SPRINT_NUM=$(python3 ~/.claude/scripts/sprint_lifecycle.py next-sprint-number --dry-run | grep "Next sprint number" | awk '{print $4}')
echo "Auto-assigned sprint number: $SPRINT_NUM"
```

Epic is optional - sprints can exist without an epic.

### 2. Register Sprint in Registry (Auto-number mode)

**If using auto-number mode**, register the sprint using automation:

```bash
# Extract title and epic from arguments
TITLE="$TITLE"  # Parsed from arguments
EPIC="$EPIC"    # Optional, parsed from --epic=N

# Register sprint and get assigned number
if [ -n "$EPIC" ]; then
  SPRINT_NUM=$(python3 ~/.claude/scripts/sprint_lifecycle.py register-sprint "$TITLE" --epic $EPIC --estimated-hours $HOURS 2>&1 | grep "Registered sprint" | awk '{print $3}')
else
  SPRINT_NUM=$(python3 ~/.claude/scripts/sprint_lifecycle.py register-sprint "$TITLE" --estimated-hours $HOURS 2>&1 | grep "Registered sprint" | awk '{print $3}')
fi

echo "✓ Sprint $SPRINT_NUM registered: $TITLE"
```

This automatically:
- Assigns next available sprint number
- Increments registry counter
- Registers sprint in registry.json with metadata
- Links to epic if specified

**If using manual number mode**, check for conflicts:
```bash
# Use Glob to find existing sprints
docs/sprints/sprint-*.md

# Verify the sprint number doesn't already exist
```

### 3. Create Sprint Directory (if needed)

```bash
mkdir -p docs/sprints
```

### 4. Create Sprint File

Create `docs/sprints/sprint-{NN}_{slug}.md` where:
- `{NN}` is zero-padded sprint number (01, 02, etc.)
- `{slug}` is lowercase, hyphenated title (e.g., "user-authentication")

Use this template:

```markdown
# Sprint {N}: {Title}

## Overview

| Field | Value |
|-------|-------|
| Sprint | {N} |
| Title | {Title} |
| Epic | {Epic number or "None"} |
| Status | Planning |
| Created | {TODAY} |
| Started | - |
| Completed | - |

## Goal

{One sentence describing what this sprint accomplishes}

## Background

{Why is this needed? What problem does it solve?}

## Requirements

### Functional Requirements

- [ ] {Requirement 1}
- [ ] {Requirement 2}
- [ ] {Requirement 3}

### Non-Functional Requirements

- [ ] {Performance, security, or other constraints}

## Dependencies

- **Sprints**: {List any sprints that must be completed first, or "None"}
- **External**: {External dependencies like APIs, libraries, etc.}

## Scope

### In Scope

- {What's included}

### Out of Scope

- {What's explicitly NOT included}

## Technical Approach

{High-level description of how this will be implemented}

## Tasks

### Phase 1: Planning
- [ ] Review requirements with stakeholder
- [ ] Design code architecture
- [ ] Clarify any ambiguous requirements

### Phase 2: Implementation
- [ ] Write tests
- [ ] Implement feature
- [ ] Fix any test failures

### Phase 3: Validation
- [ ] Verify migrations (if applicable)
- [ ] Quality review
- [ ] Refactoring

### Phase 4: Documentation
- [ ] Create dialog example (if applicable)
- [ ] Update relevant docs

## Acceptance Criteria

- [ ] {Criterion 1 - how do we know this is done?}
- [ ] {Criterion 2}
- [ ] All tests passing
- [ ] Code reviewed and refactored

## Open Questions

- {Any questions that need answers before or during implementation}

## Notes

{Any additional context, links, references}
```

### 5. Update Epic File (if epic specified)

If --epic=N was provided:
1. Find the epic file: `docs/epics/epic-{NN}_*.md`
2. Add a new row to the Sprints table:
   ```
   | {Sprint} | {Title} | planned |
   ```
3. If epic file not found, warn user but still create sprint

### 6. Report

Output:
```
Created: docs/sprints/sprint-{NN}_{slug}.md
Epic: {Epic number and title, or "None (standalone sprint)"}

Next steps:
1. Fill in the sprint details (Goal, Requirements, etc.)
2. Run /sprint-start {N} when ready to begin
```

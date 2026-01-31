# Maestro Pipeline Guide

This guide explains how to use the Maestro pipeline in Auto Claude's Kanban board for guided, low-token-cost task execution.

## What is Maestro?

Maestro is an alternative execution pipeline that provides a **guided step-by-step workflow** via terminal, as opposed to the fully autonomous agent pipeline.

| Feature | Autonomous Pipeline | Maestro Pipeline |
|---------|---------------------|------------------|
| Execution | Fully automated AI agents | Human-guided via terminal |
| Token Usage | Higher (agents run continuously) | Lower (on-demand interactions) |
| Control | AI decides next steps | You decide when to advance |
| Feedback | Review at end | Review at each phase |
| Best For | Well-defined tasks | Complex/exploratory work |

## When to Use Maestro

**Choose Maestro when:**
- You want more control over the implementation process
- The task requires human judgment at multiple points
- You're exploring unfamiliar code and want to learn as you go
- You want to minimize token usage
- The task is complex and benefits from phase-by-phase validation

**Choose Autonomous when:**
- The task is well-defined and straightforward
- You trust the AI to handle it end-to-end
- Speed is more important than cost
- You want hands-off execution

## Creating a Maestro Task

1. **Open Task Creation**
   - Click the **+** button in the Planning column, or
   - Use the keyboard shortcut to create a new task

2. **Describe Your Task**
   - Enter a clear description of what you want to build
   - Add reference images if helpful

3. **Select Pipeline Type**
   - In the task creation dialog, find the **Pipeline Type** section
   - Select **Maestro** (shows 🎯 icon)
   - The description explains: "Guided step-by-step workflow via terminal. Lower token usage, more control."

4. **Create Task**
   - Click "Create Task"
   - Auto Claude will:
     - Create the task in the Planning column
     - Generate a sprint file in `docs/sprints/`
     - Initialize the unified state entry

## Kanban Board Display

Maestro tasks appear on the Kanban board with distinct visual indicators:

### Pipeline Badge
- **🎯** - Maestro pipeline task
- **🤖** - Autonomous pipeline task

### Phase Progress
Maestro tasks show their current phase and step:
```
🎯 Planning • 1.1
```

### Column Mapping
As you progress through Maestro phases, tasks automatically move columns:

| Maestro Phase | Description | Kanban Column |
|---------------|-------------|---------------|
| Phase 1 | Planning | Planning |
| Phase 2 | Implementation | In Progress |
| Phase 3 | Validation | In Progress |
| Phase 4 | Documentation | AI Review |
| Phase 5 | Commit | AI Review |
| Phase 6 | Completion | Human Review → Done |

## Working with Maestro Tasks

### Starting Work

1. **Find your Maestro task** on the Kanban board (look for 🎯)
2. **Click "Open Terminal"** button on the task card
3. A new terminal opens in your project directory with Claude invoked

### The Maestro Workflow

Once in the terminal, Claude guides you through the sprint workflow:

#### Phase 1: Planning (Steps 1.1-1.4)
- Review sprint requirements
- Design code architecture
- Clarify ambiguous requirements
- Get your approval before implementation

#### Phase 2: Implementation (Steps 2.1-2.4)
- Write tests first (TDD approach)
- Implement the feature
- Run tests
- Fix any failures

#### Phase 3: Validation (Steps 3.1-3.4)
- Verify migrations (if applicable)
- Quality review
- Refactoring
- Re-test

#### Phase 4: Documentation (Step 4.1)
- Update relevant documentation
- Create examples if needed

#### Phase 5: Commit (Steps 5.1-5.2)
- Stage changes
- Create commit with proper message

#### Phase 6: Completion (Steps 6.1-6.4)
- Update sprint file
- Run completion checklist
- Mark sprint as done

### Advancing Steps

Use these commands in the terminal:
- `/sprint-status` - Check current progress
- `/sprint-next` - Advance to next step after completing current
- `/sprint-complete` - Finish the sprint (runs pre-flight checklist)

### Returning to a Task

If you close the terminal or need to resume later:
1. Find your Maestro task on the Kanban board
2. Click "Open Terminal" again
3. Use `/sprint-status` to see where you left off
4. Continue from the current step

## Quality Gates

When you try to move a Maestro task to "Done", quality gates are checked:

### Required Checks
1. **All phases completed** - Steps 6.1-6.4 must be done
2. **Sprint file exists** - The generated sprint file must be present
3. **Task status valid** - Task must be in appropriate state

### Coverage Thresholds by Sprint Type
| Sprint Type | Coverage Required |
|-------------|-------------------|
| Basic | 60% |
| Fullstack | 75% |
| Infrastructure | 70% |
| Documentation | 50% |
| Refactoring | 80% |

### If Gates Fail
- A toast notification shows which checks failed
- The task stays in its current column
- Fix the issues and try again

## Sprint Files

Each Maestro task generates a sprint file at:
```
docs/sprints/sprint-NN_task-slug.md
```

This file contains:
- Task overview and requirements
- Phase-by-phase task breakdown
- Acceptance criteria
- Progress tracking

You can edit this file to refine requirements or add notes.

## Unified State

Maestro tasks share state with the Kanban board via:
```
{project}/.claude/task-state.json
```

This file is automatically managed - don't edit it manually. It enables:
- Real-time Kanban board updates
- Phase/step progress tracking
- Task synchronization between terminal and UI

## Tips for Success

1. **Start with clear requirements** - The better your initial description, the better the sprint file generated

2. **Use the planning phase** - Don't rush to implementation. Good architecture design saves time later

3. **Review at each phase** - Maestro's value is in the checkpoints. Use them to catch issues early

4. **Keep the terminal open** - While working on a phase, keep the terminal session active for context continuity

5. **Check sprint status often** - Use `/sprint-status` to stay oriented in the workflow

6. **Don't skip quality gates** - They exist to ensure work is actually complete before marking done

## Troubleshooting

### Task not showing on Kanban board
- Check that the unified state file exists: `.claude/task-state.json`
- Try clicking "Refresh Tasks" in the Kanban toolbar

### Terminal doesn't have Claude context
- Make sure you clicked "Open Terminal" from the task card
- Check that Claude Code CLI is installed and configured

### Phase progress not updating
- State updates are debounced (500ms delay)
- Try `/sprint-status` in terminal to verify actual state
- Refresh the Kanban board

### Quality gates failing unexpectedly
- Check `/sprint-status` to see which steps are incomplete
- Ensure all Phase 6 steps (6.1-6.4) are marked complete
- Verify the sprint file path is correct

## Related Commands

| Command | Description |
|---------|-------------|
| `/sprint-start N` | Start a sprint |
| `/sprint-status` | Show current progress |
| `/sprint-next` | Advance to next step |
| `/sprint-complete` | Complete the sprint |
| `/sprint-blocked` | Mark sprint as blocked |
| `/sprint-abort` | Abandon the sprint |

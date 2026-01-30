"""Maestro phase mapping for Auto-Claude stage transitions.

Maps Auto-Claude execution stages to Maestro workflow phases
for unified progress tracking.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AutoClaudeStage(str, Enum):
    """Auto-Claude execution stages."""

    PLANNING = "planning"
    DISCOVERY = "discovery"
    CLARIFICATION = "clarification"
    TEST_WRITING = "test_writing"
    IMPLEMENTATION = "implementation"
    TEST_RUNNING = "test_running"
    TEST_FIXING = "test_fixing"
    VALIDATION = "validation"
    REVIEW = "review"
    REFACTORING = "refactoring"
    DOCUMENTATION = "documentation"
    COMMIT = "commit"
    COMPLETE = "complete"


class MaestroPhase(str, Enum):
    """Maestro workflow phases (6 main phases with sub-steps)."""

    # Phase 1: Planning
    PLANNING_READ = "1.1"  # Read sprint file
    PLANNING_DESIGN = "1.2"  # Architecture design
    PLANNING_CLARIFY = "1.3"  # Clarify requirements
    PLANNING_LOCKED = "1.4"  # Requirements locked

    # Phase 2: Test-First Implementation
    TDD_WRITE_TESTS = "2.1"  # Write tests
    TDD_IMPLEMENT = "2.2"  # Implement feature
    TDD_RUN_TESTS = "2.3"  # Run tests
    TDD_FIX_FAILURES = "2.4"  # Fix failures

    # Phase 3: Validation & Refactoring
    VAL_VERIFY = "3.1"  # Verify migrations
    VAL_REVIEW = "3.2"  # Quality review
    VAL_REFACTOR = "3.3"  # Refactor code
    VAL_RETEST = "3.4"  # Re-test after refactor

    # Phase 4: Documentation
    DOC_EXAMPLES = "4.1"  # Generate examples

    # Phase 5: Commit
    COMMIT = "5.1"  # Stage and commit

    # Phase 6: Completion
    COMPLETE_UPDATE = "6.1"  # Update sprint file
    COMPLETE_CHECKLIST = "6.2"  # Run checklist
    COMPLETE_CLOSE = "6.3"  # Close sprint
    COMPLETE_HANDOFF = "6.4"  # Handoff


# Auto-Claude Stage to Maestro Phase mapping
STAGE_TO_PHASE: dict[AutoClaudeStage, MaestroPhase] = {
    AutoClaudeStage.PLANNING: MaestroPhase.PLANNING_READ,
    AutoClaudeStage.DISCOVERY: MaestroPhase.PLANNING_DESIGN,
    AutoClaudeStage.CLARIFICATION: MaestroPhase.PLANNING_CLARIFY,
    AutoClaudeStage.TEST_WRITING: MaestroPhase.TDD_WRITE_TESTS,
    AutoClaudeStage.IMPLEMENTATION: MaestroPhase.TDD_IMPLEMENT,
    AutoClaudeStage.TEST_RUNNING: MaestroPhase.TDD_RUN_TESTS,
    AutoClaudeStage.TEST_FIXING: MaestroPhase.TDD_FIX_FAILURES,
    AutoClaudeStage.VALIDATION: MaestroPhase.VAL_VERIFY,
    AutoClaudeStage.REVIEW: MaestroPhase.VAL_REVIEW,
    AutoClaudeStage.REFACTORING: MaestroPhase.VAL_REFACTOR,
    AutoClaudeStage.DOCUMENTATION: MaestroPhase.DOC_EXAMPLES,
    AutoClaudeStage.COMMIT: MaestroPhase.COMMIT,
    AutoClaudeStage.COMPLETE: MaestroPhase.COMPLETE_UPDATE,
}


@dataclass(frozen=True)
class PhaseInfo:
    """Information about a Maestro phase."""

    phase: MaestroPhase
    main_phase: int
    sub_step: int
    name: str
    description: str


# Phase metadata for display and documentation
PHASE_INFO: dict[MaestroPhase, PhaseInfo] = {
    # Phase 1: Planning
    MaestroPhase.PLANNING_READ: PhaseInfo(
        MaestroPhase.PLANNING_READ, 1, 1, "Read Sprint", "Reading sprint file"
    ),
    MaestroPhase.PLANNING_DESIGN: PhaseInfo(
        MaestroPhase.PLANNING_DESIGN, 1, 2, "Design Architecture", "Designing implementation"
    ),
    MaestroPhase.PLANNING_CLARIFY: PhaseInfo(
        MaestroPhase.PLANNING_CLARIFY, 1, 3, "Clarify Requirements", "Clarifying requirements"
    ),
    MaestroPhase.PLANNING_LOCKED: PhaseInfo(
        MaestroPhase.PLANNING_LOCKED, 1, 4, "Lock Requirements", "Requirements locked"
    ),
    # Phase 2: TDD
    MaestroPhase.TDD_WRITE_TESTS: PhaseInfo(
        MaestroPhase.TDD_WRITE_TESTS, 2, 1, "Write Tests", "Writing failing tests"
    ),
    MaestroPhase.TDD_IMPLEMENT: PhaseInfo(
        MaestroPhase.TDD_IMPLEMENT, 2, 2, "Implement Feature", "Implementing feature"
    ),
    MaestroPhase.TDD_RUN_TESTS: PhaseInfo(
        MaestroPhase.TDD_RUN_TESTS, 2, 3, "Run Tests", "Running tests"
    ),
    MaestroPhase.TDD_FIX_FAILURES: PhaseInfo(
        MaestroPhase.TDD_FIX_FAILURES, 2, 4, "Fix Failures", "Fixing test failures"
    ),
    # Phase 3: Validation
    MaestroPhase.VAL_VERIFY: PhaseInfo(
        MaestroPhase.VAL_VERIFY, 3, 1, "Verify Migrations", "Verifying migrations"
    ),
    MaestroPhase.VAL_REVIEW: PhaseInfo(
        MaestroPhase.VAL_REVIEW, 3, 2, "Quality Review", "Quality review"
    ),
    MaestroPhase.VAL_REFACTOR: PhaseInfo(
        MaestroPhase.VAL_REFACTOR, 3, 3, "Refactor Code", "Refactoring code"
    ),
    MaestroPhase.VAL_RETEST: PhaseInfo(
        MaestroPhase.VAL_RETEST, 3, 4, "Re-test", "Re-testing after refactor"
    ),
    # Phase 4: Documentation
    MaestroPhase.DOC_EXAMPLES: PhaseInfo(
        MaestroPhase.DOC_EXAMPLES, 4, 1, "Generate Docs", "Generating documentation"
    ),
    # Phase 5: Commit
    MaestroPhase.COMMIT: PhaseInfo(
        MaestroPhase.COMMIT, 5, 1, "Stage & Commit", "Staging and committing"
    ),
    # Phase 6: Completion
    MaestroPhase.COMPLETE_UPDATE: PhaseInfo(
        MaestroPhase.COMPLETE_UPDATE, 6, 1, "Update Sprint", "Updating sprint file"
    ),
    MaestroPhase.COMPLETE_CHECKLIST: PhaseInfo(
        MaestroPhase.COMPLETE_CHECKLIST, 6, 2, "Run Checklist", "Running checklist"
    ),
    MaestroPhase.COMPLETE_CLOSE: PhaseInfo(
        MaestroPhase.COMPLETE_CLOSE, 6, 3, "Close Sprint", "Closing sprint"
    ),
    MaestroPhase.COMPLETE_HANDOFF: PhaseInfo(
        MaestroPhase.COMPLETE_HANDOFF, 6, 4, "Handoff", "Sprint handoff"
    ),
}


def get_phase_for_stage(stage: str) -> Optional[MaestroPhase]:
    """Map an Auto-Claude stage to a Maestro phase.

    Args:
        stage: Auto-Claude stage name (e.g., "planning", "implementation")

    Returns:
        MaestroPhase or None if stage not mapped
    """
    if not stage:
        return None

    try:
        auto_stage = AutoClaudeStage(stage.lower())
        return STAGE_TO_PHASE.get(auto_stage)
    except ValueError:
        return None


def get_phase_info(phase: MaestroPhase) -> Optional[PhaseInfo]:
    """Get metadata about a phase.

    Args:
        phase: Maestro phase

    Returns:
        PhaseInfo or None if phase not found
    """
    return PHASE_INFO.get(phase)

"""Tests for postmortem generation.

Tests the PostmortemGenerator, metrics collection, pattern extraction,
and Markdown writing for Maestro-format postmortems.
"""

import json
import pytest
from datetime import datetime, timezone
from pathlib import Path

from agents.metrics import (
    SessionMetrics,
    ExecutionMetrics,
    AgentContribution,
    MetricsCollector,
    collect_execution_metrics,
)
from analysis.patterns import (
    PatternDiscovery,
    ApproachOutcome,
    PatternExtractor,
    extract_patterns,
)
from qa.postmortem import (
    PostmortemData,
    PostmortemGenerator,
    generate_postmortem,
)
from qa.postmortem_writer import (
    PostmortemWriter,
    write_postmortem,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def spec_dir(tmp_path):
    """Create a minimal spec directory."""
    spec = tmp_path / "001-test-spec"
    spec.mkdir()
    return spec


@pytest.fixture
def project_dir(tmp_path):
    """Create a minimal project directory."""
    project = tmp_path / "project"
    project.mkdir()
    return project


@pytest.fixture
def spec_with_plan(spec_dir):
    """Spec directory with a completed implementation plan."""
    plan = {
        "feature": "Test Feature",
        "workflow_type": "fullstack",
        "phases": [
            {
                "phase": 1,
                "name": "Setup",
                "subtasks": [
                    {"id": "1-1", "status": "completed", "description": "Initialize project"},
                    {"id": "1-2", "status": "completed", "description": "Add dependencies"},
                ],
            },
            {
                "phase": 2,
                "name": "Implementation",
                "subtasks": [
                    {"id": "2-1", "status": "completed", "description": "Implement feature"},
                    {"id": "2-2", "status": "completed", "description": "Add tests"},
                ],
            },
        ],
        "qa_signoff": {"status": "approved", "timestamp": "2026-01-30T12:00:00Z"},
        "qa_iteration_history": [
            {
                "iteration": 1,
                "status": "rejected",
                "timestamp": "2026-01-30T10:00:00Z",
                "issues": [{"type": "test_failure", "description": "Test failed"}],
            },
            {
                "iteration": 2,
                "status": "approved",
                "timestamp": "2026-01-30T11:00:00Z",
                "issues": [],
            },
        ],
    }
    (spec_dir / "implementation_plan.json").write_text(json.dumps(plan, indent=2))
    return spec_dir


@pytest.fixture
def spec_with_attempts(spec_dir):
    """Spec directory with attempt history."""
    memory_dir = spec_dir / "memory"
    memory_dir.mkdir()

    attempts = {
        "attempts": [
            {
                "attempt_number": 1,
                "subtask_id": "1-1",
                "agent_type": "coder",
                "started_at": "2026-01-30T09:00:00Z",
                "ended_at": "2026-01-30T09:30:00Z",
                "success": True,
                "commit_hash": "abc123",
            },
            {
                "attempt_number": 2,
                "subtask_id": "1-2",
                "agent_type": "coder",
                "started_at": "2026-01-30T09:30:00Z",
                "ended_at": "2026-01-30T10:00:00Z",
                "success": False,
                "error": "Syntax error",
            },
            {
                "attempt_number": 3,
                "subtask_id": "1-2",
                "agent_type": "coder",
                "started_at": "2026-01-30T10:00:00Z",
                "ended_at": "2026-01-30T10:15:00Z",
                "success": True,
                "commit_hash": "def456",
            },
        ],
    }
    (memory_dir / "attempt_history.json").write_text(json.dumps(attempts, indent=2))
    return spec_dir


@pytest.fixture
def spec_with_insights(spec_dir):
    """Spec directory with session insights."""
    memory_dir = spec_dir / "memory"
    memory_dir.mkdir(exist_ok=True)

    insights = {
        "session_id": "session-1",
        "what_worked": [
            "Used existing API patterns for consistency",
            "Test-first approach caught edge cases early",
        ],
        "what_didnt_work": ["Initial approach was too complex"],
        "patterns_used": [
            {"name": "Factory pattern", "files": ["src/factory.py"]},
        ],
        "learnings": ["Simpler solutions are often better"],
    }
    (memory_dir / "session_insights_1.json").write_text(json.dumps(insights, indent=2))
    return spec_dir


# =============================================================================
# Tests: Session Metrics
# =============================================================================


class TestSessionMetrics:
    """Tests for SessionMetrics dataclass."""

    def test_create_session(self):
        """Create a basic session metrics record."""
        session = SessionMetrics(
            agent_type="coder",
            session_num=1,
            subtask_id="1-1",
            started_at=datetime.now(timezone.utc),
        )
        assert session.agent_type == "coder"
        assert session.success is False  # Default
        assert session.files_created == []

    def test_session_with_files(self):
        """Session with created and modified files."""
        session = SessionMetrics(
            agent_type="coder",
            session_num=1,
            subtask_id="1-1",
            started_at=datetime.now(timezone.utc),
            files_created=["src/new.py"],
            files_modified=["src/existing.py"],
        )
        assert len(session.files_created) == 1
        assert len(session.files_modified) == 1


class TestExecutionMetrics:
    """Tests for ExecutionMetrics dataclass."""

    def test_create_metrics(self):
        """Create execution metrics."""
        metrics = ExecutionMetrics(
            spec_name="test-spec",
            sprint_type="backend",
            started_at="2026-01-30T09:00:00Z",
            completed_at="2026-01-30T12:00:00Z",
            duration_seconds=10800,
            total_subtasks=4,
            completed_subtasks=4,
            phases_count=2,
            agents_used={"planner", "coder", "qa_reviewer"},
            tests_added=5,
            coverage_delta=3.5,
            files_changed=10,
            commits_count=3,
            rework_cycles=1,
        )
        assert metrics.spec_name == "test-spec"
        assert metrics.duration_seconds == 10800
        assert "coder" in metrics.agents_used


class TestAgentContribution:
    """Tests for AgentContribution dataclass."""

    def test_create_contribution(self):
        """Create agent contribution record."""
        contrib = AgentContribution(
            agent_type="coder",
            tasks_completed=3,
            files_created=["a.py", "b.py"],
            files_modified=["c.py"],
            sessions_count=4,
            duration_seconds=1800,
        )
        assert contrib.agent_type == "coder"
        assert contrib.tasks_completed == 3
        assert len(contrib.files_created) == 2


# =============================================================================
# Tests: Metrics Collector
# =============================================================================


class TestMetricsCollector:
    """Tests for MetricsCollector class."""

    def test_init(self, spec_dir, project_dir):
        """Initialize collector."""
        collector = MetricsCollector(spec_dir, project_dir)
        assert collector.spec_dir == spec_dir
        assert collector.project_dir == project_dir

    def test_record_session_start(self, spec_dir, project_dir):
        """Record session start."""
        collector = MetricsCollector(spec_dir, project_dir)
        session = collector.record_session_start("coder", 1, "1-1")

        assert session.agent_type == "coder"
        assert session.session_num == 1
        assert session.subtask_id == "1-1"
        assert session.started_at is not None

    def test_record_session_end(self, spec_dir, project_dir):
        """Record session end."""
        collector = MetricsCollector(spec_dir, project_dir)
        session = collector.record_session_start("coder", 1, "1-1")
        collector.record_session_end(session, success=True, files_changed=["src/new.py"])

        assert session.success is True
        assert session.ended_at is not None
        assert "src/new.py" in session.files_modified

    def test_aggregate_multiple_sessions(self, spec_dir, project_dir):
        """Aggregate metrics from multiple sessions."""
        collector = MetricsCollector(spec_dir, project_dir)

        # Session 1: coder
        s1 = collector.record_session_start("coder", 1, "1-1")
        collector.record_session_end(s1, True, ["a.py"])

        # Session 2: qa_reviewer
        s2 = collector.record_session_start("qa_reviewer", 2, None)
        collector.record_session_end(s2, True, [])

        # Session 3: coder retry
        s3 = collector.record_session_start("coder", 3, "1-2")
        collector.record_session_end(s3, True, ["b.py"])

        metrics = collector.aggregate_metrics()
        assert "coder" in metrics.agents_used
        assert "qa_reviewer" in metrics.agents_used

    def test_save_and_load_metrics(self, spec_dir, project_dir):
        """Save and load metrics to/from file."""
        collector = MetricsCollector(spec_dir, project_dir)
        s1 = collector.record_session_start("coder", 1, "1-1")
        collector.record_session_end(s1, True, ["a.py"])

        # Save
        metrics_file = collector.save_metrics()
        assert metrics_file.exists()

        # Load in new collector
        collector2 = MetricsCollector(spec_dir, project_dir)
        loaded = collector2.load_metrics()
        assert loaded is not None
        assert "coder" in loaded.agents_used

    def test_load_missing_file(self, spec_dir, project_dir):
        """Load returns None for missing file."""
        collector = MetricsCollector(spec_dir, project_dir)
        assert collector.load_metrics() is None

    def test_aggregate_empty_sessions(self, spec_dir, project_dir):
        """Aggregate with no sessions."""
        collector = MetricsCollector(spec_dir, project_dir)
        metrics = collector.aggregate_metrics()
        assert metrics.agents_used == set()
        assert metrics.duration_seconds == 0


class TestCollectExecutionMetrics:
    """Tests for collect_execution_metrics function."""

    def test_collect_from_plan(self, spec_with_plan, project_dir):
        """Collect metrics from implementation plan."""
        metrics = collect_execution_metrics(spec_with_plan, project_dir)

        assert metrics.total_subtasks == 4
        assert metrics.completed_subtasks == 4
        assert metrics.phases_count == 2
        assert metrics.rework_cycles == 1  # One rejected iteration

    def test_collect_from_attempts(self, spec_with_plan, project_dir):
        """Collect metrics including attempt history."""
        # Add attempt history
        memory_dir = spec_with_plan / "memory"
        memory_dir.mkdir()
        attempts = {
            "attempts": [
                {"agent_type": "coder", "success": True},
                {"agent_type": "planner", "success": True},
            ],
        }
        (memory_dir / "attempt_history.json").write_text(json.dumps(attempts))

        metrics = collect_execution_metrics(spec_with_plan, project_dir)
        assert "coder" in metrics.agents_used
        assert "planner" in metrics.agents_used

    def test_graceful_missing_data(self, spec_dir, project_dir):
        """Graceful handling of missing data."""
        metrics = collect_execution_metrics(spec_dir, project_dir)

        # Should return defaults, not crash
        assert metrics.total_subtasks == 0
        assert metrics.agents_used == set()
        assert metrics.tests_added == 0


# =============================================================================
# Tests: Pattern Extraction
# =============================================================================


class TestPatternDiscovery:
    """Tests for PatternDiscovery dataclass."""

    def test_create_pattern(self):
        """Create a pattern discovery record."""
        pattern = PatternDiscovery(
            pattern_type="code_pattern",
            description="Factory pattern for object creation",
            files=["src/factory.py"],
            frequency=3,
            reusable=True,
            tags=["creational", "design-pattern"],
        )
        assert pattern.pattern_type == "code_pattern"
        assert pattern.reusable is True


class TestApproachOutcome:
    """Tests for ApproachOutcome dataclass."""

    def test_successful_approach(self):
        """Record a successful approach."""
        outcome = ApproachOutcome(
            approach="Test-first development",
            worked=True,
            context="Feature implementation",
        )
        assert outcome.worked is True

    def test_failed_approach_with_alternative(self):
        """Record a failed approach with alternative."""
        outcome = ApproachOutcome(
            approach="Complex state machine",
            worked=False,
            context="State management",
            alternative_tried="Simple state object",
        )
        assert outcome.worked is False
        assert outcome.alternative_tried == "Simple state object"


class TestPatternExtractor:
    """Tests for PatternExtractor class."""

    def test_init(self, spec_dir, project_dir):
        """Initialize extractor."""
        extractor = PatternExtractor(spec_dir, project_dir)
        assert extractor.spec_dir == spec_dir

    def test_extract_from_insights(self, spec_with_insights, project_dir):
        """Extract patterns from session insights."""
        extractor = PatternExtractor(spec_with_insights, project_dir)
        patterns = extractor.extract_code_patterns()

        assert len(patterns) >= 1
        pattern_names = [p.description for p in patterns]
        assert any("Factory" in name for name in pattern_names)

    def test_extract_approach_outcomes(self, spec_with_insights, project_dir):
        """Extract what worked vs didn't."""
        extractor = PatternExtractor(spec_with_insights, project_dir)
        worked, didnt_work = extractor.extract_approach_outcomes()

        assert len(worked) >= 1
        assert len(didnt_work) >= 1

    def test_generate_learnings(self, spec_with_insights, project_dir):
        """Generate learnings from insights."""
        extractor = PatternExtractor(spec_with_insights, project_dir)
        learnings = extractor.extract_learnings()

        assert len(learnings) >= 1

    def test_empty_spec(self, spec_dir, project_dir):
        """Handle spec with no insights gracefully."""
        extractor = PatternExtractor(spec_dir, project_dir)
        patterns = extractor.extract_code_patterns()
        assert patterns == []

    def test_generate_action_items(self, spec_with_insights, project_dir):
        """Generate action items from insights."""
        extractor = PatternExtractor(spec_with_insights, project_dir)
        actions = extractor.generate_action_items()
        # Should have action items from what_didnt_work
        assert len(actions) >= 1


class TestExtractPatterns:
    """Tests for extract_patterns convenience function."""

    def test_extract_all(self, spec_with_insights, project_dir):
        """Extract all pattern types."""
        result = extract_patterns(spec_with_insights, project_dir)

        assert "patterns" in result
        assert "what_worked" in result
        assert "what_didnt_work" in result
        assert "learnings" in result


# =============================================================================
# Tests: Postmortem Generator
# =============================================================================


class TestPostmortemData:
    """Tests for PostmortemData dataclass."""

    def test_create_postmortem_data(self):
        """Create postmortem data structure."""
        metrics = ExecutionMetrics(
            spec_name="test",
            sprint_type="backend",
            started_at="2026-01-30T09:00:00Z",
            completed_at="2026-01-30T12:00:00Z",
            duration_seconds=10800,
            total_subtasks=4,
            completed_subtasks=4,
            phases_count=2,
            agents_used={"coder"},
            tests_added=5,
            coverage_delta=3.5,
            files_changed=10,
            commits_count=3,
            rework_cycles=1,
        )
        data = PostmortemData(
            metrics=metrics,
            agent_contributions=[],
            what_went_well=["Fast implementation"],
            what_could_improve=["More tests needed"],
            patterns_discovered=[],
            learnings=["Test first is good"],
            action_items=["Add more tests"],
        )
        assert data.metrics.spec_name == "test"
        assert len(data.what_went_well) == 1


class TestPostmortemGenerator:
    """Tests for PostmortemGenerator class."""

    def test_init(self, spec_dir, project_dir):
        """Initialize generator."""
        gen = PostmortemGenerator(project_dir, spec_dir)
        assert gen.project_dir == project_dir
        assert gen.spec_dir == spec_dir

    def test_collect_metrics(self, spec_with_plan, project_dir):
        """Collect metrics from spec."""
        gen = PostmortemGenerator(project_dir, spec_with_plan)
        metrics = gen.collect_metrics()

        assert metrics.total_subtasks == 4
        assert metrics.rework_cycles == 1

    def test_analyze_what_went_well(self, spec_with_plan, project_dir):
        """Analyze successes."""
        gen = PostmortemGenerator(project_dir, spec_with_plan)
        successes = gen.analyze_what_went_well()

        # Should generate at least one success item
        assert len(successes) >= 1

    def test_analyze_what_could_improve(self, spec_with_plan, project_dir):
        """Analyze improvement areas."""
        gen = PostmortemGenerator(project_dir, spec_with_plan)
        improvements = gen.analyze_what_could_improve()

        # Has rework cycles, so should have improvement suggestions
        assert len(improvements) >= 1

    def test_generate_complete(self, spec_with_plan, project_dir):
        """Generate complete postmortem data."""
        gen = PostmortemGenerator(project_dir, spec_with_plan)
        data = gen.generate()

        assert isinstance(data, PostmortemData)
        assert data.metrics is not None
        assert len(data.what_went_well) >= 1

    def test_generate_with_missing_data(self, spec_dir, project_dir):
        """Generate postmortem with missing data (graceful degradation)."""
        gen = PostmortemGenerator(project_dir, spec_dir)
        data = gen.generate()

        # Should not crash, should have N/A or defaults
        assert data.metrics.total_subtasks == 0

    def test_collect_patterns(self, spec_with_insights, project_dir):
        """Collect patterns from insights."""
        gen = PostmortemGenerator(project_dir, spec_with_insights)
        patterns = gen.collect_patterns()
        assert len(patterns) >= 1

    def test_generate_learnings(self, spec_with_plan, project_dir):
        """Generate learnings from build."""
        gen = PostmortemGenerator(project_dir, spec_with_plan)
        learnings = gen.generate_learnings()
        # Should have at least one learning (process learning from rework)
        assert len(learnings) >= 1

    def test_generate_action_items(self, spec_with_insights, project_dir):
        """Generate action items."""
        gen = PostmortemGenerator(project_dir, spec_with_insights)
        actions = gen.generate_action_items()
        assert isinstance(actions, list)


# =============================================================================
# Tests: Postmortem Writer
# =============================================================================


class TestPostmortemWriter:
    """Tests for PostmortemWriter class."""

    @pytest.fixture
    def sample_data(self):
        """Sample postmortem data for testing."""
        metrics = ExecutionMetrics(
            spec_name="test-spec",
            sprint_type="backend",
            started_at="2026-01-30T09:00:00Z",
            completed_at="2026-01-30T12:00:00Z",
            duration_seconds=10800,
            total_subtasks=4,
            completed_subtasks=4,
            phases_count=2,
            agents_used={"planner", "coder", "qa_reviewer"},
            tests_added=5,
            coverage_delta=3.5,
            files_changed=10,
            commits_count=3,
            rework_cycles=1,
        )
        return PostmortemData(
            metrics=metrics,
            agent_contributions=[
                {
                    "agent": "Coder",
                    "tasks": 3,
                    "files": "8 created, 2 modified",
                    "time": "2h 30m",
                },
            ],
            what_went_well=["Fast implementation", "Good test coverage"],
            what_could_improve=["Initial design was too complex"],
            patterns_discovered=[
                {"type": "code_pattern", "description": "Factory pattern used"},
            ],
            learnings=["Test-first catches bugs early"],
            action_items=["Document the factory pattern"],
        )

    def test_render_markdown(self, sample_data):
        """Render postmortem to Markdown."""
        writer = PostmortemWriter(sample_data, "test-spec")
        markdown = writer.render()

        assert "## Sprint" in markdown
        assert "Postmortem" in markdown
        assert "### Summary" in markdown
        assert "### Agent Contributions" in markdown
        assert "### What Went Well" in markdown
        assert "### What Could Improve" in markdown
        assert "### Patterns Discovered" in markdown
        assert "### Learnings" in markdown
        assert "### Action Items" in markdown

    def test_summary_table(self, sample_data):
        """Summary table has all metrics."""
        writer = PostmortemWriter(sample_data, "test-spec")
        markdown = writer.render()

        assert "Duration" in markdown
        assert "Tests Added" in markdown
        assert "Coverage Delta" in markdown
        assert "Files Changed" in markdown
        assert "Rework Cycles" in markdown

    def test_agent_table(self, sample_data):
        """Agent contributions table format."""
        writer = PostmortemWriter(sample_data, "test-spec")
        markdown = writer.render()

        assert "| Agent |" in markdown
        assert "Coder" in markdown

    def test_write_to_file(self, sample_data, tmp_path):
        """Write postmortem to file."""
        writer = PostmortemWriter(sample_data, "test-spec")
        output_path = tmp_path / "postmortem.md"
        writer.write(output_path)

        assert output_path.exists()
        content = output_path.read_text()
        assert "## Sprint" in content

    def test_empty_sections(self, tmp_path):
        """Render with empty sections."""
        metrics = ExecutionMetrics(
            spec_name="test",
            sprint_type="backend",
            started_at="",
            completed_at="",
            duration_seconds=0,
            total_subtasks=0,
            completed_subtasks=0,
            phases_count=0,
            agents_used=set(),
            tests_added=0,
            coverage_delta=0,
            files_changed=0,
            commits_count=0,
            rework_cycles=0,
        )
        data = PostmortemData(
            metrics=metrics,
            agent_contributions=[],
            what_went_well=[],
            what_could_improve=[],
            patterns_discovered=[],
            learnings=[],
            action_items=[],
        )
        writer = PostmortemWriter(data, "empty-spec")
        markdown = writer.render()

        # Should have N/A placeholders
        assert "N/A" in markdown
        assert "_None identified._" in markdown

    def test_negative_coverage_delta(self, sample_data):
        """Render with negative coverage delta."""
        sample_data.metrics.coverage_delta = -2.5
        writer = PostmortemWriter(sample_data, "test")
        markdown = writer.render()
        assert "-2.5%" in markdown


class TestWritePostmortem:
    """Tests for write_postmortem convenience function."""

    def test_write_to_spec_dir(self, tmp_path):
        """Write postmortem to spec directory."""
        spec_dir = tmp_path / "001-test"
        spec_dir.mkdir()

        metrics = ExecutionMetrics(
            spec_name="test",
            sprint_type="backend",
            started_at="2026-01-30T09:00:00Z",
            completed_at="2026-01-30T12:00:00Z",
            duration_seconds=10800,
            total_subtasks=4,
            completed_subtasks=4,
            phases_count=2,
            agents_used={"coder"},
            tests_added=5,
            coverage_delta=3.5,
            files_changed=10,
            commits_count=3,
            rework_cycles=0,
        )
        data = PostmortemData(
            metrics=metrics,
            agent_contributions=[],
            what_went_well=["Good"],
            what_could_improve=[],
            patterns_discovered=[],
            learnings=[],
            action_items=[],
        )

        path = write_postmortem(data, spec_dir, "001-test")

        assert path.exists()
        assert "postmortem" in path.name


# =============================================================================
# Tests: Integration
# =============================================================================


class TestPostmortemIntegration:
    """Integration tests for postmortem generation."""

    @pytest.mark.asyncio
    async def test_generate_postmortem_async(self, spec_with_plan, project_dir):
        """Async postmortem generation."""
        data = await generate_postmortem(project_dir, spec_with_plan)

        assert isinstance(data, PostmortemData)
        assert data.metrics.total_subtasks == 4

    def test_end_to_end(self, spec_with_plan, project_dir):
        """Full end-to-end postmortem generation and writing."""
        gen = PostmortemGenerator(project_dir, spec_with_plan)
        data = gen.generate()

        writer = PostmortemWriter(data, spec_with_plan.name)
        markdown = writer.render()

        # Verify structure
        assert "## Sprint" in markdown
        assert "4" in markdown  # Total subtasks
        assert "1" in markdown  # Rework cycles

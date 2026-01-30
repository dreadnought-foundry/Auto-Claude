"""Tests for epic lifecycle management.

Tests the apps/backend/spec/epic_lifecycle.py module which provides:
- Auto-completion detection when all specs done
- Manual completion with force option
- Integration with registry
"""

import pytest
import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "backend"))

from spec.epic import Epic, EpicStatus
from spec.registry import Registry, EpicEntry, SpecEntry
from spec.epic_lifecycle import EpicLifecycleManager, get_lifecycle_manager


class TestLifecycleManagerCreation:
    """Tests for EpicLifecycleManager initialization."""

    def test_manager_creation(self, tmp_path):
        """Manager can be created for a project."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        manager = EpicLifecycleManager(project_dir)

        assert manager.project_dir == project_dir
        assert manager.registry is not None

    def test_factory_function(self, tmp_path):
        """get_lifecycle_manager factory returns manager."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        manager = get_lifecycle_manager(project_dir)

        assert isinstance(manager, EpicLifecycleManager)


class TestOnSpecCompleted:
    """Tests for spec completion handling."""

    def test_spec_without_epic(self, tmp_path):
        """Spec completion without epic doesn't trigger lifecycle."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".auto-claude").mkdir()

        manager = EpicLifecycleManager(project_dir)
        manager.registry.specs[42] = SpecEntry(
            number=42, title="test", status="pending", epic_number=None
        )

        result = manager.on_spec_completed(42)

        assert result is None
        assert manager.registry.specs[42].status == "complete"

    def test_spec_completion_updates_epic(self, tmp_path):
        """Spec completion updates epic's spec status."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        epics_dir = project_dir / ".auto-claude" / "epics"
        epics_dir.mkdir(parents=True)

        # Create and save epic with spec
        epic = Epic(number=1, title="Test Epic", description="Test")
        epic.add_spec(42, "Test Spec", status="pending")
        epic.save(epics_dir)

        manager = EpicLifecycleManager(project_dir)
        manager.registry.epics[1] = EpicEntry(number=1, title="Test Epic", status="active")
        manager.registry.specs[42] = SpecEntry(
            number=42, title="Test Spec", status="pending", epic_number=1
        )

        manager.on_spec_completed(42)

        # Reload epic to check update
        loaded = Epic.load(epics_dir / epic.file_path)
        assert loaded.specs[0].status == "done"

    def test_last_spec_triggers_auto_complete(self, tmp_path):
        """Completing last spec triggers epic auto-completion."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        epics_dir = project_dir / ".auto-claude" / "epics"
        epics_dir.mkdir(parents=True)

        # Create epic with one spec
        epic = Epic(number=1, title="Test Epic", description="Test")
        epic.add_spec(42, "Only Spec", status="pending")
        epic.save(epics_dir)

        manager = EpicLifecycleManager(project_dir)
        manager.registry.epics[1] = EpicEntry(number=1, title="Test Epic", status="active")
        manager.registry.specs[42] = SpecEntry(
            number=42, title="Only Spec", status="pending", epic_number=1
        )

        result = manager.on_spec_completed(42)

        assert result == 1  # Epic number returned
        assert manager.registry.epics[1].status == "completed"

    def test_incomplete_epic_not_auto_completed(self, tmp_path):
        """Epic with pending specs is not auto-completed."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        epics_dir = project_dir / ".auto-claude" / "epics"
        epics_dir.mkdir(parents=True)

        # Create epic with two specs
        epic = Epic(number=1, title="Test Epic", description="Test")
        epic.add_spec(42, "Spec One", status="pending")
        epic.add_spec(43, "Spec Two", status="pending")
        epic.save(epics_dir)

        manager = EpicLifecycleManager(project_dir)
        manager.registry.epics[1] = EpicEntry(number=1, title="Test Epic", status="active")
        manager.registry.specs[42] = SpecEntry(number=42, title="Spec One", status="pending", epic_number=1)
        manager.registry.specs[43] = SpecEntry(number=43, title="Spec Two", status="pending", epic_number=1)

        # Complete only first spec
        result = manager.on_spec_completed(42)

        assert result is None  # No auto-complete
        assert manager.registry.epics[1].status == "active"

    def test_nonexistent_spec_handling(self, tmp_path):
        """Completing non-existent spec is handled gracefully."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".auto-claude").mkdir()

        manager = EpicLifecycleManager(project_dir)

        # Should not raise
        result = manager.on_spec_completed(999)

        assert result is None


class TestCompleteEpic:
    """Tests for manual epic completion."""

    def test_complete_epic_success(self, tmp_path):
        """Epic can be manually completed."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        epics_dir = project_dir / ".auto-claude" / "epics"
        epics_dir.mkdir(parents=True)

        epic = Epic(number=1, title="Test Epic", description="Test")
        epic.add_spec(42, "Spec", status="done")
        epic.save(epics_dir)

        manager = EpicLifecycleManager(project_dir)
        manager.registry.epics[1] = EpicEntry(number=1, title="Test Epic", status="active")

        result = manager.complete_epic(1)

        assert result == 1
        assert manager.registry.epics[1].status == "completed"
        assert manager.registry.epics[1].completed_at is not None

    def test_complete_epic_updates_file(self, tmp_path):
        """Completing epic updates the markdown file."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        epics_dir = project_dir / ".auto-claude" / "epics"
        epics_dir.mkdir(parents=True)

        epic = Epic(number=1, title="Test Epic", description="Test")
        epic.save(epics_dir)

        manager = EpicLifecycleManager(project_dir)
        manager.registry.epics[1] = EpicEntry(number=1, title="Test Epic", status="active")

        manager.complete_epic(1)

        # Reload and check
        loaded = Epic.load(epics_dir / epic.file_path)
        assert loaded.status == EpicStatus.COMPLETED

    def test_complete_nonexistent_epic(self, tmp_path):
        """Completing non-existent epic returns None."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".auto-claude" / "epics").mkdir(parents=True)

        manager = EpicLifecycleManager(project_dir)

        result = manager.complete_epic(999)

        assert result is None


class TestCheckEpicCompletion:
    """Tests for epic completion status checking."""

    def test_check_completion_all_done(self, tmp_path):
        """Check returns complete status when all specs done."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        epics_dir = project_dir / ".auto-claude" / "epics"
        epics_dir.mkdir(parents=True)

        epic = Epic(number=1, title="Test Epic", description="Test")
        epic.add_spec(42, "Spec", status="done")
        epic.save(epics_dir)

        manager = EpicLifecycleManager(project_dir)

        status = manager.check_epic_completion(1)

        assert status["can_complete"] is True
        assert status["specs"]["completed"] == 1
        assert status["specs"]["total"] == 1

    def test_check_completion_partial(self, tmp_path):
        """Check returns progress when specs incomplete."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        epics_dir = project_dir / ".auto-claude" / "epics"
        epics_dir.mkdir(parents=True)

        epic = Epic(number=1, title="Test Epic", description="Test")
        epic.add_spec(42, "Done Spec", status="done")
        epic.add_spec(43, "Pending Spec", status="pending")
        epic.save(epics_dir)

        manager = EpicLifecycleManager(project_dir)

        status = manager.check_epic_completion(1)

        assert status["can_complete"] is False
        assert status["specs"]["completed"] == 1
        assert status["specs"]["total"] == 2
        assert status["specs"]["progress"] == 0.5

    def test_check_completion_not_found(self, tmp_path):
        """Check returns error for non-existent epic."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".auto-claude" / "epics").mkdir(parents=True)

        manager = EpicLifecycleManager(project_dir)

        status = manager.check_epic_completion(999)

        assert "error" in status

    def test_check_completion_includes_criteria(self, tmp_path):
        """Check includes success criteria progress."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        epics_dir = project_dir / ".auto-claude" / "epics"
        epics_dir.mkdir(parents=True)

        from spec.epic import SuccessCriterion

        epic = Epic(number=1, title="Test Epic", description="Test")
        epic.add_spec(42, "Spec", status="done")
        epic.success_criteria = [
            SuccessCriterion(description="Criterion 1", completed=True),
            SuccessCriterion(description="Criterion 2", completed=False),
        ]
        epic.save(epics_dir)

        manager = EpicLifecycleManager(project_dir)

        status = manager.check_epic_completion(1)

        assert status["criteria"]["completed"] == 1
        assert status["criteria"]["total"] == 2
        assert status["can_complete"] is False  # Criteria not all met


class TestAutoCompletionRules:
    """Tests for auto-completion business rules."""

    def test_no_auto_complete_empty_epic(self, tmp_path):
        """Epic with no specs cannot auto-complete."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        epics_dir = project_dir / ".auto-claude" / "epics"
        epics_dir.mkdir(parents=True)

        epic = Epic(number=1, title="Empty Epic", description="No specs")
        epic.save(epics_dir)

        manager = EpicLifecycleManager(project_dir)

        status = manager.check_epic_completion(1)

        assert status["can_complete"] is False

    def test_auto_complete_requires_all_criteria(self, tmp_path):
        """Auto-complete requires all success criteria met."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        epics_dir = project_dir / ".auto-claude" / "epics"
        epics_dir.mkdir(parents=True)

        from spec.epic import SuccessCriterion

        epic = Epic(number=1, title="Test", description="Test")
        epic.add_spec(42, "Spec", status="done")
        epic.success_criteria = [
            SuccessCriterion(description="Must pass", completed=False),
        ]
        epic.save(epics_dir)

        manager = EpicLifecycleManager(project_dir)
        manager.registry.epics[1] = EpicEntry(number=1, title="Test", status="active")
        manager.registry.specs[42] = SpecEntry(number=42, title="Spec", status="pending", epic_number=1)

        # Complete the spec
        result = manager.on_spec_completed(42)

        # Should NOT auto-complete because criteria not met
        assert result is None
        assert manager.registry.epics[1].status == "active"

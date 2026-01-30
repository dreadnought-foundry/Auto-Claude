"""Tests for epic CLI commands.

Tests the apps/backend/cli/epic_commands.py module which provides:
- epic-new: Create a new epic
- epic-list: List all epics
- epic-status: Show epic details
- epic-complete: Manually complete an epic
"""

import json
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "backend"))

from cli.epic_commands import (
    handle_epic_new,
    handle_epic_list,
    handle_epic_status,
    handle_epic_complete,
    get_epics_dir,
)


class TestGetEpicsDir:
    """Tests for epics directory initialization."""

    def test_creates_epics_directory(self, tmp_path):
        """get_epics_dir creates the epics directory."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        epics_dir = get_epics_dir(project_dir)

        assert epics_dir.exists()
        assert epics_dir.name == "epics"

    def test_creates_auto_claude_if_missing(self, tmp_path):
        """get_epics_dir creates .auto-claude if needed."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        epics_dir = get_epics_dir(project_dir)

        assert (project_dir / ".auto-claude").exists()


class TestHandleEpicNew:
    """Tests for epic-new command."""

    def test_creates_epic_file(self, tmp_path):
        """epic-new creates a markdown file."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        result = handle_epic_new(
            project_dir, title="User Auth", description="Authentication system"
        )

        assert result["success"] is True
        assert result["epic_number"] == 1
        assert Path(result["file"]).exists()

    def test_increments_epic_number(self, tmp_path):
        """Epic numbers increment correctly."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        result1 = handle_epic_new(project_dir, title="First Epic")
        result2 = handle_epic_new(project_dir, title="Second Epic")

        assert result1["epic_number"] == 1
        assert result2["epic_number"] == 2

    def test_returns_file_path(self, tmp_path):
        """epic-new returns the file path."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        result = handle_epic_new(project_dir, title="Test Epic")

        assert "file" in result
        assert result["file"].endswith(".md")

    def test_registers_in_registry(self, tmp_path):
        """New epic is registered in registry."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        handle_epic_new(project_dir, title="Test Epic")

        # Check registry was updated
        from spec.registry import Registry

        registry = Registry(project_dir)
        assert 1 in registry.epics


class TestHandleEpicList:
    """Tests for epic-list command."""

    def test_empty_list(self, tmp_path, capsys):
        """epic-list handles no epics gracefully."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        result = handle_epic_list(project_dir)

        assert result == []

    def test_lists_all_epics(self, tmp_path):
        """epic-list returns all epics."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create some epics
        handle_epic_new(project_dir, title="Epic One")
        handle_epic_new(project_dir, title="Epic Two")

        result = handle_epic_list(project_dir)

        assert len(result) == 2
        assert result[0]["title"] == "Epic One"
        assert result[1]["title"] == "Epic Two"

    def test_filters_by_status(self, tmp_path):
        """epic-list can filter by status."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create epics with different statuses
        handle_epic_new(project_dir, title="Active Epic")

        # Manually update registry to have completed epic
        from spec.registry import Registry, EpicEntry

        registry = Registry(project_dir)
        registry.epics[2] = EpicEntry(
            number=2, title="Completed Epic", status="completed"
        )
        registry.counters.next_epic = 3
        registry.save()

        active = handle_epic_list(project_dir, status_filter="active")
        completed = handle_epic_list(project_dir, status_filter="completed")

        assert len(active) == 1
        assert active[0]["title"] == "Active Epic"
        assert len(completed) == 1
        assert completed[0]["title"] == "Completed Epic"

    def test_includes_spec_progress(self, tmp_path):
        """epic-list includes spec completion progress."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create epic and add specs
        from spec.epic import Epic

        epics_dir = project_dir / ".auto-claude" / "epics"
        epics_dir.mkdir(parents=True)

        epic = Epic(number=1, title="Test Epic", description="Test")
        epic.add_spec(42, "Done Spec", status="done")
        epic.add_spec(43, "Pending Spec", status="pending")
        epic.save(epics_dir)

        # Register in registry
        from spec.registry import Registry, EpicEntry

        registry = Registry(project_dir)
        registry.epics[1] = EpicEntry(number=1, title="Test Epic", status="active")
        registry.counters.next_epic = 2
        registry.save()

        result = handle_epic_list(project_dir)

        assert len(result) == 1
        assert result[0]["specs_completed"] == 1
        assert result[0]["specs_total"] == 2


class TestHandleEpicStatus:
    """Tests for epic-status command."""

    def test_shows_epic_details(self, tmp_path):
        """epic-status returns epic details."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create an epic
        handle_epic_new(project_dir, title="Test Epic", description="Description")

        result = handle_epic_status(project_dir, epic_number=1)

        assert "epic" in result
        assert result["epic"]["title"] == "Test Epic"
        assert result["epic"]["number"] == 1

    def test_includes_progress(self, tmp_path):
        """epic-status includes completion progress."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        epics_dir = project_dir / ".auto-claude" / "epics"
        epics_dir.mkdir(parents=True)

        # Create epic with specs
        from spec.epic import Epic

        epic = Epic(number=1, title="Test Epic", description="Test")
        epic.add_spec(42, "Spec", status="done")
        epic.save(epics_dir)

        # Register
        from spec.registry import Registry, EpicEntry

        registry = Registry(project_dir)
        registry.epics[1] = EpicEntry(number=1, title="Test Epic", status="active")
        registry.save()

        result = handle_epic_status(project_dir, epic_number=1)

        assert "progress" in result
        assert result["progress"]["specs"]["completed"] == 1

    def test_not_found(self, tmp_path):
        """epic-status handles non-existent epic."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".auto-claude" / "epics").mkdir(parents=True)

        result = handle_epic_status(project_dir, epic_number=999)

        assert "error" in result


class TestHandleEpicComplete:
    """Tests for epic-complete command."""

    def test_complete_epic(self, tmp_path):
        """epic-complete marks epic as completed."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        epics_dir = project_dir / ".auto-claude" / "epics"
        epics_dir.mkdir(parents=True)

        # Create completable epic
        from spec.epic import Epic

        epic = Epic(number=1, title="Test Epic", description="Test")
        epic.add_spec(42, "Spec", status="done")
        epic.save(epics_dir)

        # Register
        from spec.registry import Registry, EpicEntry

        registry = Registry(project_dir)
        registry.epics[1] = EpicEntry(number=1, title="Test Epic", status="active")
        registry.save()

        result = handle_epic_complete(project_dir, epic_number=1)

        assert result["success"] is True
        assert result["epic_number"] == 1

    def test_cannot_complete_incomplete(self, tmp_path):
        """epic-complete fails for incomplete epic without force."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        epics_dir = project_dir / ".auto-claude" / "epics"
        epics_dir.mkdir(parents=True)

        # Create incomplete epic
        from spec.epic import Epic

        epic = Epic(number=1, title="Test Epic", description="Test")
        epic.add_spec(42, "Spec", status="pending")
        epic.save(epics_dir)

        # Register
        from spec.registry import Registry, EpicEntry

        registry = Registry(project_dir)
        registry.epics[1] = EpicEntry(number=1, title="Test Epic", status="active")
        registry.save()

        result = handle_epic_complete(project_dir, epic_number=1, force=False)

        assert result["success"] is False
        assert result["reason"] == "incomplete"

    def test_force_complete(self, tmp_path):
        """epic-complete with force completes incomplete epic."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        epics_dir = project_dir / ".auto-claude" / "epics"
        epics_dir.mkdir(parents=True)

        # Create incomplete epic
        from spec.epic import Epic

        epic = Epic(number=1, title="Test Epic", description="Test")
        epic.add_spec(42, "Spec", status="pending")
        epic.save(epics_dir)

        # Register
        from spec.registry import Registry, EpicEntry

        registry = Registry(project_dir)
        registry.epics[1] = EpicEntry(number=1, title="Test Epic", status="active")
        registry.save()

        result = handle_epic_complete(project_dir, epic_number=1, force=True)

        assert result["success"] is True

    def test_not_found(self, tmp_path):
        """epic-complete handles non-existent epic."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".auto-claude" / "epics").mkdir(parents=True)

        result = handle_epic_complete(project_dir, epic_number=999)

        assert result["success"] is False
        assert "error" in result


class TestCLIIntegration:
    """Tests for CLI argument parsing integration."""

    def test_epic_new_arg_parsing(self):
        """Verify epic-new args can be parsed."""
        # This would test the argparse integration in main.py
        # Just verify the function signature is compatible
        import inspect

        sig = inspect.signature(handle_epic_new)
        params = list(sig.parameters.keys())

        assert "project_dir" in params
        assert "title" in params

    def test_epic_list_arg_parsing(self):
        """Verify epic-list args can be parsed."""
        import inspect

        sig = inspect.signature(handle_epic_list)
        params = list(sig.parameters.keys())

        assert "project_dir" in params
        assert "status_filter" in params

    def test_epic_status_arg_parsing(self):
        """Verify epic-status args can be parsed."""
        import inspect

        sig = inspect.signature(handle_epic_status)
        params = list(sig.parameters.keys())

        assert "project_dir" in params
        assert "epic_number" in params

    def test_epic_complete_arg_parsing(self):
        """Verify epic-complete args can be parsed."""
        import inspect

        sig = inspect.signature(handle_epic_complete)
        params = list(sig.parameters.keys())

        assert "project_dir" in params
        assert "epic_number" in params
        assert "force" in params

"""Tests for Registry class.

Tests the apps/backend/spec/registry.py module which provides:
- Central registry for specs and epics
- Unique ID generation
- Spec-epic relationships
- JSON persistence
"""

import json
import pytest
import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "backend"))

from spec.registry import (
    Registry,
    SpecEntry,
    EpicEntry,
    Counters,
    REGISTRY_VERSION,
    REGISTRY_FILENAME,
)


class TestRegistryCreation:
    """Tests for Registry initialization."""

    def test_registry_creates_empty(self, tmp_path):
        """New registry starts empty."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        registry = Registry(project_dir)

        assert registry.epics == {}
        assert registry.specs == {}
        assert registry.counters.next_epic == 1
        assert registry.counters.next_spec == 1

    def test_registry_creates_directory(self, tmp_path):
        """Registry ensures .auto-claude directory exists."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        registry = Registry(project_dir)
        registry.save()  # Trigger directory creation

        assert (project_dir / ".auto-claude").exists()

    def test_registry_version(self, tmp_path):
        """Registry has correct version."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        registry = Registry(project_dir)

        assert registry.version == REGISTRY_VERSION


class TestEpicOperations:
    """Tests for epic-related registry operations."""

    def test_allocate_epic_number(self, tmp_path):
        """Epic numbers increment correctly."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        registry = Registry(project_dir)

        num1 = registry.allocate_epic_number()
        num2 = registry.allocate_epic_number()
        num3 = registry.allocate_epic_number()

        assert num1 == 1
        assert num2 == 2
        assert num3 == 3

    def test_register_epic(self, tmp_path):
        """Epics can be registered."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        registry = Registry(project_dir)

        # Create a mock epic (using duck typing)
        class MockEpic:
            number = 1
            title = "Test Epic"
            status = type("Status", (), {"value": "active"})()
            specs = []
            created_at = "2024-01-15T10:00:00"
            completed_at = None

        registry.register_epic(MockEpic())

        assert 1 in registry.epics
        assert registry.epics[1].title == "Test Epic"
        assert registry.epics[1].status == "active"

    def test_update_epic(self, tmp_path):
        """Epic entries can be updated."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        registry = Registry(project_dir)
        registry.epics[1] = EpicEntry(number=1, title="Test", status="active")

        result = registry.update_epic(1, status="completed")

        assert result is True
        assert registry.epics[1].status == "completed"

    def test_update_epic_not_found(self, tmp_path):
        """Updating non-existent epic returns False."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        registry = Registry(project_dir)
        result = registry.update_epic(999, status="completed")

        assert result is False

    def test_get_epic(self, tmp_path):
        """Epic can be retrieved by number."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        registry = Registry(project_dir)
        registry.epics[1] = EpicEntry(number=1, title="Test", status="active")

        entry = registry.get_epic(1)

        assert entry is not None
        assert entry.title == "Test"

    def test_get_epic_not_found(self, tmp_path):
        """Getting non-existent epic returns None."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        registry = Registry(project_dir)
        entry = registry.get_epic(999)

        assert entry is None

    def test_list_epics(self, tmp_path):
        """Epics can be listed."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        registry = Registry(project_dir)
        registry.epics[1] = EpicEntry(number=1, title="Alpha", status="active")
        registry.epics[2] = EpicEntry(number=2, title="Beta", status="completed")

        epics = registry.list_epics()

        assert len(epics) == 2
        assert epics[0].number == 1  # Sorted by number

    def test_list_epics_filtered(self, tmp_path):
        """Epics can be filtered by status."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        registry = Registry(project_dir)
        registry.epics[1] = EpicEntry(number=1, title="Alpha", status="active")
        registry.epics[2] = EpicEntry(number=2, title="Beta", status="completed")

        active = registry.list_epics(status="active")
        completed = registry.list_epics(status="completed")

        assert len(active) == 1
        assert active[0].title == "Alpha"
        assert len(completed) == 1
        assert completed[0].title == "Beta"


class TestSpecOperations:
    """Tests for spec-related registry operations."""

    def test_allocate_spec_number(self, tmp_path):
        """Spec numbers increment correctly."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        registry = Registry(project_dir)

        num1 = registry.allocate_spec_number()
        num2 = registry.allocate_spec_number()

        assert num1 == 1
        assert num2 == 2

    def test_register_spec(self, tmp_path):
        """Specs can be registered."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        registry = Registry(project_dir)
        registry.register_spec(42, "test-feature")

        assert 42 in registry.specs
        assert registry.specs[42].title == "test-feature"
        assert registry.specs[42].status == "pending"

    def test_register_spec_with_epic(self, tmp_path):
        """Specs can be registered with epic association."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        registry = Registry(project_dir)
        registry.epics[1] = EpicEntry(number=1, title="Test", status="active")
        registry.register_spec(42, "test-feature", epic_number=1)

        assert registry.specs[42].epic_number == 1
        assert registry.epics[1].spec_count == 1

    def test_update_spec_status(self, tmp_path):
        """Spec status can be updated."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        registry = Registry(project_dir)
        registry.specs[42] = SpecEntry(number=42, title="test", status="pending")

        result = registry.update_spec_status(42, "complete")

        assert result is True
        assert registry.specs[42].status == "complete"
        assert registry.specs[42].completed_at is not None

    def test_update_spec_status_not_found(self, tmp_path):
        """Updating non-existent spec returns False."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        registry = Registry(project_dir)
        result = registry.update_spec_status(999, "complete")

        assert result is False

    def test_get_spec(self, tmp_path):
        """Spec can be retrieved by number."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        registry = Registry(project_dir)
        registry.specs[42] = SpecEntry(number=42, title="test", status="pending")

        entry = registry.get_spec(42)

        assert entry is not None
        assert entry.title == "test"

    def test_get_specs_for_epic(self, tmp_path):
        """Specs for a specific epic can be retrieved."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        registry = Registry(project_dir)
        registry.specs[42] = SpecEntry(number=42, title="a", status="pending", epic_number=1)
        registry.specs[43] = SpecEntry(number=43, title="b", status="pending", epic_number=1)
        registry.specs[44] = SpecEntry(number=44, title="c", status="pending", epic_number=2)

        epic1_specs = registry.get_specs_for_epic(1)
        epic2_specs = registry.get_specs_for_epic(2)

        assert len(epic1_specs) == 2
        assert len(epic2_specs) == 1

    def test_assign_spec_to_epic(self, tmp_path):
        """Specs can be assigned to epics."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        registry = Registry(project_dir)
        registry.epics[1] = EpicEntry(number=1, title="Test", status="active", spec_count=0)
        registry.specs[42] = SpecEntry(number=42, title="test", status="pending")

        result = registry.assign_spec_to_epic(42, 1)

        assert result is True
        assert registry.specs[42].epic_number == 1
        assert registry.epics[1].spec_count == 1

    def test_reassign_spec_updates_counts(self, tmp_path):
        """Reassigning spec updates old and new epic counts."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        registry = Registry(project_dir)
        registry.epics[1] = EpicEntry(number=1, title="Epic 1", status="active", spec_count=1)
        registry.epics[2] = EpicEntry(number=2, title="Epic 2", status="active", spec_count=0)
        registry.specs[42] = SpecEntry(number=42, title="test", status="pending", epic_number=1)

        result = registry.assign_spec_to_epic(42, 2)

        assert result is True
        assert registry.epics[1].spec_count == 0
        assert registry.epics[2].spec_count == 1


class TestRegistryPersistence:
    """Tests for Registry save/load functionality."""

    def test_save_creates_file(self, tmp_path):
        """Save creates registry.json file."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".auto-claude").mkdir()

        registry = Registry(project_dir)
        registry.epics[1] = EpicEntry(number=1, title="Test", status="active")
        registry.save()

        registry_path = project_dir / ".auto-claude" / REGISTRY_FILENAME
        assert registry_path.exists()

    def test_save_json_format(self, tmp_path):
        """Saved registry is valid JSON."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".auto-claude").mkdir()

        registry = Registry(project_dir)
        registry.counters.next_spec = 5
        registry.save()

        registry_path = project_dir / ".auto-claude" / REGISTRY_FILENAME
        data = json.loads(registry_path.read_text())

        assert data["version"] == REGISTRY_VERSION
        assert data["counters"]["nextSpec"] == 5

    def test_load_persisted_data(self, tmp_path):
        """Registry loads persisted data on init."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        auto_claude_dir = project_dir / ".auto-claude"
        auto_claude_dir.mkdir()

        # Create initial registry and save
        registry1 = Registry(project_dir)
        registry1.epics[1] = EpicEntry(number=1, title="Test", status="active")
        registry1.specs[42] = SpecEntry(number=42, title="spec", status="pending")
        registry1.counters.next_epic = 10
        registry1.save()

        # Load in new instance
        registry2 = Registry(project_dir)

        assert 1 in registry2.epics
        assert 42 in registry2.specs
        assert registry2.counters.next_epic == 10

    def test_counters_persist_across_sessions(self, tmp_path):
        """Counter values persist across registry instances."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".auto-claude").mkdir()

        # Allocate some numbers
        registry1 = Registry(project_dir)
        registry1.allocate_epic_number()
        registry1.allocate_epic_number()
        registry1.allocate_spec_number()

        # Load new instance
        registry2 = Registry(project_dir)

        assert registry2.counters.next_epic == 3
        assert registry2.counters.next_spec == 2


class TestRegistryMigration:
    """Tests for migrating existing specs to registry."""

    def test_scan_existing_specs(self, tmp_path):
        """Registry scans existing specs on first init."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        specs_dir = project_dir / ".auto-claude" / "specs"
        specs_dir.mkdir(parents=True)

        # Create existing spec directories
        (specs_dir / "001-first-spec").mkdir()
        (specs_dir / "002-second-spec").mkdir()

        registry = Registry(project_dir)

        # Should have detected existing specs
        assert registry.counters.next_spec >= 3

    def test_migration_preserves_existing_registry(self, tmp_path):
        """Migration doesn't overwrite existing registry."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        auto_claude_dir = project_dir / ".auto-claude"
        auto_claude_dir.mkdir()

        # Create existing registry with custom data
        registry_data = {
            "version": REGISTRY_VERSION,
            "epics": {"1": {"number": 1, "title": "Existing", "status": "active", "spec_count": 0}},
            "specs": {},
            "counters": {"nextEpic": 99, "nextSpec": 99},
        }
        (auto_claude_dir / REGISTRY_FILENAME).write_text(json.dumps(registry_data))

        # Load registry
        registry = Registry(project_dir)

        # Should preserve existing data, not rebuild
        assert registry.counters.next_epic == 99
        assert 1 in registry.epics


class TestDataclasses:
    """Tests for registry dataclasses."""

    def test_spec_entry_defaults(self):
        """SpecEntry has correct defaults."""
        entry = SpecEntry(number=1, title="test", status="pending")

        assert entry.epic_number is None
        assert entry.completed_at is None

    def test_epic_entry_defaults(self):
        """EpicEntry has correct defaults."""
        entry = EpicEntry(number=1, title="test", status="active")

        assert entry.spec_count == 0
        assert entry.completed_at is None

    def test_counters_defaults(self):
        """Counters has correct defaults."""
        counters = Counters()

        assert counters.next_epic == 1
        assert counters.next_spec == 1

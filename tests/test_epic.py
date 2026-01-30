"""Tests for Epic class and operations.

Tests the apps/backend/spec/epic.py module which provides:
- Epic class definition
- Markdown serialization/parsing
- Spec tracking within epics
- Completion detection
"""

import json
import pytest
import sys
from datetime import datetime
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "backend"))

from spec.epic import (
    Epic,
    EpicSpec,
    EpicStatus,
    SuccessCriterion,
)


class TestEpicCreation:
    """Tests for Epic instantiation."""

    def test_epic_basic_creation(self):
        """Epic can be created with required fields."""
        epic = Epic(number=1, title="User Auth", description="Auth system")

        assert epic.number == 1
        assert epic.title == "User Auth"
        assert epic.description == "Auth system"
        assert epic.status == EpicStatus.ACTIVE
        assert epic.specs == []
        assert epic.success_criteria == []

    def test_epic_with_status(self):
        """Epic can be created with explicit status."""
        epic = Epic(
            number=1,
            title="Test",
            description="Test epic",
            status=EpicStatus.COMPLETED,
        )
        assert epic.status == EpicStatus.COMPLETED

    def test_epic_created_at_auto_set(self):
        """Epic created_at is auto-populated."""
        epic = Epic(number=1, title="Test", description="Test")

        # Should be a valid ISO timestamp
        assert epic.created_at is not None
        # Should parse without error
        datetime.fromisoformat(epic.created_at)


class TestEpicSlugify:
    """Tests for Epic folder name generation."""

    def test_folder_name_basic(self):
        """Folder name uses number and slugified title."""
        epic = Epic(number=1, title="User Auth", description="Test")
        assert epic.folder_name == "001-user-auth"

    def test_folder_name_special_chars(self):
        """Special characters are removed from folder name."""
        epic = Epic(number=42, title="Auth & Security!", description="Test")
        # Should handle special chars gracefully
        folder = epic.folder_name
        assert folder.startswith("042-")
        assert "&" not in folder
        assert "!" not in folder

    def test_folder_name_padding(self):
        """Epic number is zero-padded to 3 digits."""
        epic = Epic(number=7, title="Small Epic", description="Test")
        assert epic.folder_name.startswith("007-")

    def test_file_path_includes_extension(self):
        """File path includes .md extension."""
        epic = Epic(number=1, title="Test Epic", description="Test")
        assert epic.file_path.endswith(".md")
        assert epic.file_path == f"{epic.folder_name}.md"


class TestEpicSpecManagement:
    """Tests for adding/updating/removing specs from epics."""

    def test_add_spec(self):
        """Specs can be added to an epic."""
        epic = Epic(number=1, title="Test", description="Test")
        epic.add_spec(42, "User Login")

        assert len(epic.specs) == 1
        assert epic.specs[0].spec_number == 42
        assert epic.specs[0].title == "User Login"
        assert epic.specs[0].status == "pending"

    def test_add_spec_with_status(self):
        """Specs can be added with initial status."""
        epic = Epic(number=1, title="Test", description="Test")
        epic.add_spec(42, "User Login", status="in_progress")

        assert epic.specs[0].status == "in_progress"

    def test_add_multiple_specs(self):
        """Multiple specs can be added."""
        epic = Epic(number=1, title="Test", description="Test")
        epic.add_spec(42, "Login")
        epic.add_spec(43, "Logout")
        epic.add_spec(44, "Session")

        assert len(epic.specs) == 3
        assert [s.spec_number for s in epic.specs] == [42, 43, 44]

    def test_update_spec_status(self):
        """Spec status can be updated."""
        epic = Epic(number=1, title="Test", description="Test")
        epic.add_spec(42, "Login")

        result = epic.update_spec_status(42, "done")

        assert result is True
        assert epic.specs[0].status == "done"

    def test_update_spec_status_not_found(self):
        """Updating non-existent spec returns False."""
        epic = Epic(number=1, title="Test", description="Test")
        epic.add_spec(42, "Login")

        result = epic.update_spec_status(999, "done")

        assert result is False

    def test_remove_spec(self):
        """Specs can be removed from epic."""
        epic = Epic(number=1, title="Test", description="Test")
        epic.add_spec(42, "Login")
        epic.add_spec(43, "Logout")

        result = epic.remove_spec(42)

        assert result is True
        assert len(epic.specs) == 1
        assert epic.specs[0].spec_number == 43

    def test_remove_spec_not_found(self):
        """Removing non-existent spec returns False."""
        epic = Epic(number=1, title="Test", description="Test")

        result = epic.remove_spec(999)

        assert result is False


class TestEpicCompletion:
    """Tests for epic completion detection."""

    def test_check_complete_no_specs(self):
        """Epic with no specs cannot be complete."""
        epic = Epic(number=1, title="Test", description="Test")

        assert epic.check_complete() is False

    def test_check_complete_all_done(self):
        """Epic is complete when all specs are done."""
        epic = Epic(number=1, title="Test", description="Test")
        epic.add_spec(42, "Login", status="done")
        epic.add_spec(43, "Logout", status="done")

        assert epic.check_complete() is True

    def test_check_complete_some_pending(self):
        """Epic is incomplete when some specs are pending."""
        epic = Epic(number=1, title="Test", description="Test")
        epic.add_spec(42, "Login", status="done")
        epic.add_spec(43, "Logout", status="pending")

        assert epic.check_complete() is False

    def test_check_complete_with_criteria(self):
        """Epic completion considers success criteria."""
        epic = Epic(number=1, title="Test", description="Test")
        epic.add_spec(42, "Login", status="done")
        epic.success_criteria = [
            SuccessCriterion(description="Test passes", completed=True),
        ]

        assert epic.check_complete() is True

    def test_check_complete_criteria_not_met(self):
        """Epic incomplete when success criteria not met."""
        epic = Epic(number=1, title="Test", description="Test")
        epic.add_spec(42, "Login", status="done")
        epic.success_criteria = [
            SuccessCriterion(description="Test passes", completed=False),
        ]

        assert epic.check_complete() is False


class TestEpicMarkdownSerialization:
    """Tests for Epic to/from markdown conversion."""

    def test_to_markdown_basic(self):
        """Epic serializes to markdown format."""
        epic = Epic(
            number=1,
            title="User Auth",
            description="Authentication system",
            status=EpicStatus.ACTIVE,
        )
        epic.add_spec(42, "Login", status="done")

        md = epic.to_markdown()

        assert "# Epic 1: User Auth" in md
        assert "Authentication system" in md
        assert "| 042 | Login" in md or "| 42 | Login" in md

    def test_to_markdown_includes_criteria(self):
        """Markdown includes success criteria."""
        epic = Epic(number=1, title="Test", description="Test")
        epic.success_criteria = [
            SuccessCriterion(description="Users can login", completed=True),
            SuccessCriterion(description="Sessions persist", completed=False),
        ]

        md = epic.to_markdown()

        assert "Users can login" in md
        assert "Sessions persist" in md
        # Check for checkbox format
        assert "[x]" in md or "- [x]" in md

    def test_to_markdown_includes_metadata(self):
        """Markdown includes metadata comment."""
        epic = Epic(number=1, title="Test", description="Test")

        md = epic.to_markdown()

        # Should have metadata as comment at end
        assert "metadata:" in md or '"status"' in md

    def test_from_markdown_basic(self):
        """Epic can be parsed from markdown."""
        md = """# Epic 1: User Auth

## Overview
Authentication system for users.

## Success Criteria
- [ ] Users can login
- [x] Sessions persist

## Specs
| Spec | Title | Status |
|------|-------|--------|
| 042 | Login | done |
| 043 | Logout | pending |

---
<!-- metadata: {"status": "active", "created_at": "2024-01-15T10:00:00"} -->
"""
        epic = Epic.from_markdown(md, 1)

        assert epic.number == 1
        assert epic.title == "User Auth"
        assert "Authentication" in epic.description
        assert len(epic.specs) == 2
        assert len(epic.success_criteria) == 2

    def test_roundtrip_serialization(self):
        """Epic survives to_markdown -> from_markdown."""
        original = Epic(
            number=5,
            title="Complex Epic",
            description="A multi-feature epic",
            status=EpicStatus.ACTIVE,
        )
        original.add_spec(100, "Feature A", status="done")
        original.add_spec(101, "Feature B", status="in_progress")
        original.success_criteria = [
            SuccessCriterion(description="All tests pass", completed=False),
        ]

        md = original.to_markdown()
        restored = Epic.from_markdown(md, 5)

        assert restored.number == original.number
        assert restored.title == original.title
        assert len(restored.specs) == 2
        assert len(restored.success_criteria) == 1


class TestEpicPersistence:
    """Tests for Epic save/load to filesystem."""

    def test_save_creates_file(self, tmp_path):
        """Save creates markdown file in epics directory."""
        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()

        epic = Epic(number=1, title="Test Epic", description="Test")
        file_path = epic.save(epics_dir)

        assert file_path.exists()
        assert file_path.name == epic.file_path

    def test_load_from_file(self, tmp_path):
        """Epic can be loaded from saved file."""
        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()

        original = Epic(number=1, title="Test Epic", description="Test description")
        original.add_spec(42, "Test Spec", status="done")
        saved_path = original.save(epics_dir)

        loaded = Epic.load(saved_path)

        assert loaded is not None
        assert loaded.number == original.number
        assert loaded.title == original.title

    def test_load_nonexistent_returns_none(self, tmp_path):
        """Loading non-existent file returns None."""
        result = Epic.load(tmp_path / "nonexistent.md")
        assert result is None


class TestEpicStatus:
    """Tests for EpicStatus enum."""

    def test_status_values(self):
        """All expected status values exist."""
        assert EpicStatus.ACTIVE.value == "active"
        assert EpicStatus.COMPLETED.value == "completed"
        assert EpicStatus.ARCHIVED.value == "archived"

    def test_status_is_string_enum(self):
        """Status enum is string-based for JSON compatibility."""
        assert EpicStatus.ACTIVE == "active"


class TestEpicSpec:
    """Tests for EpicSpec dataclass."""

    def test_epic_spec_creation(self):
        """EpicSpec can be created with required fields."""
        spec = EpicSpec(spec_number=42, title="Test Spec")

        assert spec.spec_number == 42
        assert spec.title == "Test Spec"
        assert spec.status == "pending"

    def test_epic_spec_with_status(self):
        """EpicSpec can be created with status."""
        spec = EpicSpec(spec_number=42, title="Test", status="done")
        assert spec.status == "done"


class TestSuccessCriterion:
    """Tests for SuccessCriterion dataclass."""

    def test_criterion_creation(self):
        """SuccessCriterion can be created."""
        criterion = SuccessCriterion(description="Users can login")

        assert criterion.description == "Users can login"
        assert criterion.completed is False
        assert criterion.completed_at is None

    def test_criterion_completed(self):
        """SuccessCriterion tracks completion."""
        criterion = SuccessCriterion(
            description="Test",
            completed=True,
            completed_at="2024-01-15T10:00:00",
        )

        assert criterion.completed is True
        assert criterion.completed_at is not None

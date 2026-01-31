#!/usr/bin/env python3
"""Sync unified_state.py from Auto Claude to Maestro.

Auto Claude is the source of truth for unified_state.py since it has
comprehensive test coverage (40+ tests, 95% coverage).

This script:
1. Copies apps/backend/spec/unified_state.py to ~/.claude/scripts/sprint_automation/utils/
2. Adjusts the module docstring to reflect it's a copy
3. Runs cross-system integration tests to verify compatibility

Usage:
    python scripts/sync_unified_state.py [--dry-run] [--no-test]
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# Paths
AUTO_CLAUDE_ROOT = Path(__file__).parent.parent
SOURCE_FILE = AUTO_CLAUDE_ROOT / "apps" / "backend" / "spec" / "unified_state.py"
MAESTRO_DIR = Path.home() / ".claude" / "scripts" / "sprint_automation" / "utils"
TARGET_FILE = MAESTRO_DIR / "unified_state.py"
TEST_FILE = Path.home() / ".claude" / "tests" / "test_cross_system_integration.py"


def sync_file(dry_run: bool = False) -> bool:
    """Copy unified_state.py from Auto Claude to Maestro."""
    if not SOURCE_FILE.exists():
        print(f"❌ Source file not found: {SOURCE_FILE}")
        return False

    if not MAESTRO_DIR.exists():
        print(f"❌ Maestro utils directory not found: {MAESTRO_DIR}")
        return False

    # Read source
    content = SOURCE_FILE.read_text()

    # Update docstring to indicate it's a copy
    old_docstring = '''"""Unified state operations for project-level task state.

Provides read/write access to the unified task state format that both
Maestro (Claude Code workflow) and Auto Claude (autonomous agent pipeline)
can use.

State Location: {project}/.claude/task-state.json

This module is designed to be duplicated in Maestro scripts (~/.claude/scripts/)
to avoid cross-repository dependencies while maintaining identical behavior.'''

    new_docstring = '''"""Unified state operations for project-level task state.

Provides read/write access to the unified task state format that both
Maestro (Claude Code workflow) and Auto Claude (autonomous agent pipeline)
can use.

State Location: {project}/.claude/task-state.json

This module is duplicated in Auto Claude backend (apps/backend/spec/unified_state.py)
to avoid cross-repository dependencies while maintaining identical behavior.'''

    content = content.replace(old_docstring, new_docstring)

    if dry_run:
        print(f"Would copy: {SOURCE_FILE}")
        print(f"        to: {TARGET_FILE}")
        print(f"\nFirst 500 chars of content:\n{content[:500]}...")
        return True

    # Backup existing file
    if TARGET_FILE.exists():
        backup = TARGET_FILE.with_suffix(".py.bak")
        shutil.copy2(TARGET_FILE, backup)
        print(f"📦 Backed up existing file to: {backup}")

    # Write to target
    TARGET_FILE.write_text(content)
    print(f"✅ Synced: {SOURCE_FILE.name}")
    print(f"   From: {SOURCE_FILE}")
    print(f"   To:   {TARGET_FILE}")

    return True


def run_tests() -> bool:
    """Run cross-system integration tests."""
    if not TEST_FILE.exists():
        print(f"⚠️  Test file not found: {TEST_FILE}")
        print("   Skipping integration tests")
        return True

    print("\n🧪 Running cross-system integration tests...")
    result = subprocess.run(
        [sys.executable, str(TEST_FILE)],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print(result.stdout)
        return True
    else:
        print("❌ Tests failed!")
        print(result.stdout)
        print(result.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Sync unified_state.py from Auto Claude to Maestro"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--no-test",
        action="store_true",
        help="Skip running integration tests after sync",
    )
    args = parser.parse_args()

    print("🔄 Unified State Sync")
    print("=" * 40)

    # Sync the file
    if not sync_file(dry_run=args.dry_run):
        sys.exit(1)

    if args.dry_run:
        print("\n(Dry run - no changes made)")
        return

    # Run tests unless skipped
    if not args.no_test:
        if not run_tests():
            print("\n⚠️  Sync completed but tests failed!")
            print("   Consider reverting: cp ~/.claude/scripts/sprint_automation/utils/unified_state.py.bak ~/.claude/scripts/sprint_automation/utils/unified_state.py")
            sys.exit(1)

    print("\n✅ Sync complete!")


if __name__ == "__main__":
    main()

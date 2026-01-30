"""
Epic Commands
=============

CLI commands for managing epics.

Commands:
    epic-new       Create a new epic
    epic-list      List all epics
    epic-status    Show epic details
    epic-complete  Manually complete an epic
"""

import sys
from pathlib import Path

# Ensure parent directory is in path
_PARENT_DIR = Path(__file__).parent.parent
if str(_PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(_PARENT_DIR))

from ui import (  # noqa: E402
    Icons,
    bold,
    box,
    highlight,
    icon,
    print_status,
)


def get_epics_dir(project_dir: Path) -> Path:
    """Get the epics directory, creating if needed."""
    from init import init_auto_claude_dir

    init_auto_claude_dir(project_dir)
    epics_dir = project_dir / ".auto-claude" / "epics"
    epics_dir.mkdir(exist_ok=True)
    return epics_dir


def handle_epic_new(
    project_dir: Path,
    title: str,
    description: str = "",
    interactive: bool = False,
) -> dict:
    """
    Create a new epic.

    Args:
        project_dir: Project root directory
        title: Epic title
        description: Epic description
        interactive: If True, prompt for success criteria

    Returns:
        Dict with epic details or error
    """
    from spec.epic import Epic, SuccessCriterion
    from spec.registry import Registry

    epics_dir = get_epics_dir(project_dir)
    registry = Registry(project_dir)

    # Allocate epic number
    epic_number = registry.allocate_epic_number()

    # Create epic
    epic = Epic(
        number=epic_number,
        title=title,
        description=description or f"Epic {epic_number}: {title}",
    )

    # Interactive mode: prompt for success criteria
    if interactive:
        print_status(f"Creating Epic {epic_number}: {title}", "info")
        print("\nEnter success criteria (empty line to finish):")
        while True:
            try:
                criterion = input("  - ").strip()
            except EOFError:
                break
            if not criterion:
                break
            epic.success_criteria.append(SuccessCriterion(description=criterion))

    # Save epic and register
    epic.save(epics_dir)
    registry.register_epic(epic)

    print_status(f"Created epic: {highlight(epic.folder_name)}", "success")

    return {
        "success": True,
        "epic_number": epic_number,
        "title": title,
        "file": str(epics_dir / epic.file_path),
    }


def handle_epic_list(
    project_dir: Path, status_filter: str = None
) -> list[dict]:
    """
    List all epics.

    Args:
        project_dir: Project root directory
        status_filter: Optional filter by status (active/completed/archived)

    Returns:
        List of epic summaries
    """
    from spec.registry import Registry
    from spec.epic import Epic

    epics_dir = get_epics_dir(project_dir)
    registry = Registry(project_dir)

    entries = registry.list_epics(status=status_filter)

    if not entries:
        print_status("No epics found", "info")
        return []

    print("\n" + bold("EPICS"))
    print("-" * 60)

    results = []
    for entry in entries:
        # Load full epic for spec details
        epic = None
        for file in epics_dir.glob(f"{entry.number:03d}-*.md"):
            epic = Epic.load(file)
            break

        specs_done = 0
        specs_total = 0
        if epic:
            specs_total = len(epic.specs)
            specs_done = sum(1 for s in epic.specs if s.status == "done")

        status_icon = {
            "active": icon(Icons.IN_PROGRESS),
            "completed": icon(Icons.SUCCESS),
            "archived": icon(Icons.INFO),
        }.get(entry.status, "")

        print(f"  {status_icon} {entry.number:03d} - {entry.title}")
        print(f"       Status: {entry.status} | Specs: {specs_done}/{specs_total}")

        results.append(
            {
                "number": entry.number,
                "title": entry.title,
                "status": entry.status,
                "specs_completed": specs_done,
                "specs_total": specs_total,
            }
        )

    print("-" * 60)
    return results


def handle_epic_status(project_dir: Path, epic_number: int) -> dict:
    """
    Show detailed epic status.

    Args:
        project_dir: Project root directory
        epic_number: Epic number to show

    Returns:
        Epic details dict
    """
    from spec.epic_lifecycle import get_lifecycle_manager
    from spec.epic import Epic

    epics_dir = get_epics_dir(project_dir)
    lifecycle = get_lifecycle_manager(project_dir)

    status = lifecycle.check_epic_completion(epic_number)

    if "error" in status:
        print_status(status["error"], "error")
        return status

    # Load full epic for detailed display
    epic = None
    for file in epics_dir.glob(f"{epic_number:03d}-*.md"):
        epic = Epic.load(file)
        break

    if not epic:
        return {"error": "Epic file not found"}

    # Print detailed status
    print(
        "\n"
        + box(
            [
                bold(f"Epic {epic_number}: {epic.title}"),
                "",
                (
                    epic.description[:100] + "..."
                    if len(epic.description) > 100
                    else epic.description
                ),
            ],
            width=70,
        )
    )

    print(f"\nStatus: {epic.status.value}")
    print(f"Created: {epic.created_at}")
    if epic.completed_at:
        print(f"Completed: {epic.completed_at}")

    # Success criteria
    if epic.success_criteria:
        print(f"\n{bold('Success Criteria')}")
        for criterion in epic.success_criteria:
            check = icon(Icons.SUCCESS) if criterion.completed else "[ ]"
            print(f"  {check} {criterion.description}")

    # Specs
    if epic.specs:
        print(f"\n{bold('Specs')}")
        print("  | Spec | Title | Status |")
        print("  |------|-------|--------|")
        for spec in epic.specs:
            status_icon = {
                "done": icon(Icons.SUCCESS),
                "in_progress": icon(Icons.IN_PROGRESS),
                "pending": icon(Icons.PENDING),
            }.get(spec.status, "")
            # Truncate title to fit
            if len(spec.title) > 25:
                title_display = spec.title[:25] + "..."
            else:
                title_display = spec.title
            print(f"  | {spec.spec_number:03d} | {title_display:<28} | "
                  f"{status_icon} {spec.status} |")

    # Progress summary
    print(f"\n{bold('Progress')}")
    specs_pct = status['specs']['progress'] * 100
    print(f"  Specs: {status['specs']['completed']}/{status['specs']['total']} "
          f"({specs_pct:.0f}%)")
    if status["criteria"]["total"] > 0:
        crit_pct = status['criteria']['progress'] * 100
        print(f"  Criteria: {status['criteria']['completed']}/"
              f"{status['criteria']['total']} ({crit_pct:.0f}%)")

    return {
        "epic": {
            "number": epic.number,
            "title": epic.title,
            "status": epic.status.value,
            "description": epic.description,
        },
        "progress": status,
    }


def handle_epic_complete(
    project_dir: Path, epic_number: int, force: bool = False
) -> dict:
    """
    Manually complete an epic.

    Args:
        project_dir: Project root directory
        epic_number: Epic to complete
        force: Force completion even if criteria not met

    Returns:
        Result dict
    """
    from spec.epic_lifecycle import get_lifecycle_manager

    # Ensure epics dir exists
    get_epics_dir(project_dir)

    lifecycle = get_lifecycle_manager(project_dir)
    status = lifecycle.check_epic_completion(epic_number)

    if "error" in status:
        print_status(status["error"], "error")
        return {"success": False, "error": status["error"]}

    if not status["can_complete"] and not force:
        print_status(
            "Epic cannot be completed - not all specs/criteria are done", "warning"
        )
        print(f"  Specs: {status['specs']['completed']}/{status['specs']['total']}")
        crit_done = status['criteria']['completed']
        crit_total = status['criteria']['total']
        print(f"  Criteria: {crit_done}/{crit_total}")
        print("\nUse --force to complete anyway")
        return {"success": False, "reason": "incomplete"}

    result = lifecycle.complete_epic(epic_number)

    if result:
        print_status(f"Completed epic {epic_number}: {status['title']}", "success")
        return {"success": True, "epic_number": result}
    else:
        print_status("Failed to complete epic", "error")
        return {"success": False, "error": "Failed to complete"}

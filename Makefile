.PHONY: claude dev start test test-backend test-maestro test-unified sync-unified run list help

# Get the directory where this Makefile lives (works from any directory)
MAKEFILE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

# Show available commands
help:
	@echo "Auto-Claude Make Commands:"
	@echo ""
	@echo "  make dev           - Start Electron app in dev mode (HMR)"
	@echo "  make start         - Start Electron app in production mode"
	@echo "  make run SPEC=001  - Run backend CLI on a spec"
	@echo "  make list          - List all specs"
	@echo "  make test          - Run frontend tests"
	@echo "  make test-backend  - Run backend tests"
	@echo "  make test-maestro  - Run Maestro integration tests"
	@echo "  make test-unified  - Run unified state tests (Auto Claude + cross-system)"
	@echo "  make sync-unified  - Sync unified_state.py to Maestro"
	@echo "  make claude        - Start Claude Code (skip permissions)"
	@echo ""
	@echo "Backend CLI examples:"
	@echo "  make run SPEC=001                    # Run spec 001"
	@echo "  make run SPEC=001 ARGS='--qa'        # Run QA on spec"
	@echo "  make run SPEC=001 ARGS='--postmortem' # Generate postmortem"
	@echo "  make run SPEC=001 ARGS='--review'    # Review spec changes"

# Claude Code with skip permissions
claude:
	cd "$(MAKEFILE_DIR)" && claude --dangerously-skip-permissions

# Development mode (Electron + Vite HMR)
dev:
	cd "$(MAKEFILE_DIR)apps/frontend" && npm run dev

# Production mode
start:
	cd "$(MAKEFILE_DIR)apps/frontend" && npm start

# Run backend CLI (use: make run SPEC=001 or make run SPEC=001 ARGS='--qa')
run:
ifndef SPEC
	@echo "Usage: make run SPEC=<spec-number> [ARGS='<additional-args>']"
	@echo "Example: make run SPEC=001"
	@echo "         make run SPEC=001 ARGS='--postmortem'"
	@exit 1
endif
	cd "$(MAKEFILE_DIR)apps/backend" && uv run python run.py --spec $(SPEC) $(ARGS)

# List all specs
list:
	cd "$(MAKEFILE_DIR)apps/backend" && uv run python run.py --list

# Run all frontend tests
test:
	cd "$(MAKEFILE_DIR)apps/frontend" && npm test

# Run backend tests
test-backend:
	cd "$(MAKEFILE_DIR)apps/backend" && uv run pytest tests/ -v

# Run Maestro integration tests
test-maestro:
	cd "$(MAKEFILE_DIR)apps/backend" && uv run pytest tests/test_maestro_state_bridge.py tests/test_postmortem.py tests/test_sprint_types.py -v

# Run unified state tests (Auto Claude + cross-system)
test-unified:
	cd "$(MAKEFILE_DIR)apps/backend" && uv run pytest spec/tests/test_unified_state.py -v
	python3 ~/.claude/tests/test_cross_system_integration.py

# Sync unified_state.py from Auto Claude to Maestro
sync-unified:
	python3 "$(MAKEFILE_DIR)scripts/sync_unified_state.py"

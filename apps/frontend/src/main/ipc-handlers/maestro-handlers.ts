/**
 * Maestro IPC Handlers
 *
 * Handles Maestro unified state operations for the pipeline integration.
 * Watches the unified state file ({project}/.claude/task-state.json) and
 * sends updates to the renderer for real-time Kanban board updates.
 */

import { ipcMain, BrowserWindow } from 'electron';
import { existsSync } from 'node:fs';
import * as path from 'node:path';
import { IPC_CHANNELS } from '../../shared/constants';
import type { IPCResult, MaestroQualityGateResult } from '../../shared/types';
import { projectStore } from '../project-store';
import { TerminalManager } from '../terminal-manager';
import { readSettingsFileAsync } from '../settings-utils';
import {
  readUnifiedState,
  watchUnifiedState,
  stopWatching,
  sendStateToRenderer,
  type UnifiedTaskState,
} from '../agent/maestro-watcher';

/**
 * Active watcher cleanup functions by project ID
 */
const activeWatcherCleanups = new Map<string, () => void>();

/**
 * Register Maestro state IPC handlers
 */
export function registerMaestroHandlers(
  terminalManager: TerminalManager,
  getMainWindow: () => BrowserWindow | null
): void {
  /**
   * Get current unified state for a project
   */
  ipcMain.handle(
    IPC_CHANNELS.MAESTRO_STATE_GET,
    async (_, projectId: string): Promise<IPCResult<UnifiedTaskState | null>> => {
      const project = projectStore.getProject(projectId);
      if (!project) {
        return { success: false, error: 'Project not found' };
      }

      try {
        const state = await readUnifiedState(project.path);
        return { success: true, data: state };
      } catch (err) {
        console.error('[maestro-handlers] Error reading unified state:', err);
        return {
          success: false,
          error: err instanceof Error ? err.message : 'Failed to read unified state',
        };
      }
    }
  );

  /**
   * Start watching unified state file for changes
   */
  ipcMain.handle(
    IPC_CHANNELS.MAESTRO_STATE_WATCH,
    async (_, projectId: string): Promise<IPCResult<void>> => {
      const project = projectStore.getProject(projectId);
      if (!project) {
        return { success: false, error: 'Project not found' };
      }

      // Stop any existing watcher for this project
      const existingCleanup = activeWatcherCleanups.get(projectId);
      if (existingCleanup) {
        existingCleanup();
        activeWatcherCleanups.delete(projectId);
      }

      try {
        const mainWindow = getMainWindow();
        if (!mainWindow) {
          return { success: false, error: 'No main window available' };
        }

        // Start watching and send updates to renderer
        const cleanup = watchUnifiedState(project.path, (state) => {
          sendStateToRenderer(mainWindow, projectId, state);
        });

        activeWatcherCleanups.set(projectId, cleanup);

        // Send initial state immediately
        const initialState = await readUnifiedState(project.path);
        if (initialState) {
          sendStateToRenderer(mainWindow, projectId, initialState);
        }

        console.log(`[maestro-handlers] Started watching unified state for project ${projectId}`);
        return { success: true, data: undefined };
      } catch (err) {
        console.error('[maestro-handlers] Error starting unified state watch:', err);
        return {
          success: false,
          error: err instanceof Error ? err.message : 'Failed to start watching',
        };
      }
    }
  );

  /**
   * Stop watching unified state file
   */
  ipcMain.handle(
    IPC_CHANNELS.MAESTRO_STATE_UNWATCH,
    async (_, projectId: string): Promise<IPCResult<void>> => {
      const project = projectStore.getProject(projectId);
      if (!project) {
        return { success: false, error: 'Project not found' };
      }

      const cleanup = activeWatcherCleanups.get(projectId);
      if (cleanup) {
        cleanup();
        activeWatcherCleanups.delete(projectId);
        stopWatching(project.path);
        console.log(`[maestro-handlers] Stopped watching unified state for project ${projectId}`);
      }

      return { success: true, data: undefined };
    }
  );

  /**
   * Open a terminal for Maestro sprint work
   * Creates or reuses a terminal in the project directory with Claude invoked
   *
   * Options:
   * - sprintFile: Path to the sprint file (for reference)
   * - invokeClaude: Whether to invoke Claude Code (default: true)
   * - autoStartSprint: Sprint number to auto-start (sends /sprint-start N after Claude loads)
   */
  ipcMain.handle(
    IPC_CHANNELS.MAESTRO_OPEN_TERMINAL,
    async (
      _,
      projectId: string,
      options?: { sprintFile?: string; invokeClaude?: boolean; autoStartSprint?: number }
    ): Promise<IPCResult<{ terminalId: string }>> => {
      const project = projectStore.getProject(projectId);
      if (!project) {
        return { success: false, error: 'Project not found' };
      }

      try {
        // Generate a unique terminal ID for Maestro work
        const terminalId = `maestro-${projectId}-${Date.now()}`;

        // Create a new terminal in the project directory
        const createResult = await terminalManager.create({
          id: terminalId,
          cwd: project.path,
          projectPath: project.path,
        });

        if (!createResult.success) {
          return { success: false, error: createResult.error || 'Failed to create terminal' };
        }

        // If requested, invoke Claude in the terminal
        if (options?.invokeClaude !== false) {
          // Read settings to check for YOLO mode
          const settings = await readSettingsFileAsync();
          const dangerouslySkipPermissions = settings?.dangerouslySkipPermissions === true;

          // Small delay to let the terminal initialize before invoking Claude
          setTimeout(async () => {
            await terminalManager.invokeClaudeAsync(
              terminalId,
              project.path,
              undefined,
              dangerouslySkipPermissions
            );

            // If autoStartSprint is specified, send the /sprint-start command after Claude loads
            if (options?.autoStartSprint !== undefined) {
              // Wait for Claude to fully initialize (Claude Code takes a moment to start)
              setTimeout(() => {
                const sprintCommand = `/sprint-start ${options.autoStartSprint}\n`;
                console.log(`[maestro-handlers] Auto-starting sprint ${options.autoStartSprint} in terminal ${terminalId}`);
                terminalManager.write(terminalId, sprintCommand);
              }, 3000); // 3 second delay for Claude to initialize
            }
          }, 500);
        }

        console.log(`[maestro-handlers] Opened terminal for Maestro work: ${terminalId}${options?.autoStartSprint ? ` (auto-start sprint ${options.autoStartSprint})` : ''}`);
        return { success: true, data: { terminalId } };
      } catch (err) {
        console.error('[maestro-handlers] Error opening terminal for Maestro:', err);
        return {
          success: false,
          error: err instanceof Error ? err.message : 'Failed to open terminal',
        };
      }
    }
  );

  /**
   * Check quality gates for a Maestro task before completion
   * Returns pass/fail status with details about which checks passed/failed
   */
  ipcMain.handle(
    IPC_CHANNELS.MAESTRO_CHECK_QUALITY_GATES,
    async (
      _,
      projectId: string,
      taskId: string
    ): Promise<IPCResult<MaestroQualityGateResult>> => {
      const project = projectStore.getProject(projectId);
      if (!project) {
        return { success: false, error: 'Project not found' };
      }

      try {
        // Get task from unified state
        const state = await readUnifiedState(project.path);
        if (!state) {
          return { success: false, error: 'Unified state not found' };
        }

        const task = state.tasks.find(t => t.id === taskId);
        if (!task) {
          return { success: false, error: 'Task not found in unified state' };
        }

        // Get sprint type and coverage threshold
        const sprintType = task.sprintType || 'basic';
        const coverageThresholds: Record<string, number> = {
          'basic': 60,
          'fullstack': 75,
          'infrastructure': 70,
          'documentation': 50,
          'refactoring': 80,
        };
        const coverageThreshold = coverageThresholds[sprintType] || 60;

        // Run quality gate checks
        const checks: MaestroQualityGateResult['checks'] = [];

        // Check 1: All phases completed
        const completedSteps = task.completedSteps || [];
        const phase6Steps = ['6.1', '6.2', '6.3', '6.4'];
        const allPhasesComplete = phase6Steps.every(step => completedSteps.includes(step));
        checks.push({
          name: 'All phases completed',
          passed: allPhasesComplete,
          message: allPhasesComplete ? 'All completion steps verified' : 'Missing completion steps: ' + phase6Steps.filter(s => !completedSteps.includes(s)).join(', ')
        });

        // Check 2: Sprint file exists
        const sprintFileExists = task.sprintFile ? existsSync(path.join(project.path, task.sprintFile)) : false;
        checks.push({
          name: 'Sprint file exists',
          passed: sprintFileExists,
          message: sprintFileExists ? `Sprint file: ${task.sprintFile}` : 'Sprint file not found'
        });

        // Check 3: Task status is appropriate for completion
        const statusOk = task.status === 'in_progress' || task.status === 'completed';
        checks.push({
          name: 'Task status valid',
          passed: statusOk,
          message: statusOk ? `Status: ${task.status}` : `Invalid status for completion: ${task.status}`
        });

        // Determine overall pass/fail
        // For now, we require all completion steps to be done
        // In the future, this could call the Python maestro_adapter for full validation
        const passed = checks.every(c => c.passed);

        const result: MaestroQualityGateResult = {
          passed,
          sprintType,
          coverageThreshold,
          checks,
          failureReason: passed ? undefined : 'One or more quality checks failed'
        };

        console.log(`[maestro-handlers] Quality gate check for ${taskId}: ${passed ? 'PASSED' : 'FAILED'}`);
        return { success: true, data: result };
      } catch (err) {
        console.error('[maestro-handlers] Error checking quality gates:', err);
        return {
          success: false,
          error: err instanceof Error ? err.message : 'Failed to check quality gates',
        };
      }
    }
  );

  console.log('[maestro-handlers] Maestro IPC handlers registered');
}

/**
 * Cleanup all active watchers (called on app shutdown)
 */
export function cleanupMaestroWatchers(): void {
  for (const [projectId, cleanup] of activeWatcherCleanups) {
    cleanup();
    console.log(`[maestro-handlers] Cleaned up watcher for project ${projectId}`);
  }
  activeWatcherCleanups.clear();
}

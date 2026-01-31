/**
 * Maestro IPC Handlers
 *
 * Handles Maestro unified state operations for the pipeline integration.
 * Watches the unified state file ({project}/.claude/task-state.json) and
 * sends updates to the renderer for real-time Kanban board updates.
 */

import { ipcMain, BrowserWindow } from 'electron';
import { IPC_CHANNELS } from '../../shared/constants';
import type { IPCResult } from '../../shared/types';
import { projectStore } from '../project-store';
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

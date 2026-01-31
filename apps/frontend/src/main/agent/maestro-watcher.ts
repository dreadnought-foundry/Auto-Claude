/**
 * Maestro State Watcher
 *
 * Watches the unified state file ({project}/.claude/task-state.json) for changes
 * and emits events when Maestro task state is updated. This enables the Kanban
 * board to reflect Maestro workflow progress in real-time.
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import { BrowserWindow } from 'electron';
import { IPC_CHANNELS } from '../../shared/constants/ipc';
import type { UnifiedTaskState, UnifiedTask } from '../../shared/types/task';

// Re-export types for convenience
export type { UnifiedTaskState, UnifiedTask };

/**
 * Active watchers by project path
 */
const activeWatchers = new Map<string, fs.FSWatcher>();

/**
 * Debounce timers by project path
 */
const debounceTimers = new Map<string, NodeJS.Timeout>();

/**
 * Debounce delay in milliseconds
 */
const DEBOUNCE_DELAY = 500;

/**
 * Read and parse the unified state file
 */
export async function readUnifiedState(projectPath: string): Promise<UnifiedTaskState | null> {
  const statePath = path.join(projectPath, '.claude', 'task-state.json');

  try {
    if (!fs.existsSync(statePath)) {
      return null;
    }

    const content = await fs.promises.readFile(statePath, 'utf-8');
    return JSON.parse(content) as UnifiedTaskState;
  } catch (error) {
    console.error('[MaestroWatcher] Failed to read unified state:', error);
    return null;
  }
}

/**
 * Write the unified state file
 */
export async function writeUnifiedState(
  projectPath: string,
  state: UnifiedTaskState
): Promise<void> {
  const stateDir = path.join(projectPath, '.claude');
  const statePath = path.join(stateDir, 'task-state.json');

  // Ensure directory exists
  if (!fs.existsSync(stateDir)) {
    fs.mkdirSync(stateDir, { recursive: true });
  }

  // Update lastUpdated timestamp
  state.lastUpdated = new Date().toISOString();

  await fs.promises.writeFile(statePath, JSON.stringify(state, null, 2), 'utf-8');
  console.log(`[MaestroWatcher] Wrote unified state with ${state.tasks.length} tasks`);
}

/**
 * Add a task to the unified state
 * Creates the state file if it doesn't exist
 */
export async function addTaskToUnifiedState(
  projectPath: string,
  task: UnifiedTask
): Promise<void> {
  let state = await readUnifiedState(projectPath);

  if (!state) {
    // Initialize new state file
    state = {
      version: '1.0',
      projectRoot: projectPath,
      tasks: [],
      lastUpdated: new Date().toISOString(),
    };
  }

  // Check if task already exists
  const existingIndex = state.tasks.findIndex(t => t.id === task.id);
  if (existingIndex >= 0) {
    // Update existing task
    state.tasks[existingIndex] = task;
  } else {
    // Add new task
    state.tasks.push(task);
  }

  await writeUnifiedState(projectPath, state);
}

/**
 * Get Maestro tasks from unified state
 */
export function getMaestroTasks(state: UnifiedTaskState): UnifiedTask[] {
  return state.tasks.filter(task => task.pipeline === 'maestro');
}

/**
 * Start watching unified state for a project
 *
 * @param projectPath - Path to the project root
 * @param onStateChange - Callback when state changes
 * @returns Cleanup function to stop watching
 */
export function watchUnifiedState(
  projectPath: string,
  onStateChange: (state: UnifiedTaskState) => void
): () => void {
  const statePath = path.join(projectPath, '.claude', 'task-state.json');
  const stateDir = path.dirname(statePath);

  // Ensure directory exists
  if (!fs.existsSync(stateDir)) {
    fs.mkdirSync(stateDir, { recursive: true });
  }

  // Stop any existing watcher for this project
  stopWatching(projectPath);

  console.log(`[MaestroWatcher] Starting watch on ${statePath}`);

  try {
    const watcher = fs.watch(stateDir, { persistent: true }, (_eventType, filename) => {
      // Only react to changes to task-state.json
      if (filename !== 'task-state.json') {
        return;
      }

      // Debounce to avoid multiple rapid events
      const existingTimer = debounceTimers.get(projectPath);
      if (existingTimer) {
        clearTimeout(existingTimer);
      }

      const timer = setTimeout(async () => {
        debounceTimers.delete(projectPath);

        const state = await readUnifiedState(projectPath);
        if (state) {
          console.log(`[MaestroWatcher] State changed, ${state.tasks.length} tasks`);
          onStateChange(state);
        }
      }, DEBOUNCE_DELAY);

      debounceTimers.set(projectPath, timer);
    });

    activeWatchers.set(projectPath, watcher);

    // Return cleanup function
    return () => stopWatching(projectPath);
  } catch (error) {
    console.error('[MaestroWatcher] Failed to start watcher:', error);
    return () => { /* no-op */ };
  }
}

/**
 * Stop watching unified state for a project
 */
export function stopWatching(projectPath: string): void {
  const watcher = activeWatchers.get(projectPath);
  if (watcher) {
    watcher.close();
    activeWatchers.delete(projectPath);
    console.log(`[MaestroWatcher] Stopped watching ${projectPath}`);
  }

  const timer = debounceTimers.get(projectPath);
  if (timer) {
    clearTimeout(timer);
    debounceTimers.delete(projectPath);
  }
}

/**
 * Stop all active watchers
 */
export function stopAllWatchers(): void {
  for (const projectPath of activeWatchers.keys()) {
    stopWatching(projectPath);
  }
}

/**
 * Send unified state update to renderer
 */
export function sendStateToRenderer(
  window: BrowserWindow | null,
  projectId: string,
  state: UnifiedTaskState
): void {
  if (!window || window.isDestroyed()) {
    return;
  }

  try {
    window.webContents.send(IPC_CHANNELS.MAESTRO_STATE_UPDATE, {
      projectId,
      state
    });
  } catch (error) {
    console.error('[MaestroWatcher] Failed to send state to renderer:', error);
  }
}

/**
 * Initialize watcher for a project and send updates to renderer
 */
export function initMaestroWatcher(
  window: BrowserWindow,
  projectId: string,
  projectPath: string
): () => void {
  return watchUnifiedState(projectPath, (state) => {
    sendStateToRenderer(window, projectId, state);
  });
}

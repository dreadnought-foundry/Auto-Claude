/**
 * Maestro State Hook
 *
 * Manages watching and consuming unified state updates from Maestro pipeline.
 * Used to display Maestro task progress on the Kanban board.
 */

import { useEffect, useState, useCallback } from 'react';
import type { UnifiedTaskState, UnifiedTask } from '@shared/types/task';

interface UseMaestroStateOptions {
  /** Project ID to watch */
  projectId: string | null;
  /** Whether to auto-start watching (default: true) */
  autoWatch?: boolean;
}

interface UseMaestroStateResult {
  /** Current unified state (null if not loaded) */
  state: UnifiedTaskState | null;
  /** Maestro tasks from the unified state */
  maestroTasks: UnifiedTask[];
  /** Whether we're currently watching for updates */
  isWatching: boolean;
  /** Any error that occurred */
  error: string | null;
  /** Manually start watching */
  startWatching: () => Promise<void>;
  /** Manually stop watching */
  stopWatching: () => Promise<void>;
  /** Manually refresh state */
  refresh: () => Promise<void>;
}

/**
 * Hook to watch and consume Maestro unified state
 */
export function useMaestroState({
  projectId,
  autoWatch = true,
}: UseMaestroStateOptions): UseMaestroStateResult {
  const [state, setState] = useState<UnifiedTaskState | null>(null);
  const [isWatching, setIsWatching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Get Maestro tasks from unified state
  const maestroTasks = state?.tasks.filter((t) => t.pipeline === 'maestro') ?? [];

  // Refresh state manually
  const refresh = useCallback(async () => {
    if (!projectId) return;

    try {
      const result = await window.electronAPI.getMaestroState(projectId);
      if (result.success) {
        setState(result.data ?? null);
        setError(null);
      } else {
        setError(result.error ?? 'Failed to get Maestro state');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  }, [projectId]);

  // Start watching for state updates
  const startWatching = useCallback(async () => {
    if (!projectId || isWatching) return;

    try {
      const result = await window.electronAPI.watchMaestroState(projectId);
      if (result.success) {
        setIsWatching(true);
        setError(null);
      } else {
        setError(result.error ?? 'Failed to start watching');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  }, [projectId, isWatching]);

  // Stop watching for state updates
  const stopWatching = useCallback(async () => {
    if (!projectId || !isWatching) return;

    try {
      await window.electronAPI.unwatchMaestroState(projectId);
      setIsWatching(false);
    } catch (err) {
      console.error('[useMaestroState] Error stopping watch:', err);
    }
  }, [projectId, isWatching]);

  // Set up state update listener
  useEffect(() => {
    if (!projectId) return;

    const cleanup = window.electronAPI.onMaestroStateUpdate((_, data) => {
      if (data.projectId === projectId) {
        setState(data.state);
      }
    });

    return () => {
      cleanup();
    };
  }, [projectId]);

  // Auto-start watching when project changes
  useEffect(() => {
    if (!projectId || !autoWatch) return;

    startWatching();

    // Cleanup: stop watching when project changes or component unmounts
    return () => {
      if (projectId) {
        window.electronAPI.unwatchMaestroState(projectId).catch(console.error);
      }
    };
  }, [projectId, autoWatch]); // Note: intentionally not including startWatching to avoid re-triggering

  return {
    state,
    maestroTasks,
    isWatching,
    error,
    startWatching,
    stopWatching,
    refresh,
  };
}

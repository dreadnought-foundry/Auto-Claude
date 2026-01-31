/**
 * Maestro API
 *
 * Exposes Maestro unified state operations to the renderer.
 * Used for pipeline integration with the Kanban board.
 */

import { ipcRenderer, type IpcRendererEvent } from 'electron';
import { IPC_CHANNELS } from '../../../shared/constants/ipc';
import type { IPCResult } from '../../../shared/types/common';
import type { UnifiedTaskState } from '../../../shared/types/task';

export interface MaestroAPI {
  /** Get current unified state for a project */
  getMaestroState: (projectId: string) => Promise<IPCResult<UnifiedTaskState | null>>;
  /** Start watching unified state file for changes */
  watchMaestroState: (projectId: string) => Promise<IPCResult<void>>;
  /** Stop watching unified state file */
  unwatchMaestroState: (projectId: string) => Promise<IPCResult<void>>;
  /** Listen for state updates */
  onMaestroStateUpdate: (
    callback: (event: IpcRendererEvent, data: { projectId: string; state: UnifiedTaskState }) => void
  ) => () => void;
}

export function createMaestroAPI(): MaestroAPI {
  return {
    getMaestroState: (projectId: string) =>
      ipcRenderer.invoke(IPC_CHANNELS.MAESTRO_STATE_GET, projectId),

    watchMaestroState: (projectId: string) =>
      ipcRenderer.invoke(IPC_CHANNELS.MAESTRO_STATE_WATCH, projectId),

    unwatchMaestroState: (projectId: string) =>
      ipcRenderer.invoke(IPC_CHANNELS.MAESTRO_STATE_UNWATCH, projectId),

    onMaestroStateUpdate: (callback) => {
      ipcRenderer.on(IPC_CHANNELS.MAESTRO_STATE_UPDATE, callback);
      return () => {
        ipcRenderer.removeListener(IPC_CHANNELS.MAESTRO_STATE_UPDATE, callback);
      };
    },
  };
}

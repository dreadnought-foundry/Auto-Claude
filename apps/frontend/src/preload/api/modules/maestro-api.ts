/**
 * Maestro API
 *
 * Exposes Maestro unified state operations to the renderer.
 * Used for pipeline integration with the Kanban board.
 */

import { ipcRenderer, type IpcRendererEvent } from 'electron';
import { IPC_CHANNELS } from '../../../shared/constants/ipc';
import type { IPCResult } from '../../../shared/types/common';
import type { UnifiedTaskState, MaestroQualityGateResult } from '../../../shared/types/task';

export interface OpenMaestroTerminalOptions {
  /** Sprint file path for context (optional) */
  sprintFile?: string;
  /** Whether to invoke Claude in the terminal (default: true) */
  invokeClaude?: boolean;
}

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
  /** Open a terminal for Maestro sprint work */
  openMaestroTerminal: (
    projectId: string,
    options?: OpenMaestroTerminalOptions
  ) => Promise<IPCResult<{ terminalId: string }>>;
  /** Check quality gates for a Maestro task before completion */
  checkMaestroQualityGates: (
    projectId: string,
    taskId: string
  ) => Promise<IPCResult<MaestroQualityGateResult>>;
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

    openMaestroTerminal: (projectId: string, options?: OpenMaestroTerminalOptions) =>
      ipcRenderer.invoke(IPC_CHANNELS.MAESTRO_OPEN_TERMINAL, projectId, options),

    checkMaestroQualityGates: (projectId: string, taskId: string) =>
      ipcRenderer.invoke(IPC_CHANNELS.MAESTRO_CHECK_QUALITY_GATES, projectId, taskId),
  };
}

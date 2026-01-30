/**
 * Epic IPC Handlers
 *
 * Handles epic management operations for Maestro-style work organization.
 * Epics are optional - projects work without them.
 */

import { ipcMain } from 'electron';
import { spawn } from 'child_process';
import path from 'path';
import { IPC_CHANNELS } from '../../shared/constants';
import type { IPCResult, EpicSummary } from '../../shared/types';
import { projectStore } from '../project-store';
import { getPythonExecutable } from '../python-executable';

/**
 * Run a Python CLI command and parse JSON output
 */
async function runPythonCommand(
  projectPath: string,
  args: string[]
): Promise<{ success: boolean; data?: unknown; error?: string }> {
  return new Promise((resolve) => {
    const pythonPath = getPythonExecutable();
    const cliPath = path.join(__dirname, '../../../../backend/cli/main.py');

    const proc = spawn(pythonPath, [cliPath, '--project-dir', projectPath, ...args], {
      cwd: projectPath,
      env: { ...process.env },
    });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('close', (code) => {
      if (code !== 0) {
        resolve({ success: false, error: stderr || `Process exited with code ${code}` });
        return;
      }

      // Try to parse JSON output
      try {
        // Look for JSON in stdout (CLI may print other text too)
        const jsonMatch = stdout.match(/\{[\s\S]*\}|\[[\s\S]*\]/);
        if (jsonMatch) {
          const data = JSON.parse(jsonMatch[0]);
          resolve({ success: true, data });
        } else {
          resolve({ success: true, data: stdout });
        }
      } catch {
        resolve({ success: true, data: stdout });
      }
    });

    proc.on('error', (err) => {
      resolve({ success: false, error: err.message });
    });
  });
}

/**
 * Parse epic list from registry.json directly (faster than CLI)
 */
async function getEpicsFromRegistry(projectPath: string): Promise<EpicSummary[]> {
  const fs = await import('fs/promises');
  const registryPath = path.join(projectPath, '.auto-claude', 'registry.json');

  try {
    const content = await fs.readFile(registryPath, 'utf-8');
    const registry = JSON.parse(content);

    const epics: EpicSummary[] = [];

    if (registry.epics) {
      for (const [numStr, epic] of Object.entries(registry.epics)) {
        const epicData = epic as {
          number: number;
          title: string;
          status: string;
          spec_count: number;
        };

        // Count completed specs for this epic from registry
        let specsCompleted = 0;
        if (registry.specs) {
          for (const spec of Object.values(registry.specs)) {
            const specData = spec as { epic_number?: number; status: string };
            if (specData.epic_number === epicData.number && specData.status === 'complete') {
              specsCompleted++;
            }
          }
        }

        epics.push({
          number: epicData.number,
          title: epicData.title,
          status: epicData.status as 'active' | 'completed' | 'archived',
          specsCompleted,
          specsTotal: epicData.spec_count || 0,
        });
      }
    }

    // Sort by number
    epics.sort((a, b) => a.number - b.number);

    return epics;
  } catch (err) {
    // Registry doesn't exist or is invalid - no epics
    console.debug('[epic-handlers] No registry found or error reading:', err);
    return [];
  }
}

/**
 * Register epic management IPC handlers
 */
export function registerEpicHandlers(): void {
  /**
   * List all epics for a project
   */
  ipcMain.handle(
    IPC_CHANNELS.EPIC_LIST,
    async (_, projectId: string): Promise<IPCResult<EpicSummary[]>> => {
      const project = projectStore.getProject(projectId);
      if (!project) {
        return { success: false, error: 'Project not found' };
      }

      try {
        const epics = await getEpicsFromRegistry(project.path);
        return { success: true, data: epics };
      } catch (err) {
        console.error('[epic-handlers] Error listing epics:', err);
        return {
          success: false,
          error: err instanceof Error ? err.message : 'Failed to list epics',
        };
      }
    }
  );

  /**
   * Create a new epic
   */
  ipcMain.handle(
    IPC_CHANNELS.EPIC_CREATE,
    async (
      _,
      projectId: string,
      title: string,
      description?: string
    ): Promise<IPCResult<{ epicNumber: number }>> => {
      const project = projectStore.getProject(projectId);
      if (!project) {
        return { success: false, error: 'Project not found' };
      }

      try {
        // Use CLI to create epic (handles registry updates)
        const result = await runPythonCommand(project.path, [
          '--epic-new',
          title,
        ]);

        if (!result.success) {
          return { success: false, error: result.error };
        }

        // Parse epic number from result
        // CLI outputs: "Created epic: 001-title"
        const output = String(result.data);
        const match = output.match(/(\d{3})-/);
        const epicNumber = match ? parseInt(match[1], 10) : 1;

        return { success: true, data: { epicNumber } };
      } catch (err) {
        console.error('[epic-handlers] Error creating epic:', err);
        return {
          success: false,
          error: err instanceof Error ? err.message : 'Failed to create epic',
        };
      }
    }
  );
}

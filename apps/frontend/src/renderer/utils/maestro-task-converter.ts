/**
 * Maestro Task Converter
 *
 * Converts UnifiedTask from Maestro unified state format to the Task format
 * used by the Kanban board. This enables Maestro workflow tasks to be
 * displayed alongside autonomous tasks.
 */

import type { Task, TaskStatus, UnifiedTask } from '@shared/types';
import { MAESTRO_PHASE_TO_COLUMN, } from '@shared/constants/task';

/**
 * Map Maestro unified status to Kanban TaskStatus
 */
function mapMaestroStatusToTaskStatus(
  unifiedStatus: UnifiedTask['status'],
  phase?: string
): TaskStatus {
  // First, check if phase provides a more specific mapping
  if (phase && MAESTRO_PHASE_TO_COLUMN[phase]) {
    return MAESTRO_PHASE_TO_COLUMN[phase] as TaskStatus;
  }

  // Fallback to status-based mapping
  switch (unifiedStatus) {
    case 'pending':
      return 'backlog';
    case 'in_progress':
      return 'in_progress';
    case 'blocked':
      return 'human_review';
    case 'completed':
      return 'done';
    case 'failed':
      return 'error';
    default:
      return 'backlog';
  }
}

/**
 * Convert a Maestro UnifiedTask to the Kanban Task format
 */
export function convertUnifiedTaskToTask(
  unifiedTask: UnifiedTask,
  projectId: string
): Task {
  const taskStatus = mapMaestroStatusToTaskStatus(unifiedTask.status, unifiedTask.phase);

  return {
    id: unifiedTask.id,
    specId: `maestro-${unifiedTask.id}`, // Prefix to distinguish from autonomous specs
    projectId,
    title: unifiedTask.title,
    description: unifiedTask.sprintFile || '', // Use sprint file as description source
    status: taskStatus,
    subtasks: (unifiedTask.subtasks || []).map((st, idx) => ({
      id: st.id,
      title: `Subtask ${idx + 1}`,
      description: '',
      status: st.status as 'pending' | 'in_progress' | 'completed' | 'failed',
      files: [],
    })),
    logs: [],
    metadata: {
      pipelineType: 'maestro',
      maestroPhase: unifiedTask.phase,
      maestroStep: unifiedTask.step,
      maestroCompletedSteps: unifiedTask.completedSteps,
      sprintFile: unifiedTask.sprintFile,
      sprintType: unifiedTask.sprintType,
      epicNumber: unifiedTask.epicNumber,
    },
    createdAt: new Date(unifiedTask.created),
    updatedAt: new Date(unifiedTask.started || unifiedTask.created),
  };
}

/**
 * Convert multiple Maestro unified tasks to Task format
 */
export function convertUnifiedTasksToTasks(
  unifiedTasks: UnifiedTask[],
  projectId: string
): Task[] {
  return unifiedTasks
    .filter((ut) => ut.pipeline === 'maestro')
    .map((ut) => convertUnifiedTaskToTask(ut, projectId));
}

/**
 * Merge Maestro tasks with autonomous tasks, avoiding duplicates
 * Maestro tasks are identified by their id, autonomous tasks by specId
 */
export function mergeTasks(
  autonomousTasks: Task[],
  maestroTasks: Task[]
): Task[] {
  // Create a Set of autonomous task IDs to check for duplicates
  const autonomousIds = new Set(autonomousTasks.map((t) => t.id));

  // Filter out any Maestro tasks that somehow duplicate autonomous ones
  const uniqueMaestroTasks = maestroTasks.filter((mt) => !autonomousIds.has(mt.id));

  // Return merged array with Maestro tasks first (they're typically active sprints)
  return [...uniqueMaestroTasks, ...autonomousTasks];
}

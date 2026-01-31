/**
 * Tests for Maestro Task Converter
 *
 * Tests the conversion of UnifiedTask format to Task format
 * and the phase-to-column mapping for Kanban board integration.
 */

import { describe, it, expect } from 'vitest';
import {
  convertUnifiedTaskToTask,
  convertUnifiedTasksToTasks,
  mergeTasks,
} from '../maestro-task-converter';
import type { Task, UnifiedTask } from '@shared/types';

describe('maestro-task-converter', () => {
  describe('convertUnifiedTaskToTask', () => {
    it('converts a basic Maestro task to Task format', () => {
      const unifiedTask: UnifiedTask = {
        id: 'task-001',
        title: 'Implement feature X',
        pipeline: 'maestro',
        status: 'pending',
        phase: '1',
        step: '1.1',
        completedSteps: [],
        sprintFile: 'docs/sprints/sprint-01_feature-x.md',
        created: '2024-01-15T10:00:00Z',
      };

      const result = convertUnifiedTaskToTask(unifiedTask, 'project-123');

      expect(result.id).toBe('task-001');
      expect(result.title).toBe('Implement feature X');
      expect(result.projectId).toBe('project-123');
      expect(result.specId).toBe('maestro-task-001');
      expect(result.metadata?.pipelineType).toBe('maestro');
      expect(result.metadata?.maestroPhase).toBe('1');
      expect(result.metadata?.maestroStep).toBe('1.1');
      expect(result.metadata?.sprintFile).toBe('docs/sprints/sprint-01_feature-x.md');
    });

    it('maps phase 1 to backlog column', () => {
      const unifiedTask: UnifiedTask = {
        id: 'task-001',
        title: 'Planning task',
        pipeline: 'maestro',
        status: 'in_progress',
        phase: '1',
        created: '2024-01-15T10:00:00Z',
      };

      const result = convertUnifiedTaskToTask(unifiedTask, 'project-123');
      expect(result.status).toBe('backlog');
    });

    it('maps phase 2 to in_progress column', () => {
      const unifiedTask: UnifiedTask = {
        id: 'task-001',
        title: 'Implementation task',
        pipeline: 'maestro',
        status: 'in_progress',
        phase: '2',
        created: '2024-01-15T10:00:00Z',
      };

      const result = convertUnifiedTaskToTask(unifiedTask, 'project-123');
      expect(result.status).toBe('in_progress');
    });

    it('maps phase 3 to in_progress column', () => {
      const unifiedTask: UnifiedTask = {
        id: 'task-001',
        title: 'Validation task',
        pipeline: 'maestro',
        status: 'in_progress',
        phase: '3',
        created: '2024-01-15T10:00:00Z',
      };

      const result = convertUnifiedTaskToTask(unifiedTask, 'project-123');
      expect(result.status).toBe('in_progress');
    });

    it('maps phase 4 to ai_review column', () => {
      const unifiedTask: UnifiedTask = {
        id: 'task-001',
        title: 'Documentation task',
        pipeline: 'maestro',
        status: 'in_progress',
        phase: '4',
        created: '2024-01-15T10:00:00Z',
      };

      const result = convertUnifiedTaskToTask(unifiedTask, 'project-123');
      expect(result.status).toBe('ai_review');
    });

    it('maps phase 5 to ai_review column', () => {
      const unifiedTask: UnifiedTask = {
        id: 'task-001',
        title: 'Commit task',
        pipeline: 'maestro',
        status: 'in_progress',
        phase: '5',
        created: '2024-01-15T10:00:00Z',
      };

      const result = convertUnifiedTaskToTask(unifiedTask, 'project-123');
      expect(result.status).toBe('ai_review');
    });

    it('maps phase 6 to human_review column', () => {
      const unifiedTask: UnifiedTask = {
        id: 'task-001',
        title: 'Completion task',
        pipeline: 'maestro',
        status: 'in_progress',
        phase: '6',
        created: '2024-01-15T10:00:00Z',
      };

      const result = convertUnifiedTaskToTask(unifiedTask, 'project-123');
      expect(result.status).toBe('human_review');
    });

    it('maps completed status to done when no phase specified', () => {
      const unifiedTask: UnifiedTask = {
        id: 'task-001',
        title: 'Completed task',
        pipeline: 'maestro',
        status: 'completed',
        created: '2024-01-15T10:00:00Z',
      };

      const result = convertUnifiedTaskToTask(unifiedTask, 'project-123');
      expect(result.status).toBe('done');
    });

    it('maps blocked status to human_review', () => {
      const unifiedTask: UnifiedTask = {
        id: 'task-001',
        title: 'Blocked task',
        pipeline: 'maestro',
        status: 'blocked',
        created: '2024-01-15T10:00:00Z',
      };

      const result = convertUnifiedTaskToTask(unifiedTask, 'project-123');
      expect(result.status).toBe('human_review');
    });

    it('maps failed status to error', () => {
      const unifiedTask: UnifiedTask = {
        id: 'task-001',
        title: 'Failed task',
        pipeline: 'maestro',
        status: 'failed',
        error: 'Something went wrong',
        created: '2024-01-15T10:00:00Z',
      };

      const result = convertUnifiedTaskToTask(unifiedTask, 'project-123');
      expect(result.status).toBe('error');
    });

    it('converts subtasks correctly', () => {
      const unifiedTask: UnifiedTask = {
        id: 'task-001',
        title: 'Task with subtasks',
        pipeline: 'maestro',
        status: 'in_progress',
        phase: '2',
        subtasks: [
          { id: 'sub-1', status: 'completed' },
          { id: 'sub-2', status: 'in_progress' },
          { id: 'sub-3', status: 'pending' },
        ],
        created: '2024-01-15T10:00:00Z',
      };

      const result = convertUnifiedTaskToTask(unifiedTask, 'project-123');
      expect(result.subtasks).toHaveLength(3);
      expect(result.subtasks[0].status).toBe('completed');
      expect(result.subtasks[1].status).toBe('in_progress');
      expect(result.subtasks[2].status).toBe('pending');
    });

    it('includes epic number and sprint type in metadata', () => {
      const unifiedTask: UnifiedTask = {
        id: 'task-001',
        title: 'Epic task',
        pipeline: 'maestro',
        status: 'pending',
        epicNumber: 2,
        sprintType: 'fullstack',
        created: '2024-01-15T10:00:00Z',
      };

      const result = convertUnifiedTaskToTask(unifiedTask, 'project-123');
      expect(result.metadata?.epicNumber).toBe(2);
      expect(result.metadata?.sprintType).toBe('fullstack');
    });
  });

  describe('convertUnifiedTasksToTasks', () => {
    it('converts multiple Maestro tasks', () => {
      const unifiedTasks: UnifiedTask[] = [
        {
          id: 'task-001',
          title: 'Task 1',
          pipeline: 'maestro',
          status: 'pending',
          created: '2024-01-15T10:00:00Z',
        },
        {
          id: 'task-002',
          title: 'Task 2',
          pipeline: 'maestro',
          status: 'in_progress',
          phase: '2',
          created: '2024-01-15T11:00:00Z',
        },
      ];

      const result = convertUnifiedTasksToTasks(unifiedTasks, 'project-123');
      expect(result).toHaveLength(2);
      expect(result[0].id).toBe('task-001');
      expect(result[1].id).toBe('task-002');
    });

    it('filters out non-Maestro tasks', () => {
      const unifiedTasks: UnifiedTask[] = [
        {
          id: 'task-001',
          title: 'Maestro Task',
          pipeline: 'maestro',
          status: 'pending',
          created: '2024-01-15T10:00:00Z',
        },
        {
          id: 'task-002',
          title: 'Autonomous Task',
          pipeline: 'autonomous',
          status: 'pending',
          created: '2024-01-15T11:00:00Z',
        },
      ];

      const result = convertUnifiedTasksToTasks(unifiedTasks, 'project-123');
      expect(result).toHaveLength(1);
      expect(result[0].id).toBe('task-001');
    });

    it('returns empty array for empty input', () => {
      const result = convertUnifiedTasksToTasks([], 'project-123');
      expect(result).toHaveLength(0);
    });
  });

  describe('mergeTasks', () => {
    it('merges Maestro and autonomous tasks', () => {
      const autonomousTasks: Task[] = [
        {
          id: 'auto-001',
          specId: '001-feature',
          projectId: 'project-123',
          title: 'Autonomous Task',
          description: 'Test',
          status: 'backlog',
          subtasks: [],
          logs: [],
          createdAt: new Date(),
          updatedAt: new Date(),
        },
      ];

      const maestroTasks: Task[] = [
        {
          id: 'maestro-001',
          specId: 'maestro-maestro-001',
          projectId: 'project-123',
          title: 'Maestro Task',
          description: '',
          status: 'in_progress',
          subtasks: [],
          logs: [],
          metadata: { pipelineType: 'maestro' },
          createdAt: new Date(),
          updatedAt: new Date(),
        },
      ];

      const result = mergeTasks(autonomousTasks, maestroTasks);
      expect(result).toHaveLength(2);
      // Maestro tasks should come first
      expect(result[0].id).toBe('maestro-001');
      expect(result[1].id).toBe('auto-001');
    });

    it('filters out duplicate tasks by ID', () => {
      const autonomousTasks: Task[] = [
        {
          id: 'task-001',
          specId: '001-feature',
          projectId: 'project-123',
          title: 'Original Task',
          description: 'Test',
          status: 'backlog',
          subtasks: [],
          logs: [],
          createdAt: new Date(),
          updatedAt: new Date(),
        },
      ];

      const maestroTasks: Task[] = [
        {
          id: 'task-001', // Same ID as autonomous task
          specId: 'maestro-task-001',
          projectId: 'project-123',
          title: 'Duplicate Task',
          description: '',
          status: 'in_progress',
          subtasks: [],
          logs: [],
          metadata: { pipelineType: 'maestro' },
          createdAt: new Date(),
          updatedAt: new Date(),
        },
      ];

      const result = mergeTasks(autonomousTasks, maestroTasks);
      expect(result).toHaveLength(1);
      // Autonomous task takes precedence (Maestro duplicate filtered out)
      expect(result[0].title).toBe('Original Task');
    });

    it('handles empty arrays', () => {
      expect(mergeTasks([], [])).toHaveLength(0);

      const tasks: Task[] = [{
        id: 'task-001',
        specId: '001-test',
        projectId: 'project-123',
        title: 'Test',
        description: '',
        status: 'backlog',
        subtasks: [],
        logs: [],
        createdAt: new Date(),
        updatedAt: new Date(),
      }];

      expect(mergeTasks(tasks, [])).toHaveLength(1);
      expect(mergeTasks([], tasks)).toHaveLength(1);
    });
  });
});

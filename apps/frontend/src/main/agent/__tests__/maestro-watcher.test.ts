/**
 * Tests for Maestro State Watcher
 *
 * Tests the unified state file read/write operations
 * and task management for Maestro pipeline integration.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { tmpdir } from 'node:os';
import {
  readUnifiedState,
  writeUnifiedState,
  addTaskToUnifiedState,
  getMaestroTasks,
} from '../maestro-watcher';
import type { UnifiedTaskState, UnifiedTask } from '../../../shared/types/task';

// Create a unique temp directory for each test run
const testDir = path.join(tmpdir(), `maestro-test-${Date.now()}`);
const claudeDir = path.join(testDir, '.claude');
const stateFilePath = path.join(claudeDir, 'task-state.json');

describe('maestro-watcher', () => {
  beforeEach(() => {
    // Create test directories
    fs.mkdirSync(claudeDir, { recursive: true });
  });

  afterEach(() => {
    // Clean up test directory
    if (fs.existsSync(testDir)) {
      fs.rmSync(testDir, { recursive: true, force: true });
    }
  });

  describe('readUnifiedState', () => {
    it('returns null when state file does not exist', async () => {
      const result = await readUnifiedState(testDir);
      expect(result).toBeNull();
    });

    it('reads and parses valid state file', async () => {
      const state: UnifiedTaskState = {
        version: '1.0',
        projectRoot: testDir,
        tasks: [
          {
            id: 'task-001',
            title: 'Test Task',
            pipeline: 'maestro',
            status: 'pending',
            created: '2024-01-15T10:00:00Z',
          },
        ],
        lastUpdated: '2024-01-15T10:00:00Z',
      };

      fs.writeFileSync(stateFilePath, JSON.stringify(state, null, 2));

      const result = await readUnifiedState(testDir);
      expect(result).not.toBeNull();
      expect(result?.version).toBe('1.0');
      expect(result?.tasks).toHaveLength(1);
      expect(result?.tasks[0].id).toBe('task-001');
    });

    it('returns null for invalid JSON', async () => {
      fs.writeFileSync(stateFilePath, 'invalid json {{{');

      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => { /* suppress error output */ });
      const result = await readUnifiedState(testDir);

      expect(result).toBeNull();
      expect(consoleSpy).toHaveBeenCalled();

      consoleSpy.mockRestore();
    });
  });

  describe('writeUnifiedState', () => {
    it('creates state file and directories if they do not exist', async () => {
      // Remove the claude directory
      fs.rmSync(claudeDir, { recursive: true, force: true });

      const state: UnifiedTaskState = {
        version: '1.0',
        projectRoot: testDir,
        tasks: [],
        lastUpdated: '2024-01-15T10:00:00Z',
      };

      await writeUnifiedState(testDir, state);

      expect(fs.existsSync(stateFilePath)).toBe(true);
      const written = JSON.parse(fs.readFileSync(stateFilePath, 'utf-8'));
      expect(written.version).toBe('1.0');
    });

    it('updates lastUpdated timestamp', async () => {
      const state: UnifiedTaskState = {
        version: '1.0',
        projectRoot: testDir,
        tasks: [],
        lastUpdated: '2024-01-01T00:00:00Z', // Old timestamp
      };

      await writeUnifiedState(testDir, state);

      const written = JSON.parse(fs.readFileSync(stateFilePath, 'utf-8'));
      // Should have a newer timestamp
      expect(new Date(written.lastUpdated).getTime()).toBeGreaterThan(
        new Date('2024-01-01T00:00:00Z').getTime()
      );
    });

    it('writes formatted JSON', async () => {
      const state: UnifiedTaskState = {
        version: '1.0',
        projectRoot: testDir,
        tasks: [
          {
            id: 'task-001',
            title: 'Test',
            pipeline: 'maestro',
            status: 'pending',
            created: '2024-01-15T10:00:00Z',
          },
        ],
        lastUpdated: '2024-01-15T10:00:00Z',
      };

      await writeUnifiedState(testDir, state);

      const content = fs.readFileSync(stateFilePath, 'utf-8');
      // Check for formatting (should contain newlines and indentation)
      expect(content).toContain('\n');
      expect(content).toContain('  ');
    });
  });

  describe('addTaskToUnifiedState', () => {
    it('creates new state file when none exists', async () => {
      const task: UnifiedTask = {
        id: 'task-001',
        title: 'New Task',
        pipeline: 'maestro',
        status: 'pending',
        created: '2024-01-15T10:00:00Z',
      };

      await addTaskToUnifiedState(testDir, task);

      const state = await readUnifiedState(testDir);
      expect(state).not.toBeNull();
      expect(state?.tasks).toHaveLength(1);
      expect(state?.tasks[0].id).toBe('task-001');
    });

    it('adds task to existing state', async () => {
      // Create initial state with one task
      const initialState: UnifiedTaskState = {
        version: '1.0',
        projectRoot: testDir,
        tasks: [
          {
            id: 'task-001',
            title: 'Existing Task',
            pipeline: 'maestro',
            status: 'completed',
            created: '2024-01-14T10:00:00Z',
          },
        ],
        lastUpdated: '2024-01-14T10:00:00Z',
      };
      fs.writeFileSync(stateFilePath, JSON.stringify(initialState, null, 2));

      // Add new task
      const newTask: UnifiedTask = {
        id: 'task-002',
        title: 'New Task',
        pipeline: 'maestro',
        status: 'pending',
        created: '2024-01-15T10:00:00Z',
      };

      await addTaskToUnifiedState(testDir, newTask);

      const state = await readUnifiedState(testDir);
      expect(state?.tasks).toHaveLength(2);
      expect(state?.tasks.map((t) => t.id)).toContain('task-001');
      expect(state?.tasks.map((t) => t.id)).toContain('task-002');
    });

    it('updates existing task by ID', async () => {
      // Create initial state
      const initialState: UnifiedTaskState = {
        version: '1.0',
        projectRoot: testDir,
        tasks: [
          {
            id: 'task-001',
            title: 'Original Title',
            pipeline: 'maestro',
            status: 'pending',
            phase: '1',
            created: '2024-01-15T10:00:00Z',
          },
        ],
        lastUpdated: '2024-01-15T10:00:00Z',
      };
      fs.writeFileSync(stateFilePath, JSON.stringify(initialState, null, 2));

      // Update task with same ID
      const updatedTask: UnifiedTask = {
        id: 'task-001',
        title: 'Updated Title',
        pipeline: 'maestro',
        status: 'in_progress',
        phase: '2',
        created: '2024-01-15T10:00:00Z',
        started: '2024-01-15T11:00:00Z',
      };

      await addTaskToUnifiedState(testDir, updatedTask);

      const state = await readUnifiedState(testDir);
      expect(state?.tasks).toHaveLength(1);
      expect(state?.tasks[0].title).toBe('Updated Title');
      expect(state?.tasks[0].status).toBe('in_progress');
      expect(state?.tasks[0].phase).toBe('2');
    });
  });

  describe('getMaestroTasks', () => {
    it('filters only Maestro pipeline tasks', () => {
      const state: UnifiedTaskState = {
        version: '1.0',
        projectRoot: '/test',
        tasks: [
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
            created: '2024-01-15T10:00:00Z',
          },
          {
            id: 'task-003',
            title: 'Another Maestro Task',
            pipeline: 'maestro',
            status: 'in_progress',
            created: '2024-01-15T10:00:00Z',
          },
        ],
        lastUpdated: '2024-01-15T10:00:00Z',
      };

      const maestroTasks = getMaestroTasks(state);
      expect(maestroTasks).toHaveLength(2);
      expect(maestroTasks.every((t) => t.pipeline === 'maestro')).toBe(true);
    });

    it('returns empty array when no Maestro tasks', () => {
      const state: UnifiedTaskState = {
        version: '1.0',
        projectRoot: '/test',
        tasks: [
          {
            id: 'task-001',
            title: 'Autonomous Task',
            pipeline: 'autonomous',
            status: 'pending',
            created: '2024-01-15T10:00:00Z',
          },
        ],
        lastUpdated: '2024-01-15T10:00:00Z',
      };

      const maestroTasks = getMaestroTasks(state);
      expect(maestroTasks).toHaveLength(0);
    });
  });
});

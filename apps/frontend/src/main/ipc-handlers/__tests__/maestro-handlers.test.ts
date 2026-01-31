/**
 * Tests for Maestro IPC Handlers
 *
 * Tests the quality gate checking logic and Maestro state operations.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { tmpdir } from 'node:os';
import type { UnifiedTaskState, MaestroQualityGateResult } from '../../../shared/types/task';

// Create a unique temp directory for each test run
const testDir = path.join(tmpdir(), `maestro-handlers-test-${Date.now()}`);
const claudeDir = path.join(testDir, '.claude');
const sprintsDir = path.join(testDir, 'docs', 'sprints');

/**
 * Simulates the quality gate check logic from maestro-handlers.ts
 * This is extracted for unit testing without IPC dependencies
 */
function checkQualityGates(
  task: UnifiedTaskState['tasks'][0],
  projectPath: string
): MaestroQualityGateResult {
  const sprintType = task.sprintType || 'basic';
  const coverageThresholds: Record<string, number> = {
    basic: 60,
    fullstack: 75,
    infrastructure: 70,
    documentation: 50,
    refactoring: 80,
  };
  const coverageThreshold = coverageThresholds[sprintType] || 60;

  const checks: MaestroQualityGateResult['checks'] = [];

  // Check 1: All phases completed
  const completedSteps = task.completedSteps || [];
  const phase6Steps = ['6.1', '6.2', '6.3', '6.4'];
  const allPhasesComplete = phase6Steps.every((step) => completedSteps.includes(step));
  checks.push({
    name: 'All phases completed',
    passed: allPhasesComplete,
    message: allPhasesComplete
      ? 'All completion steps verified'
      : 'Missing completion steps: ' + phase6Steps.filter((s) => !completedSteps.includes(s)).join(', '),
  });

  // Check 2: Sprint file exists
  const sprintFileExists = task.sprintFile
    ? fs.existsSync(path.join(projectPath, task.sprintFile))
    : false;
  checks.push({
    name: 'Sprint file exists',
    passed: sprintFileExists,
    message: sprintFileExists ? `Sprint file: ${task.sprintFile}` : 'Sprint file not found',
  });

  // Check 3: Task status is appropriate for completion
  const statusOk = task.status === 'in_progress' || task.status === 'completed';
  checks.push({
    name: 'Task status valid',
    passed: statusOk,
    message: statusOk ? `Status: ${task.status}` : `Invalid status for completion: ${task.status}`,
  });

  const passed = checks.every((c) => c.passed);

  return {
    passed,
    sprintType,
    coverageThreshold,
    checks,
    failureReason: passed ? undefined : 'One or more quality checks failed',
  };
}

describe('maestro-handlers quality gates', () => {
  beforeEach(() => {
    // Create test directories
    fs.mkdirSync(claudeDir, { recursive: true });
    fs.mkdirSync(sprintsDir, { recursive: true });
  });

  afterEach(() => {
    // Clean up test directory
    if (fs.existsSync(testDir)) {
      fs.rmSync(testDir, { recursive: true, force: true });
    }
  });

  describe('checkQualityGates', () => {
    it('passes when all checks are satisfied', () => {
      // Create sprint file
      const sprintFile = 'docs/sprints/sprint-01_test.md';
      fs.writeFileSync(path.join(testDir, sprintFile), '# Sprint 1');

      const task: UnifiedTaskState['tasks'][0] = {
        id: 'task-001',
        title: 'Completed Task',
        pipeline: 'maestro',
        status: 'in_progress',
        phase: '6',
        completedSteps: ['6.1', '6.2', '6.3', '6.4'],
        sprintFile,
        created: '2024-01-15T10:00:00Z',
      };

      const result = checkQualityGates(task, testDir);

      expect(result.passed).toBe(true);
      expect(result.failureReason).toBeUndefined();
      expect(result.checks.every((c) => c.passed)).toBe(true);
    });

    it('fails when completion steps are missing', () => {
      // Create sprint file
      const sprintFile = 'docs/sprints/sprint-01_test.md';
      fs.writeFileSync(path.join(testDir, sprintFile), '# Sprint 1');

      const task: UnifiedTaskState['tasks'][0] = {
        id: 'task-001',
        title: 'Incomplete Task',
        pipeline: 'maestro',
        status: 'in_progress',
        phase: '6',
        completedSteps: ['6.1', '6.2'], // Missing 6.3 and 6.4
        sprintFile,
        created: '2024-01-15T10:00:00Z',
      };

      const result = checkQualityGates(task, testDir);

      expect(result.passed).toBe(false);
      expect(result.failureReason).toBe('One or more quality checks failed');

      const phasesCheck = result.checks.find((c) => c.name === 'All phases completed');
      expect(phasesCheck?.passed).toBe(false);
      expect(phasesCheck?.message).toContain('6.3');
      expect(phasesCheck?.message).toContain('6.4');
    });

    it('fails when sprint file does not exist', () => {
      const task: UnifiedTaskState['tasks'][0] = {
        id: 'task-001',
        title: 'No Sprint File Task',
        pipeline: 'maestro',
        status: 'in_progress',
        phase: '6',
        completedSteps: ['6.1', '6.2', '6.3', '6.4'],
        sprintFile: 'docs/sprints/nonexistent.md',
        created: '2024-01-15T10:00:00Z',
      };

      const result = checkQualityGates(task, testDir);

      expect(result.passed).toBe(false);

      const sprintCheck = result.checks.find((c) => c.name === 'Sprint file exists');
      expect(sprintCheck?.passed).toBe(false);
      expect(sprintCheck?.message).toBe('Sprint file not found');
    });

    it('fails when task status is invalid for completion', () => {
      // Create sprint file
      const sprintFile = 'docs/sprints/sprint-01_test.md';
      fs.writeFileSync(path.join(testDir, sprintFile), '# Sprint 1');

      const task: UnifiedTaskState['tasks'][0] = {
        id: 'task-001',
        title: 'Pending Task',
        pipeline: 'maestro',
        status: 'pending', // Invalid status for completion
        phase: '6',
        completedSteps: ['6.1', '6.2', '6.3', '6.4'],
        sprintFile,
        created: '2024-01-15T10:00:00Z',
      };

      const result = checkQualityGates(task, testDir);

      expect(result.passed).toBe(false);

      const statusCheck = result.checks.find((c) => c.name === 'Task status valid');
      expect(statusCheck?.passed).toBe(false);
      expect(statusCheck?.message).toContain('pending');
    });

    it('uses correct coverage threshold for sprint type', () => {
      const sprintFile = 'docs/sprints/sprint-01_test.md';
      fs.writeFileSync(path.join(testDir, sprintFile), '# Sprint 1');

      const basicTask: UnifiedTaskState['tasks'][0] = {
        id: 'task-001',
        title: 'Basic Task',
        pipeline: 'maestro',
        status: 'in_progress',
        sprintType: 'basic',
        completedSteps: ['6.1', '6.2', '6.3', '6.4'],
        sprintFile,
        created: '2024-01-15T10:00:00Z',
      };

      const fullstackTask: UnifiedTaskState['tasks'][0] = {
        ...basicTask,
        id: 'task-002',
        sprintType: 'fullstack',
      };

      const refactoringTask: UnifiedTaskState['tasks'][0] = {
        ...basicTask,
        id: 'task-003',
        sprintType: 'refactoring',
      };

      expect(checkQualityGates(basicTask, testDir).coverageThreshold).toBe(60);
      expect(checkQualityGates(fullstackTask, testDir).coverageThreshold).toBe(75);
      expect(checkQualityGates(refactoringTask, testDir).coverageThreshold).toBe(80);
    });

    it('defaults to basic coverage threshold for unknown sprint type', () => {
      const sprintFile = 'docs/sprints/sprint-01_test.md';
      fs.writeFileSync(path.join(testDir, sprintFile), '# Sprint 1');

      const task: UnifiedTaskState['tasks'][0] = {
        id: 'task-001',
        title: 'Unknown Type Task',
        pipeline: 'maestro',
        status: 'in_progress',
        sprintType: 'custom-unknown-type',
        completedSteps: ['6.1', '6.2', '6.3', '6.4'],
        sprintFile,
        created: '2024-01-15T10:00:00Z',
      };

      const result = checkQualityGates(task, testDir);
      expect(result.coverageThreshold).toBe(60);
    });

    it('handles task with no completedSteps array', () => {
      const sprintFile = 'docs/sprints/sprint-01_test.md';
      fs.writeFileSync(path.join(testDir, sprintFile), '# Sprint 1');

      const task: UnifiedTaskState['tasks'][0] = {
        id: 'task-001',
        title: 'No Steps Task',
        pipeline: 'maestro',
        status: 'in_progress',
        // completedSteps is undefined
        sprintFile,
        created: '2024-01-15T10:00:00Z',
      };

      const result = checkQualityGates(task, testDir);

      expect(result.passed).toBe(false);
      const phasesCheck = result.checks.find((c) => c.name === 'All phases completed');
      expect(phasesCheck?.passed).toBe(false);
    });

    it('handles task with no sprintFile', () => {
      const task: UnifiedTaskState['tasks'][0] = {
        id: 'task-001',
        title: 'No Sprint File',
        pipeline: 'maestro',
        status: 'in_progress',
        completedSteps: ['6.1', '6.2', '6.3', '6.4'],
        // sprintFile is undefined
        created: '2024-01-15T10:00:00Z',
      };

      const result = checkQualityGates(task, testDir);

      expect(result.passed).toBe(false);
      const sprintCheck = result.checks.find((c) => c.name === 'Sprint file exists');
      expect(sprintCheck?.passed).toBe(false);
    });
  });
});

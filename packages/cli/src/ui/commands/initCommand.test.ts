/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { initCommand } from './initCommand.js';
import { createMockCommandContext } from '../../test-utils/mockCommandContext.js';
import type { CommandContext } from './types.js';
import type { SubmitPromptActionReturn } from '@open-agent/core';

// Mock the 'fs' module
vi.mock('fs', async (importOriginal) => {
  const actual = await importOriginal<typeof import('node:fs')>();
  return {
    ...actual,
    existsSync: vi.fn(),
    writeFileSync: vi.fn(),
  };
});

describe('initCommand', () => {
  let mockContext: CommandContext;
  const targetDir = '/test/dir';
  const contextFilePath = path.join(targetDir, 'OPENAGENT.md');

  beforeEach(() => {
    // Create a fresh mock context for each test
    mockContext = createMockCommandContext({
      services: {
        agentContext: {
          config: {
            getTargetDir: () => targetDir,
          },
        },
      },
    });
  });

  afterEach(() => {
    // Clear all mocks after each test
    vi.clearAllMocks();
  });

  it('should inform the user if OPENAGENT.md already exists', async () => {
    // Arrange: Simulate that the file exists
    vi.mocked(fs.existsSync).mockReturnValue(true);

    // Act: Run the command's action
    const result = await initCommand.action!(mockContext, '');

    // Assert: Check for the correct informational message
    expect(result).toEqual({
      type: 'message',
      messageType: 'info',
      content:
        'A OPENAGENT.md file already exists in this directory. No changes were made.',
    });
    // Assert: Ensure no file was written
    expect(fs.writeFileSync).not.toHaveBeenCalled();
  });

  it('should create OPENAGENT.md and submit a prompt if it does not exist', async () => {
    // Arrange: Simulate that the file does not exist
    vi.mocked(fs.existsSync).mockReturnValue(false);

    // Act: Run the command's action
    const result = (await initCommand.action!(
      mockContext,
      '',
    )) as SubmitPromptActionReturn;

    // Assert: Check that writeFileSync was called correctly
    expect(fs.writeFileSync).toHaveBeenCalledWith(contextFilePath, '', 'utf8');

    // Assert: Check that an informational message was added to the UI
    expect(mockContext.ui.addItem).toHaveBeenCalledWith(
      {
        type: 'info',
        text: 'Empty OPENAGENT.md created. Now analyzing the project to populate it.',
      },
      expect.any(Number),
    );

    // Assert: Check that the correct prompt is submitted
    expect(result.type).toBe('submit_prompt');
    expect(result.content).toContain(
      'You are an AI agent that brings the power of OpenAgent',
    );
  });

  it('should return an error if config is not available', async () => {
    // Arrange: Create a context without config
    const noConfigContext = createMockCommandContext();
    if (noConfigContext.services) {
      noConfigContext.services.agentContext = null;
    }

    // Act: Run the command's action
    const result = await initCommand.action!(noConfigContext, '');

    // Assert: Check for the correct error message
    expect(result).toEqual({
      type: 'message',
      messageType: 'error',
      content: 'Configuration not available.',
    });
  });
});

/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { vi, describe, it, expect, beforeEach } from 'vitest';
import { pickCommand } from './pickCommand.js';
import { type CommandContext } from './types.js';
import { MessageType } from '../types.js';
import { createMockCommandContext } from '../../test-utils/mockCommandContext.js';

const mocks = vi.hoisted(() => ({
  isOllamaRunning: vi.fn(),
  listOllamaModels: vi.fn(),
  isLMStudioRunning: vi.fn(),
  listLMStudioModels: vi.fn(),
  loadRegistry: vi.fn(),
}));

vi.mock('@google/gemini-cli-core', async () => {
  const actual = await vi.importActual('@google/gemini-cli-core');
  return {
    ...actual,
    isOllamaRunning: mocks.isOllamaRunning,
    listOllamaModels: mocks.listOllamaModels,
    isLMStudioRunning: mocks.isLMStudioRunning,
    listLMStudioModels: mocks.listLMStudioModels,
    ModelRegistry: Object.assign(
      (actual as Record<string, unknown>)['ModelRegistry'] as object,
      { load: mocks.loadRegistry },
    ),
  };
});

import { ModelRegistry } from '@google/gemini-cli-core';

function testRegistry(): ModelRegistry {
  return new ModelRegistry('test://models.toml', {
    default_model: 'gpt-4o',
    models: {
      'gpt-4o': { model: 'gpt-4o' },
      'groq-llama-3.1-8b': { model: 'groq/llama-3.1-8b-instant' },
    },
    free_catalog: [],
    default_priority: [],
  });
}

describe('pickCommand', () => {
  let mockContext: CommandContext;
  let mockSetModel: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
    mocks.loadRegistry.mockReturnValue(testRegistry());
    mocks.isOllamaRunning.mockResolvedValue(false);
    mocks.isLMStudioRunning.mockResolvedValue(false);
    mockSetModel = vi.fn();
    mockContext = createMockCommandContext({
      services: {
        agentContext: {
          config: { setModel: mockSetModel },
        },
      },
    } as never);
  });

  it('lists models grouped by provider when called without args', async () => {
    mocks.isOllamaRunning.mockResolvedValue(true);
    mocks.listOllamaModels.mockResolvedValue(['llama3.1:8b']);

    await pickCommand.action!(mockContext, '');

    expect(mockContext.ui.addItem).toHaveBeenCalledWith(
      expect.objectContaining({
        type: MessageType.INFO,
        text: expect.stringContaining('Ollama (local)'),
      }),
      expect.any(Number),
    );
    const text = (mockContext.ui.addItem as ReturnType<typeof vi.fn>).mock
      .calls[0][0].text as string;
    expect(text).toContain('✓ ollama/llama3.1:8b');
    expect(text).toContain('gpt-4o');
  });

  it('switches to the requested model with /pick <name>', async () => {
    await pickCommand.action!(mockContext, 'groq-llama-3.1-8b');
    expect(mockSetModel).toHaveBeenCalledWith(
      'groq/llama-3.1-8b-instant',
      true,
    );
    expect(mockContext.ui.addItem).toHaveBeenCalledWith(
      expect.objectContaining({
        type: MessageType.INFO,
        text: 'Model set to groq/llama-3.1-8b-instant',
      }),
      expect.any(Number),
    );
  });

  it('errors when no session config is available', async () => {
    const bareContext = createMockCommandContext();
    await pickCommand.action!(bareContext, 'gpt-4o');
    expect(bareContext.ui.addItem).toHaveBeenCalledWith(
      expect.objectContaining({ type: MessageType.ERROR }),
      expect.any(Number),
    );
  });
});

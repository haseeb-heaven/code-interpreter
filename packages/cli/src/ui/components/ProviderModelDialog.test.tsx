/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect, vi } from 'vitest';
import { act } from 'react';
import { ProviderModelDialog } from './ProviderModelDialog.js';
import { renderWithProviders } from '../../test-utils/render.js';
import { waitFor } from '../../test-utils/async.js';
import type { PickerGroup } from '@google/gemini-cli-core';

const GROUPS: PickerGroup[] = [
  {
    provider: {
      id: 'groq',
      displayName: 'Groq',
      envKey: 'GROQ_API_KEY',
      apiBase: 'https://api.groq.com/openai/v1',
      local: false,
      vision: false,
      streaming: true,
    },
    models: [
      {
        key: 'groq-llama',
        model: 'groq/llama-3.1-8b-instant',
        vision: false,
        streaming: true,
        available: true,
        tier: 'free',
      },
    ],
  },
  {
    provider: {
      id: 'openai',
      displayName: 'OpenAI',
      envKey: 'OPENAI_API_KEY',
      apiBase: 'https://api.openai.com/v1',
      local: false,
      vision: true,
      streaming: true,
    },
    models: [
      {
        key: 'gpt-4o',
        model: 'gpt-4o',
        vision: true,
        streaming: true,
        available: false,
        tier: 'paid',
      },
    ],
  },
];

vi.mock('@google/gemini-cli-core', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('@google/gemini-cli-core')>();
  return {
    ...actual,
    isOllamaRunning: async () => false,
    isLMStudioRunning: async () => false,
    groupModelsByProvider: () => GROUPS,
  };
});

describe('<ProviderModelDialog />', () => {
  it('lists registry models from every provider with availability marks', async () => {
    const { lastFrame, waitUntilReady } = await renderWithProviders(
      <ProviderModelDialog onClose={vi.fn()} />,
    );
    // Flush the async local-model detection effect inside act.
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    await waitUntilReady();
    await waitFor(() => {
      const frame = lastFrame({ allowEmpty: true }) ?? '';
      expect(frame).toContain('groq-llama');
      expect(frame).toContain('gpt-4o');
    });
    const frame = lastFrame({ allowEmpty: true }) ?? '';
    expect(frame).toContain('✓ groq-llama');
    expect(frame).toContain('✗ gpt-4o');
    expect(frame).toContain('needs OPENAI_API_KEY');
  });
});

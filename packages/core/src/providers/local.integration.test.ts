/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Integration tests against real local servers. Skipped in CI and
 * whenever the servers are not running; enable locally with
 * `RUN_LOCAL_PROVIDER_TESTS=1` plus a live Ollama / LM Studio.
 */

import { describe, it, expect } from 'vitest';
import {
  isOllamaRunning,
  listOllamaModels,
  resolveOllamaModel,
} from './ollama.js';
import { isLMStudioRunning, listLMStudioModels } from './lmstudio.js';
import { OpenAICompatContentGenerator } from './openaiCompatGenerator.js';
import { getProvider } from './providers.js';

const runLocal =
  process.env['RUN_LOCAL_PROVIDER_TESTS'] === '1' && !process.env['CI'];

describe.skipIf(!runLocal)('Ollama (live server)', () => {
  it('detects the server and lists installed models', async () => {
    expect(await isOllamaRunning()).toBe(true);
    const models = await listOllamaModels();
    expect(models.length).toBeGreaterThan(0);
  });

  it('completes a prompt through the OpenAI-compatible route', async () => {
    const model = await resolveOllamaModel();
    const generator = new OpenAICompatContentGenerator({
      modelId: `ollama/${model}`,
      provider: getProvider('ollama')!,
    });
    const response = await generator.generateContent(
      {
        model,
        contents: [{ role: 'user', parts: [{ text: 'Say "ok".' }] }],
        config: { maxOutputTokens: 16 },
      },
      'integration-test',
    );
    const text = response.candidates?.[0]?.content?.parts?.[0]?.text;
    expect(typeof text).toBe('string');
  }, 60_000);
});

describe.skipIf(!runLocal)('LM Studio (live server)', () => {
  it('detects the server and lists loaded models', async () => {
    expect(await isLMStudioRunning()).toBe(true);
    const models = await listLMStudioModels();
    expect(Array.isArray(models)).toBe(true);
  });
});

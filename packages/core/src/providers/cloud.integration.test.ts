/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Live integration tests against real cloud provider endpoints, one per
 * provider. Skipped in CI and for any provider whose API key is not set;
 * enable locally with `RUN_LIVE_PROVIDER_TESTS=1` plus the keys you have:
 *
 *   RUN_LIVE_PROVIDER_TESTS=1 GROQ_API_KEY=... npx vitest run src/providers/cloud.integration.test.ts
 */

import { describe, it, expect } from 'vitest';
import { OpenAICompatContentGenerator } from './openaiCompatGenerator.js';
import { getProvider, providerApiKey } from './providers.js';

const runLive =
  process.env['RUN_LIVE_PROVIDER_TESTS'] === '1' && !process.env['CI'];

/** One cheap/free model per cloud provider for a minimal live probe. */
const LIVE_MATRIX: Array<{ providerId: string; model: string }> = [
  { providerId: 'openai', model: 'openai/gpt-4o-mini' },
  { providerId: 'anthropic', model: 'anthropic/claude-haiku-4-5' },
  { providerId: 'gemini', model: 'gemini/gemini-2.5-flash' },
  { providerId: 'groq', model: 'groq/llama-3.1-8b-instant' },
  { providerId: 'deepseek', model: 'deepseek/deepseek-chat' },
  { providerId: 'nvidia', model: 'nvidia/nemotron-3-super-120b-a12b' },
  {
    providerId: 'together',
    model: 'together/meta-llama/Llama-3.3-70B-Instruct-Turbo',
  },
  {
    providerId: 'huggingface',
    model: 'huggingface/meta-llama/Meta-Llama-3-8B-Instruct',
  },
  { providerId: 'openrouter', model: 'openrouter/openai/gpt-oss-20b:free' },
  { providerId: 'cerebras', model: 'cerebras/gpt-oss-120b' },
  { providerId: 'z-ai', model: 'z-ai/glm-5' },
];

for (const { providerId, model } of LIVE_MATRIX) {
  const provider = getProvider(providerId);
  const hasKey =
    provider !== undefined && providerApiKey(provider) !== undefined;

  describe.skipIf(!runLive || !hasKey)(`${providerId} (live endpoint)`, () => {
    it(`completes a tiny prompt on ${model}`, async () => {
      const generator = new OpenAICompatContentGenerator({
        modelId: model,
        provider: provider!,
      });
      const response = await generator.generateContent(
        {
          model,
          contents: [
            { role: 'user', parts: [{ text: 'Reply with the word: ok' }] },
          ],
          config: { maxOutputTokens: 16, temperature: 0 },
        },
        'live-integration-test',
      );
      const text = response.candidates?.[0]?.content?.parts
        ?.map((p) => p.text ?? '')
        .join('');
      expect(typeof text).toBe('string');
      expect((text ?? '').length).toBeGreaterThan(0);
    }, 60_000);

    it(`streams a tiny prompt on ${model}`, async () => {
      const generator = new OpenAICompatContentGenerator({
        modelId: model,
        provider: provider!,
      });
      const chunks: string[] = [];
      const stream = await generator.generateContentStream(
        {
          model,
          contents: [{ role: 'user', parts: [{ text: 'Count from 1 to 3.' }] }],
          config: { maxOutputTokens: 32, temperature: 0 },
        },
        'live-integration-test',
      );
      for await (const chunk of stream) {
        const text = chunk.candidates?.[0]?.content?.parts?.[0]?.text;
        if (text) chunks.push(text);
      }
      expect(chunks.length).toBeGreaterThan(0);
    }, 60_000);
  });
}

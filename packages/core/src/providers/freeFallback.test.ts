/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, it, expect, vi } from 'vitest';
import { FreeFallbackContentGenerator } from './freeFallback.js';
import { OpenAICompatContentGenerator } from './openaiCompatGenerator.js';
import { FreeModelsExhaustedError } from './freeCatalog.js';
import { ModelRegistry } from './modelRegistry.js';
import { getProvider } from './providers.js';
import { LlmRole } from '../telemetry/llmRole.js';
import type { GenerateContentParameters } from '@google/genai';

const REGISTRY = ModelRegistry.load(
  path.join(
    path.dirname(fileURLToPath(import.meta.url)),
    '..',
    '..',
    '..',
    '..',
    'configs',
    'models.toml',
  ),
);

const REQUEST: GenerateContentParameters = {
  model: 'test',
  contents: [{ role: 'user', parts: [{ text: 'hi' }] }],
};

const ENV_ALL_KEYS: NodeJS.ProcessEnv = {
  OPENROUTER_API_KEY: 'or-key',
  GROQ_API_KEY: 'groq-key',
  GEMINI_API_KEY: 'gem-key',
  HUGGINGFACE_API_KEY: 'hf-key',
  CEREBRAS_API_KEY: 'cb-key',
};

function makePrimary(
  fetchImpl: typeof fetch,
  env: NodeJS.ProcessEnv = ENV_ALL_KEYS,
): OpenAICompatContentGenerator {
  return new OpenAICompatContentGenerator({
    modelId: 'openrouter/free',
    provider: getProvider('openrouter')!,
    env,
    fetchImpl,
  });
}

function okResponse(text: string): Response {
  return new Response(
    JSON.stringify({
      choices: [{ message: { content: text }, finish_reason: 'stop' }],
      model: 'whatever',
    }),
    { status: 200, headers: { 'Content-Type': 'application/json' } },
  );
}

describe('FreeFallbackContentGenerator', () => {
  it('passes through when the primary model succeeds', async () => {
    const fetchImpl = vi.fn(async () => okResponse('primary answer'));
    const wrapper = new FreeFallbackContentGenerator(
      makePrimary(fetchImpl as unknown as typeof fetch),
      ENV_ALL_KEYS,
    );
    const response = await wrapper.generateContent(REQUEST, 'p', LlmRole.MAIN);
    expect(response.candidates?.[0]?.content?.parts?.[0]?.text).toBe(
      'primary answer',
    );
    expect(wrapper.activeModelId).toBe('openrouter/free');
  });

  it('rethrows non-routing failures without falling back', async () => {
    const fetchImpl = vi.fn(
      async () => new Response('{"error":"invalid api key"}', { status: 401 }),
    );
    const wrapper = new FreeFallbackContentGenerator(
      makePrimary(fetchImpl as unknown as typeof fetch),
      ENV_ALL_KEYS,
    );
    await expect(
      wrapper.generateContent(REQUEST, 'p', LlmRole.MAIN),
    ).rejects.toThrow(/401/);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it('falls through the catalog on a tool-use routing failure', async () => {
    // Primary (openrouter/free) fails the way OpenRouter's free router
    // does for agents; candidate generators use the real global fetch,
    // so stub it per-URL.
    const primaryFetch = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            error: { message: 'No endpoints found that support tool use' },
          }),
          { status: 404 },
        ),
    );
    const globalFetch = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(async () => okResponse('fallback answer'));
    try {
      const wrapper = new FreeFallbackContentGenerator(
        makePrimary(primaryFetch as unknown as typeof fetch),
        ENV_ALL_KEYS,
        { registry: REGISTRY },
      );
      const response = await wrapper.generateContent(
        REQUEST,
        'p',
        LlmRole.MAIN,
      );
      expect(response.candidates?.[0]?.content?.parts?.[0]?.text).toBe(
        'fallback answer',
      );
      // The winning fallback stays active for the next request.
      expect(wrapper.activeModelId).not.toBe('openrouter/free');
      const callsAfterSuccess = globalFetch.mock.calls.length;
      await wrapper.generateContent(REQUEST, 'p', LlmRole.MAIN);
      expect(primaryFetch).toHaveBeenCalledTimes(1);
      expect(globalFetch.mock.calls.length).toBe(callsAfterSuccess + 1);
    } finally {
      globalFetch.mockRestore();
    }
  });

  it('throws FreeModelsExhaustedError when every candidate fails', async () => {
    const rateLimited = async () =>
      new Response(
        JSON.stringify({ error: { message: 'rate_limit_exceeded' } }),
        { status: 429 },
      );
    const primaryFetch = vi.fn(rateLimited);
    const globalFetch = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(rateLimited as unknown as typeof fetch);
    try {
      const wrapper = new FreeFallbackContentGenerator(
        makePrimary(primaryFetch as unknown as typeof fetch),
        ENV_ALL_KEYS,
        { registry: REGISTRY },
      );
      await expect(
        wrapper.generateContent(REQUEST, 'p', LlmRole.MAIN),
      ).rejects.toThrow(FreeModelsExhaustedError);
    } finally {
      globalFetch.mockRestore();
    }
  });

  it('rotates to the next free model when the primary returns an empty 200 completion', async () => {
    // Reproduces the silent "Thinking... then stops" symptom: an overloaded
    // free router answers HTTP 200 with no content and no tool calls.
    // The empty-response guard classifies this as a routing failure, so the
    // fallback chain should rotate to a working candidate instead of
    // returning a zero-parts response.
    const emptyOk = async () =>
      new Response(
        JSON.stringify({
          choices: [{ message: { content: null }, finish_reason: 'stop' }],
          model: 'whatever',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      );
    const primaryFetch = vi.fn(emptyOk);
    const globalFetch = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(async () => okResponse('recovered answer'));
    try {
      const wrapper = new FreeFallbackContentGenerator(
        makePrimary(primaryFetch as unknown as typeof fetch),
        ENV_ALL_KEYS,
        { registry: REGISTRY },
      );
      const response = await wrapper.generateContent(
        REQUEST,
        'p',
        LlmRole.MAIN,
      );
      expect(response.candidates?.[0]?.content?.parts?.[0]?.text).toBe(
        'recovered answer',
      );
      expect(wrapper.activeModelId).not.toBe('openrouter/free');
    } finally {
      globalFetch.mockRestore();
    }
  });
});

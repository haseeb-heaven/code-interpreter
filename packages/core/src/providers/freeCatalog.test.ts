/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect } from 'vitest';
import { ModelRegistry } from './modelRegistry.js';
import {
  FreeLLMCatalog,
  FreeModelsExhaustedError,
  formatFreeModelsExhaustedMessage,
  freeFallbackCandidates,
  isDailyFreeQuotaExhausted,
  isEntryAvailable,
  isFreeRoutingFailure,
  isRateLimitFailure,
  matchCatalogEntry,
  parseRetryAfterSeconds,
} from './freeCatalog.js';

function testRegistry(): ModelRegistry {
  return new ModelRegistry('test://models.toml', {
    default_model: 'gpt-4o',
    models: {
      'openrouter-free': {
        model: 'openrouter/free',
        provider: 'openrouter',
        api_base: 'https://openrouter.ai/api/v1',
      },
      'openrouter-qwen3-coder': {
        model: 'qwen/qwen3-coder:free',
        provider: 'openrouter',
        api_base: 'https://openrouter.ai/api/v1',
      },
      'groq-llama-3.1-8b': { model: 'groq/llama-3.1-8b-instant' },
      'gemini-2.5-flash': { model: 'gemini/gemini-2.5-flash' },
      'local-model': {
        model: 'llama3.1:8b',
        provider: 'local',
        api_base: 'http://localhost:11434/v1',
      },
      'lmstudio-local': {
        model: 'lmstudio/local-model',
        provider: 'lmstudio',
        api_base: 'http://localhost:1234/v1',
      },
    },
    free_catalog: [
      {
        id: 'openrouter-free',
        model_key: 'openrouter-free',
        provider: 'openrouter',
        env_key: 'OPENROUTER_API_KEY',
        tier: 'free',
        notes: '',
      },
      {
        id: 'openrouter-qwen3-coder',
        model_key: 'openrouter-qwen3-coder',
        provider: 'openrouter',
        env_key: 'OPENROUTER_API_KEY',
        tier: 'free',
        notes: '',
      },
      {
        id: 'groq-llama-3.1-8b',
        model_key: 'groq-llama-3.1-8b',
        provider: 'groq',
        env_key: 'GROQ_API_KEY',
        tier: 'free_tier',
        notes: '',
      },
      {
        id: 'gemini-2.5-flash',
        model_key: 'gemini-2.5-flash',
        provider: 'gemini',
        env_key: 'GEMINI_API_KEY',
        tier: 'free_tier',
        notes: '',
      },
      {
        id: 'local-model',
        model_key: 'local-model',
        provider: 'local',
        env_key: '',
        tier: 'local',
        notes: '',
      },
      {
        id: 'lmstudio',
        model_key: 'lmstudio-local',
        provider: 'lmstudio',
        env_key: '',
        tier: 'local',
        notes: '',
      },
    ],
    default_priority: [],
  });
}

const ALL_KEYS = {
  OPENROUTER_API_KEY: 'sk-or',
  GROQ_API_KEY: 'gsk',
  GEMINI_API_KEY: 'ai',
};

describe('FreeLLMCatalog', () => {
  it('loads every catalog row from the registry', () => {
    const catalog = FreeLLMCatalog.load(testRegistry());
    expect(catalog.length).toBe(6);
    expect(catalog.get('openrouter-free')?.provider).toBe('openrouter');
  });

  it('local entries are always available; cloud entries need their key', () => {
    const catalog = FreeLLMCatalog.load(testRegistry());
    const local = catalog.get('local-model')!;
    const cloud = catalog.get('openrouter-free')!;
    expect(isEntryAvailable(local, {})).toBe(true);
    expect(isEntryAvailable(cloud, {})).toBe(false);
    expect(isEntryAvailable(cloud, { OPENROUTER_API_KEY: 'x' })).toBe(true);
  });

  it('available() filters by env keys and registry membership', () => {
    const registry = testRegistry();
    const catalog = FreeLLMCatalog.load(registry);
    const available = catalog.available({ GROQ_API_KEY: 'x' }, registry);
    expect(available.map((e) => e.config)).toEqual([
      'groq-llama-3.1-8b',
      'local-model',
      'lmstudio-local',
    ]);
  });

  it('pickDefault returns the first available config with preferred order', () => {
    const registry = testRegistry();
    const catalog = FreeLLMCatalog.load(registry);
    expect(catalog.pickDefault({ GROQ_API_KEY: 'x' }, registry)).toBe(
      'groq-llama-3.1-8b',
    );
    expect(catalog.pickDefault(ALL_KEYS, registry, ['gemini-2.5-flash'])).toBe(
      'gemini-2.5-flash',
    );
  });
});

describe('failure classification', () => {
  it('detects rate limits', () => {
    expect(isRateLimitFailure(new Error('429 Too Many Requests'))).toBe(true);
    expect(isRateLimitFailure(new Error('tokens per minute (TPM)'))).toBe(true);
    expect(isRateLimitFailure(new Error('invalid api key'))).toBe(false);
  });

  it('routing failures fall through; auth/billing failures do not', () => {
    expect(isFreeRoutingFailure(new Error('502 Bad Gateway'))).toBe(true);
    expect(
      isFreeRoutingFailure(
        new Error('No endpoints found that support tool use'),
      ),
    ).toBe(true);
    expect(isFreeRoutingFailure(new Error('401 unauthorized'))).toBe(false);
    expect(isFreeRoutingFailure(new Error('payment required'))).toBe(false);
  });

  it('detects exhausted daily free quotas', () => {
    expect(
      isDailyFreeQuotaExhausted(new Error('free-models-per-day: Remaining: 0')),
    ).toBe(true);
    expect(isDailyFreeQuotaExhausted(new Error('429'))).toBe(false);
  });

  it('parses retry-after hints with a cap', () => {
    expect(parseRetryAfterSeconds('try again in 2.5s')).toBe(2.5);
    expect(parseRetryAfterSeconds('Retry-after: 600')).toBe(60);
    expect(parseRetryAfterSeconds('no hint here')).toBeUndefined();
  });
});

describe('freeFallbackCandidates (full chain)', () => {
  it('jumps off OpenRouter first and ends with local models', () => {
    const registry = testRegistry();
    const candidates = freeFallbackCandidates('openrouter/free', {
      registry,
      env: ALL_KEYS,
    });
    const configs = candidates.map((c) => c.config);
    expect(configs).toEqual([
      'groq-llama-3.1-8b',
      'gemini-2.5-flash',
      'openrouter-qwen3-coder',
      'local-model',
      'lmstudio-local',
    ]);
  });

  it('prefers same-provider siblings for non-OpenRouter failures', () => {
    const registry = testRegistry();
    const candidates = freeFallbackCandidates('groq/llama-3.1-8b-instant', {
      registry,
      env: ALL_KEYS,
    });
    const configs = candidates.map((c) => c.config);
    // No groq sibling exists, so other remote free models come first…
    expect(configs[0]).toBe('openrouter-free');
    // …and local models are always the final fallback.
    expect(configs.slice(-2)).toEqual(['local-model', 'lmstudio-local']);
  });

  it('local models remain when no cloud key is configured', () => {
    const registry = testRegistry();
    const candidates = freeFallbackCandidates('openrouter/free', {
      registry,
      env: {},
    });
    expect(candidates.map((c) => c.config)).toEqual([
      'local-model',
      'lmstudio-local',
    ]);
  });

  it('resolves candidate routing metadata from the registry', () => {
    const registry = testRegistry();
    const [first] = freeFallbackCandidates('groq/llama-3.1-8b-instant', {
      registry,
      env: { OPENROUTER_API_KEY: 'x' },
    });
    expect(first.model).toBe('openrouter/free');
    expect(first.apiBase).toBe('https://openrouter.ai/api/v1');
    expect(first.temperature).toBe(0.1);
    expect(first.maxTokens).toBe(4096);
  });

  it('matchCatalogEntry maps litellm ids back to catalog entries', () => {
    const registry = testRegistry();
    const catalog = FreeLLMCatalog.load(registry);
    expect(
      matchCatalogEntry('qwen/qwen3-coder:free', catalog, registry)?.config,
    ).toBe('openrouter-qwen3-coder');
    expect(
      matchCatalogEntry('unknown-model', catalog, registry),
    ).toBeUndefined();
  });
});

describe('FreeModelsExhaustedError', () => {
  it('formats a helpful exhaustion message', () => {
    const error = new FreeModelsExhaustedError(
      'exhausted',
      ['openrouter/free', 'groq/llama-3.1-8b-instant'],
      new Error('429 rate limit'),
    );
    expect(error.tried).toHaveLength(2);
    const message = formatFreeModelsExhaustedMessage(
      error.tried,
      error.lastError,
    );
    expect(message).toContain('openrouter/free');
    expect(message).toContain('429 rate limit');
    expect(message).toContain('/byok');
  });
});

/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect } from 'vitest';
import { ModelRegistry } from './modelRegistry.js';
import { resolveProviderRoute } from './resolve.js';

const registry = new ModelRegistry('test://models.toml', {
  default_model: 'gpt-4o',
  models: {
    'gpt-4o': { model: 'gpt-4o' },
    'groq-llama-3.1-8b': {
      model: 'groq/llama-3.1-8b-instant',
      tier: 'free_tier',
    },
    'openrouter-free': {
      model: 'openrouter/free',
      provider: 'openrouter',
      api_base: 'https://openrouter.ai/api/v1',
      temperature: 0.1,
      max_tokens: 4096,
    },
    'claude-sonnet-4-6': {
      model: 'claude-sonnet-4-6',
      provider: 'anthropic',
    },
    'browser-use-bu-max': {
      model: 'bu-max',
      provider: 'browser-use',
      api_base: 'https://api.browser-use.com/api/v3',
    },
    'local-model': {
      model: 'llama3.1:8b',
      provider: 'local',
      api_base: 'http://localhost:11434/v1',
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
      id: 'local-model',
      model_key: 'local-model',
      provider: 'local',
      env_key: '',
      tier: 'local',
      notes: '',
    },
  ],
  default_priority: [
    { env: 'OPENAI_API_KEY', model: 'gpt-4o' },
    { env: 'GROQ_API_KEY', model: 'groq-llama-3.1-8b' },
  ],
});

const ollamaUp = {
  probeOllama: async () => true,
  listOllama: async () => ['llama3.1:8b', 'mistral:latest'],
};
const ollamaDown = {
  probeOllama: async () => false,
  listOllama: async () => [],
};
const lmStudioUp = {
  probeLMStudio: async () => true,
  listLMStudio: async () => ['qwen2.5-coder-7b-instruct'],
};
const lmStudioDown = {
  probeLMStudio: async () => false,
  listLMStudio: async () => [],
};

describe('resolveProviderRoute', () => {
  it('tries Ollama first when no provider is specified', async () => {
    const route = await resolveProviderRoute({
      registry,
      env: { OPENAI_API_KEY: 'sk' },
      ...ollamaUp,
      ...lmStudioDown,
    });
    expect(route?.provider.id).toBe('ollama');
    expect(route?.modelId).toBe('ollama/llama3.1:8b');
    expect(route?.source).toBe('ollama-auto');
  });

  it('falls back to LM Studio when Ollama is down', async () => {
    const route = await resolveProviderRoute({
      registry,
      env: {},
      ...ollamaDown,
      ...lmStudioUp,
    });
    expect(route?.provider.id).toBe('lmstudio');
    expect(route?.modelId).toBe('lmstudio/qwen2.5-coder-7b-instruct');
  });

  it('falls back to [[default_priority]] when no local server runs', async () => {
    const route = await resolveProviderRoute({
      registry,
      env: { GROQ_API_KEY: 'gsk' },
      ...ollamaDown,
      ...lmStudioDown,
    });
    expect(route?.provider.id).toBe('groq');
    expect(route?.modelId).toBe('groq/llama-3.1-8b-instant');
    expect(route?.source).toBe('default-priority');
  });

  it('--provider ollama pins to the local server', async () => {
    const route = await resolveProviderRoute({
      provider: 'ollama',
      registry,
      env: {},
      ...ollamaUp,
      ...lmStudioDown,
    });
    expect(route?.modelId).toBe('ollama/llama3.1:8b');
  });

  it('--model resolves registry keys with routing metadata', async () => {
    const route = await resolveProviderRoute({
      model: 'openrouter-free',
      registry,
      env: { OPENROUTER_API_KEY: 'sk-or' },
      ...ollamaDown,
      ...lmStudioDown,
    });
    expect(route?.provider.id).toBe('openrouter');
    expect(route?.modelId).toBe('openrouter/free');
    expect(route?.apiBase).toBe('https://openrouter.ai/api/v1');
  });

  it('--free picks the first available free preset', async () => {
    const route = await resolveProviderRoute({
      free: true,
      registry,
      env: { OPENROUTER_API_KEY: 'sk-or' },
      ...ollamaDown,
      ...lmStudioDown,
    });
    expect(route?.source).toBe('free-catalog');
    expect(route?.modelId).toBe('openrouter/free');
  });

  it('--free falls back to local detection without cloud keys', async () => {
    const route = await resolveProviderRoute({
      free: true,
      registry,
      env: {},
      ...ollamaUp,
      ...lmStudioDown,
    });
    expect(route?.provider.id).toBe('ollama');
  });

  it('--provider anthropic (no -m) finds the default model tagged for it in the registry', async () => {
    const route = await resolveProviderRoute({
      provider: 'anthropic',
      registry,
      env: { ANTHROPIC_API_KEY: 'sk-ant' },
      ...ollamaDown,
      ...lmStudioDown,
    });
    expect(route?.provider.id).toBe('anthropic');
    expect(route?.modelId).toBe('anthropic/claude-sonnet-4-6');
    expect(route?.source).toBe('explicit');
  });

  it('an entry tagged with an unsupported provider is never misrouted to openrouter/openai', async () => {
    const route = await resolveProviderRoute({
      model: 'browser-use-bu-max',
      registry,
      env: { OPENROUTER_API_KEY: 'sk-or', OPENAI_API_KEY: 'sk' },
      ...ollamaDown,
      ...lmStudioDown,
    });
    expect(route).toBeUndefined();
  });

  it('a registry entry tagged provider="local" routes to ollama, not openrouter/openai', async () => {
    const route = await resolveProviderRoute({
      model: 'local-model',
      registry,
      env: { OPENROUTER_API_KEY: 'sk-or', OPENAI_API_KEY: 'sk' },
      ...ollamaDown,
      ...lmStudioDown,
    });
    expect(route?.provider.id).toBe('ollama');
    expect(route?.modelId).toBe('llama3.1:8b');
  });

  it('returns undefined when nothing resolves', async () => {
    const route = await resolveProviderRoute({
      registry,
      env: {},
      ...ollamaDown,
      ...lmStudioDown,
    });
    expect(route).toBeUndefined();
  });
});

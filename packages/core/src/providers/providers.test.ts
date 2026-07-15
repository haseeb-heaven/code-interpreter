/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect } from 'vitest';
import {
  ENV_KEY_ALIASES,
  getProvider,
  isProviderAvailable,
  listProviderIds,
  providerApiKey,
  splitModelId,
} from './providers.js';

/** Expected wiring for every supported provider. */
const EXPECTED_PROVIDERS: Array<{
  id: string;
  envKey: string | null;
  apiBase: string;
  local: boolean;
}> = [
  {
    id: 'ollama',
    envKey: null,
    apiBase: 'http://localhost:11434/v1',
    local: true,
  },
  {
    id: 'lmstudio',
    envKey: null,
    apiBase: 'http://localhost:1234/v1',
    local: true,
  },
  {
    id: 'openai',
    envKey: 'OPENAI_API_KEY',
    apiBase: 'https://api.openai.com/v1',
    local: false,
  },
  {
    id: 'anthropic',
    envKey: 'ANTHROPIC_API_KEY',
    apiBase: 'https://api.anthropic.com/v1',
    local: false,
  },
  {
    id: 'gemini',
    envKey: 'GEMINI_API_KEY',
    apiBase: 'https://generativelanguage.googleapis.com/v1beta/openai',
    local: false,
  },
  {
    id: 'groq',
    envKey: 'GROQ_API_KEY',
    apiBase: 'https://api.groq.com/openai/v1',
    local: false,
  },
  {
    id: 'deepseek',
    envKey: 'DEEPSEEK_API_KEY',
    apiBase: 'https://api.deepseek.com/v1',
    local: false,
  },
  {
    id: 'nvidia',
    envKey: 'NVIDIA_API_KEY',
    apiBase: 'https://integrate.api.nvidia.com/v1',
    local: false,
  },
  {
    id: 'together',
    envKey: 'TOGETHER_API_KEY',
    apiBase: 'https://api.together.xyz/v1',
    local: false,
  },
  {
    id: 'huggingface',
    envKey: 'HF_TOKEN',
    apiBase: 'https://router.huggingface.co/v1',
    local: false,
  },
  {
    id: 'openrouter',
    envKey: 'OPENROUTER_API_KEY',
    apiBase: 'https://openrouter.ai/api/v1',
    local: false,
  },
  {
    id: 'cerebras',
    envKey: 'CEREBRAS_API_KEY',
    apiBase: 'https://api.cerebras.ai/v1',
    local: false,
  },
  {
    id: 'z-ai',
    envKey: 'Z_AI_API_KEY',
    apiBase: 'https://api.z.ai/api/paas/v4',
    local: false,
  },
];

describe('provider definitions', () => {
  it('declares every provider from the original project plus local ones', () => {
    expect(listProviderIds()).toEqual(EXPECTED_PROVIDERS.map((p) => p.id));
  });

  it.each(EXPECTED_PROVIDERS)(
    '$id uses env key $envKey and base $apiBase',
    ({ id, envKey, apiBase, local }) => {
      const provider = getProvider(id);
      expect(provider).toBeDefined();
      expect(provider?.envKey).toBe(envKey);
      expect(provider?.apiBase).toBe(apiBase);
      expect(provider?.local).toBe(local);
      // Every provider must support streaming.
      expect(provider?.streaming).toBe(true);
    },
  );

  it.each(EXPECTED_PROVIDERS.filter((p) => p.local))(
    'local provider $id is always available without any key',
    ({ id }) => {
      const provider = getProvider(id);
      expect(isProviderAvailable(provider!, {})).toBe(true);
      expect(providerApiKey(provider!, { ANYTHING: 'x' })).toBeUndefined();
    },
  );

  it.each(EXPECTED_PROVIDERS.filter((p) => !p.local))(
    'cloud provider $id requires $envKey',
    ({ id, envKey }) => {
      const provider = getProvider(id)!;
      expect(isProviderAvailable(provider, {})).toBe(false);
      const env = { [String(envKey)]: 'test-key' };
      expect(isProviderAvailable(provider, env)).toBe(true);
      expect(providerApiKey(provider, env)).toBe('test-key');
    },
  );

  it('accepts documented env key aliases', () => {
    expect(ENV_KEY_ALIASES['huggingface']).toContain('HUGGINGFACE_API_KEY');
    expect(
      providerApiKey(getProvider('huggingface')!, {
        HUGGINGFACE_API_KEY: 'hf-alias',
      }),
    ).toBe('hf-alias');
    expect(
      providerApiKey(getProvider('gemini')!, { GOOGLE_API_KEY: 'g-alias' }),
    ).toBe('g-alias');
  });
});

describe('splitModelId', () => {
  it.each(EXPECTED_PROVIDERS)('parses $id/<model> ids', ({ id }) => {
    const { provider, model } = splitModelId(`${id}/some-model:tag`);
    expect(provider?.id).toBe(id);
    expect(model).toBe('some-model:tag');
  });

  it('returns no provider for bare or unknown-prefixed ids', () => {
    expect(splitModelId('gpt-4o').provider).toBeUndefined();
    expect(splitModelId('unknown/model').provider).toBeUndefined();
    expect(splitModelId('unknown/model').model).toBe('unknown/model');
  });
});

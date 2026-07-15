/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Multi-provider definitions for LiteLLM-style routing.
 *
 * Mirrors the provider set of the original Python code-interpreter project
 * (see configs/models.toml) plus first-class local providers (Ollama and
 * LM Studio). Model ids use the LiteLLM convention `provider/model`, e.g.
 * `ollama/llama3.1:8b`, `groq/llama-3.1-8b-instant`, `openai/gpt-4o`.
 */

export const OLLAMA_BASE_URL = 'http://localhost:11434';
export const LMSTUDIO_BASE_URL = 'http://localhost:1234';

export interface ProviderDefinition {
  /** Canonical provider id (LiteLLM-style prefix). */
  id: string;
  /** Human-readable name for picker output. */
  displayName: string;
  /** Environment variable holding the API key; null for local providers. */
  envKey: string | null;
  /** Default OpenAI-compatible base URL (chat completions). */
  apiBase: string;
  /** True for providers running on localhost without any API key. */
  local: boolean;
  /** Whether the provider generally supports image (vision) input. */
  vision: boolean;
  /** Whether the provider supports token streaming. */
  streaming: boolean;
}

/**
 * Every supported provider. Order matters: it is the display order of the
 * model picker and the probe order when no provider is specified (local
 * first, Ollama before LM Studio).
 */
export const PROVIDERS: readonly ProviderDefinition[] = [
  {
    id: 'ollama',
    displayName: 'Ollama (local)',
    envKey: null,
    apiBase: `${OLLAMA_BASE_URL}/v1`,
    local: true,
    vision: true,
    streaming: true,
  },
  {
    id: 'lmstudio',
    displayName: 'LM Studio (local)',
    envKey: null,
    apiBase: `${LMSTUDIO_BASE_URL}/v1`,
    local: true,
    vision: true,
    streaming: true,
  },
  {
    id: 'openai',
    displayName: 'OpenAI',
    envKey: 'OPENAI_API_KEY',
    apiBase: 'https://api.openai.com/v1',
    local: false,
    vision: true,
    streaming: true,
  },
  {
    id: 'anthropic',
    displayName: 'Anthropic',
    envKey: 'ANTHROPIC_API_KEY',
    apiBase: 'https://api.anthropic.com/v1',
    local: false,
    vision: true,
    streaming: true,
  },
  {
    id: 'gemini',
    displayName: 'Gemini',
    envKey: 'GEMINI_API_KEY',
    apiBase: 'https://generativelanguage.googleapis.com/v1beta/openai',
    local: false,
    vision: true,
    streaming: true,
  },
  {
    id: 'groq',
    displayName: 'Groq',
    envKey: 'GROQ_API_KEY',
    apiBase: 'https://api.groq.com/openai/v1',
    local: false,
    vision: false,
    streaming: true,
  },
  {
    id: 'deepseek',
    displayName: 'DeepSeek',
    envKey: 'DEEPSEEK_API_KEY',
    apiBase: 'https://api.deepseek.com/v1',
    local: false,
    vision: false,
    streaming: true,
  },
  {
    id: 'nvidia',
    displayName: 'NVIDIA',
    envKey: 'NVIDIA_API_KEY',
    apiBase: 'https://integrate.api.nvidia.com/v1',
    local: false,
    vision: false,
    streaming: true,
  },
  {
    id: 'together',
    displayName: 'Together AI',
    envKey: 'TOGETHER_API_KEY',
    apiBase: 'https://api.together.xyz/v1',
    local: false,
    vision: true,
    streaming: true,
  },
  {
    id: 'huggingface',
    displayName: 'HuggingFace',
    envKey: 'HF_TOKEN',
    apiBase: 'https://router.huggingface.co/v1',
    local: false,
    vision: false,
    streaming: true,
  },
  {
    id: 'openrouter',
    displayName: 'OpenRouter',
    envKey: 'OPENROUTER_API_KEY',
    apiBase: 'https://openrouter.ai/api/v1',
    local: false,
    vision: true,
    streaming: true,
  },
  {
    id: 'cerebras',
    displayName: 'Cerebras',
    envKey: 'CEREBRAS_API_KEY',
    apiBase: 'https://api.cerebras.ai/v1',
    local: false,
    vision: false,
    streaming: true,
  },
  {
    id: 'z-ai',
    displayName: 'Z.ai',
    envKey: 'Z_AI_API_KEY',
    apiBase: 'https://api.z.ai/api/paas/v4',
    local: false,
    vision: false,
    streaming: true,
  },
] as const;

/** Extra env var aliases accepted per provider (checked after `envKey`). */
export const ENV_KEY_ALIASES: Readonly<Record<string, readonly string[]>> = {
  huggingface: ['HUGGINGFACE_API_KEY'],
  gemini: ['GOOGLE_API_KEY'],
};

export function getProvider(id: string): ProviderDefinition | undefined {
  const needle = (id ?? '').trim().toLowerCase();
  return PROVIDERS.find((p) => p.id === needle);
}

export function listProviderIds(): string[] {
  return PROVIDERS.map((p) => p.id);
}

/**
 * Returns the API key for a provider from `env`, or `undefined`.
 * Local providers never need a key (returns `undefined`).
 */
export function providerApiKey(
  provider: ProviderDefinition,
  env: NodeJS.ProcessEnv = process.env,
): string | undefined {
  if (!provider.envKey) return undefined;
  const primary = env[provider.envKey];
  if (primary && primary.trim()) return primary.trim();
  for (const alias of ENV_KEY_ALIASES[provider.id] ?? []) {
    const value = env[alias];
    if (value && value.trim()) return value.trim();
  }
  return undefined;
}

/** True when the provider is usable: local, or its API key is set. */
export function isProviderAvailable(
  provider: ProviderDefinition,
  env: NodeJS.ProcessEnv = process.env,
): boolean {
  return provider.local || providerApiKey(provider, env) !== undefined;
}

/**
 * Splits a LiteLLM-style model id `provider/model` into its parts.
 * Ids without a known provider prefix return `provider: undefined`.
 */
export function splitModelId(modelId: string): {
  provider: ProviderDefinition | undefined;
  model: string;
} {
  const id = (modelId ?? '').trim();
  const slash = id.indexOf('/');
  if (slash > 0) {
    const provider = getProvider(id.slice(0, slash));
    if (provider) {
      return { provider, model: id.slice(slash + 1) };
    }
  }
  return { provider: undefined, model: id };
}

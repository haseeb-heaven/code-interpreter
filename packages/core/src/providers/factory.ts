/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Factory bridging the model id in the session config to the
 * multi-provider router. A model id with a known provider prefix
 * ("ollama/llama3.1:8b", "groq/llama-3.1-8b-instant") or a registry key
 * from configs/models.toml resolves to an OpenAI-compatible route.
 */

import { splitModelId } from './providers.js';
import { ModelRegistry } from './modelRegistry.js';
import { OpenAICompatContentGenerator } from './openaiCompatGenerator.js';

/** True when `modelId` should be routed by the multi-provider layer. */
export function isMultiProviderModel(modelId: string): boolean {
  const { provider } = splitModelId(modelId);
  // Bare gemini/... ids stay on the native Gemini path.
  return provider !== undefined && provider.id !== 'gemini';
}

/**
 * Builds the router for `modelId`, consulting configs/models.toml for
 * api_base/temperature/max_tokens overrides. Returns undefined when the
 * id carries no known provider prefix and no registry entry.
 */
export function createMultiProviderGenerator(
  modelId: string,
  env: NodeJS.ProcessEnv = process.env,
  registry?: ModelRegistry,
): OpenAICompatContentGenerator | undefined {
  const reg = registry ?? ModelRegistry.load();
  let id = (modelId ?? '').trim();
  let cfg = undefined;

  const key = reg.resolveModelKey(id);
  if (key) {
    cfg = reg.getModel(key);
    if (cfg?.model) id = cfg.model;
  }

  const { provider } = splitModelId(id);
  if (!provider) return undefined;

  return new OpenAICompatContentGenerator({
    modelId: id,
    provider,
    apiBase: cfg?.api_base ? String(cfg.api_base) : undefined,
    temperature:
      typeof cfg?.temperature === 'number' ? cfg.temperature : undefined,
    maxTokens: typeof cfg?.max_tokens === 'number' ? cfg.max_tokens : undefined,
    env,
  });
}

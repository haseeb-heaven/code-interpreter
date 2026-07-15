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

import { getProvider, splitModelId } from './providers.js';
import { ModelRegistry, getModelRegistry } from './modelRegistry.js';
import { OpenAICompatContentGenerator } from './openaiCompatGenerator.js';
import { FreeLLMCatalog, matchCatalogEntry } from './freeCatalog.js';
import { FreeFallbackContentGenerator } from './freeFallback.js';

/** True when `modelId` should be routed by the multi-provider layer. */
export function isMultiProviderModel(
  modelId: string,
  registry?: ModelRegistry,
): boolean {
  const id = (modelId ?? '').trim();
  let { provider } = splitModelId(id);
  if (!provider) {
    // Registry keys ("openrouter-gpt-oss-20b-free") carry no prefix but
    // still resolve to a provider route through configs/models.toml.
    const reg = registry ?? getModelRegistry();
    const key = reg.resolveModelKey(id);
    const cfg = key ? reg.getModel(key) : undefined;
    if (cfg?.model) provider = splitModelId(cfg.model).provider;
    if (!provider && cfg?.provider) provider = getProvider(cfg.provider);
  }
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
): OpenAICompatContentGenerator | FreeFallbackContentGenerator | undefined {
  const reg = registry ?? ModelRegistry.load();
  let id = (modelId ?? '').trim();
  let cfg = undefined;

  const key = reg.resolveModelKey(id);
  if (key) {
    cfg = reg.getModel(key);
    if (cfg?.model) id = cfg.model;
  }

  // An explicit provider tag in the registry outranks the id prefix:
  // "openai/gpt-oss-20b:free" with provider = "openrouter" must ship
  // OpenRouter's key to OpenRouter's endpoint, not OpenAI's.
  const configured = cfg?.provider ? getProvider(cfg.provider) : undefined;
  const provider = configured ?? splitModelId(id).provider;
  if (!provider) return undefined;

  const generator = new OpenAICompatContentGenerator({
    modelId: id,
    provider,
    apiBase: cfg?.api_base ? String(cfg.api_base) : undefined,
    temperature:
      typeof cfg?.temperature === 'number' ? cfg.temperature : undefined,
    maxTokens: typeof cfg?.max_tokens === 'number' ? cfg.max_tokens : undefined,
    env,
  });

  // Free-catalog models (and any session started with --free) get the
  // runtime fallback chain: rate limits and free-router failures fall
  // through the catalog instead of killing the request.
  const freeSession = env['GEMINI_CLI_FREE'] === '1';
  const inCatalog =
    matchCatalogEntry(id, FreeLLMCatalog.load(reg), reg) !== undefined;
  if (freeSession || inCatalog) {
    return new FreeFallbackContentGenerator(generator, env, { registry: reg });
  }
  return generator;
}

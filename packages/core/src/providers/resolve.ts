/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Provider/model resolution for startup flags.
 *
 * Resolution order when no explicit provider/model is given:
 *   1. Ollama at localhost:11434 (default provider, auto-detected models)
 *   2. LM Studio at localhost:1234
 *   3. The registry's `[[default_priority]]` rows (first env key set wins)
 *   4. The registry's `default_model`
 */

import {
  getProvider,
  isProviderAvailable,
  splitModelId,
  type ProviderDefinition,
} from './providers.js';
import {
  isOllamaRunning,
  listOllamaModels,
  pickBestOllamaModel,
} from './ollama.js';
import { isLMStudioRunning, listLMStudioModels } from './lmstudio.js';
import { ModelRegistry } from './modelRegistry.js';
import { FreeLLMCatalog } from './freeCatalog.js';

export interface ResolvedRoute {
  /** LiteLLM-style model id, e.g. "ollama/llama3.1:8b". */
  modelId: string;
  /**
   * Registry key the route came from (e.g. "openrouter-gpt-oss-20b-free").
   * Prefer it over modelId when re-resolving: LiteLLM ids may be shared
   * by several alias keys, while keys are unique.
   */
  configKey?: string;
  provider: ProviderDefinition;
  /** Registry api_base override, when the model came from models.toml. */
  apiBase?: string;
  temperature?: number;
  maxTokens?: number;
  /** How the route was chosen (for logging / --pick display). */
  source:
    | 'explicit'
    | 'registry'
    | 'free-catalog'
    | 'ollama-auto'
    | 'lmstudio-auto'
    | 'default-priority';
}

export interface ResolveOptions {
  /** --model / -m value: registry key, free id, or LiteLLM id. */
  model?: string;
  /** --provider value. */
  provider?: string;
  /** --free: prefer the free catalog rotation. */
  free?: boolean;
  allowUnavailable?: boolean;
  registry?: ModelRegistry;
  env?: NodeJS.ProcessEnv;
  /** Injection points for tests. */
  probeOllama?: typeof isOllamaRunning;
  listOllama?: typeof listOllamaModels;
  probeLMStudio?: typeof isLMStudioRunning;
  listLMStudio?: typeof listLMStudioModels;
}

function routeFromRegistry(
  key: string,
  registry: ModelRegistry,
  source: ResolvedRoute['source'],
): ResolvedRoute | undefined {
  const cfg = registry.getModel(key);
  if (!cfg) return undefined;
  const modelId = (cfg.model ?? key).trim();
  const { provider } = splitModelId(modelId);
  const configured = cfg.provider ? getProvider(cfg.provider) : undefined;
  const resolved =
    configured ??
    provider ??
    (cfg.api_base ? getProvider('openrouter') : getProvider('openai'));
  if (!resolved) return undefined;
  return {
    modelId,
    configKey: key,
    provider: resolved,
    apiBase: cfg.api_base ? String(cfg.api_base) : undefined,
    temperature:
      typeof cfg.temperature === 'number' ? cfg.temperature : undefined,
    maxTokens: typeof cfg.max_tokens === 'number' ? cfg.max_tokens : undefined,
    source,
  };
}

async function detectOllamaRoute(
  options: ResolveOptions,
  requestedModel?: string,
): Promise<ResolvedRoute | undefined> {
  const probe = options.probeOllama ?? isOllamaRunning;
  const list = options.listOllama ?? listOllamaModels;
  if (!(await probe())) return undefined;
  const installed = await list();
  const wanted = requestedModel?.replace(/^ollama\//, '');
  const model = wanted
    ? installed.find((m) => m === wanted || m.split(':')[0] === wanted)
    : pickBestOllamaModel(installed);
  if (!model) return undefined;
  const provider = getProvider('ollama');
  if (!provider) return undefined;
  return { modelId: `ollama/${model}`, provider, source: 'ollama-auto' };
}

async function detectLMStudioRoute(
  options: ResolveOptions,
  requestedModel?: string,
): Promise<ResolvedRoute | undefined> {
  const probe = options.probeLMStudio ?? isLMStudioRunning;
  const list = options.listLMStudio ?? listLMStudioModels;
  if (!(await probe())) return undefined;
  const loaded = await list();
  const wanted = requestedModel?.replace(/^lmstudio\//, '');
  const model = wanted ? loaded.find((m) => m === wanted) : loaded[0];
  if (!model) return undefined;
  const provider = getProvider('lmstudio');
  if (!provider) return undefined;
  return { modelId: `lmstudio/${model}`, provider, source: 'lmstudio-auto' };
}

/**
 * Resolves which provider/model to use from startup flags, the registry,
 * and live local-server detection. Returns `undefined` when nothing can
 * be resolved (caller falls back to the stock Gemini flow).
 */
export async function resolveProviderRoute(
  options: ResolveOptions = {},
): Promise<ResolvedRoute | undefined> {
  const registry = options.registry ?? ModelRegistry.load();
  const env = options.env ?? process.env;

  // --provider pins the provider; --model narrows within it.
  if (options.provider) {
    const provider = getProvider(options.provider);
    if (!provider) return undefined;
    if (provider.id === 'ollama') {
      return detectOllamaRoute(options, options.model);
    }
    if (provider.id === 'lmstudio') {
      return detectLMStudioRoute(options, options.model);
    }
    if (!options.allowUnavailable && !isProviderAvailable(provider, env)) return undefined;
    const model =
      options.model ??
      registry
        .listModelNames()
        .map((key) => registry.getModel(key))
        .find(
          (cfg) => cfg && getProvider(cfg.provider ?? '')?.id === provider.id,
        )?.model;
    if (!model) return undefined;
    const bare = splitModelId(model).provider
      ? model
      : `${provider.id}/${model}`;
    return { modelId: bare, provider, source: 'explicit' };
  }

  // --model alone: registry key / free id / LiteLLM id / local model.
  if (options.model) {
    const key = registry.resolveModelKey(options.model);
    if (key) {
      const route = routeFromRegistry(key, registry, 'registry');
      if (route) return route;
    }
    const { provider } = splitModelId(options.model);
    if (provider?.id === 'ollama') {
      return detectOllamaRoute(options, options.model);
    }
    if (provider?.id === 'lmstudio') {
      return detectLMStudioRoute(options, options.model);
    }
    if (provider && (options.allowUnavailable || isProviderAvailable(provider, env))) {
      return { modelId: options.model, provider, source: 'explicit' };
    }
    return undefined;
  }

  // --free: first available free preset, falling back to local detection.
  if (options.free) {
    const catalog = FreeLLMCatalog.load(registry);
    const remote = catalog
      .available(env, registry)
      .find((entry) => entry.envKey);
    if (remote) {
      const route = routeFromRegistry(remote.config, registry, 'free-catalog');
      if (route) return route;
    }
    return (
      (await detectOllamaRoute(options)) ?? (await detectLMStudioRoute(options))
    );
  }

  // No provider specified: try Ollama first, then LM Studio, then the
  // registry's default priority.
  const ollama = await detectOllamaRoute(options);
  if (ollama) return ollama;
  const lmstudio = await detectLMStudioRoute(options);
  if (lmstudio) return lmstudio;

  const defaultKey = registry.defaultModelName(env);
  const route = routeFromRegistry(defaultKey, registry, 'default-priority');
  if (route && (options.allowUnavailable || isProviderAvailable(route.provider, env))) return route;
  return undefined;
}

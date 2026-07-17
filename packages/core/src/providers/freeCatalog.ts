/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Free / cheap LLM catalog and fallback routing.
 *
 * TypeScript port of `libs/free_llms.py` from the original Python
 * code-interpreter project. Backed by the single-file
 * `configs/models.toml` registry (see `modelRegistry.ts`). Helps pick
 * models that work without paid cloud lock-in (OpenRouter free,
 * Groq/Gemini free tiers, Ollama, LM Studio, HF) and orders fallback
 * candidates when a free model fails, with local models as the final
 * fallback.
 */

import type { FreeCatalogEntry, RegistryModelConfig } from './modelRegistry.js';
import { ModelRegistry } from './modelRegistry.js';
import { getProvider, providerApiKey } from './providers.js';

/** One curated free/cheap model preset. */
export interface FreeModelEntry {
  id: string;
  /** Registry key ([models.<config>] in models.toml). */
  config: string;
  provider: string;
  envKey: string | null;
  tier: string;
  notes: string;
}

/** A resolved fallback candidate ready to hand to the router. */
export interface FallbackCandidate {
  config: string;
  model: string;
  provider: string;
  apiBase?: string;
  temperature: number;
  maxTokens: number;
}

const LOCAL_TIERS = new Set(['local']);
const LOCAL_PROVIDERS = new Set(['local', 'ollama', 'lmstudio']);

export function freeModelEntryFromCatalog(
  row: FreeCatalogEntry,
): FreeModelEntry | undefined {
  const config = (row.model_key || row.id || '').trim();
  if (!config) return undefined;
  return {
    id: (row.id || config).trim(),
    config,
    provider: (row.provider || 'unknown').trim(),
    envKey: row.env_key ? row.env_key.trim() : null,
    tier: (row.tier || 'free').trim(),
    notes: (row.notes || '').trim(),
  };
}

/** True when the entry's required key is present (local always available). */
export function isEntryAvailable(
  entry: FreeModelEntry,
  env: NodeJS.ProcessEnv = process.env,
): boolean {
  if (!entry.envKey) return true;
  // Prefer provider-aware lookup so aliases like HUGGINGFACE_API_KEY → HF_TOKEN work.
  const provider = getProvider(entry.provider);
  if (provider) {
    if (provider.local) return true;
    return providerApiKey(provider, env) !== undefined;
  }
  const value = env[entry.envKey];
  return Boolean(value && value.trim());
}

export function isLocalEntry(entry: FreeModelEntry): boolean {
  return (
    LOCAL_TIERS.has(entry.tier.toLowerCase()) ||
    LOCAL_PROVIDERS.has(entry.provider.toLowerCase())
  );
}

/** Curated catalog of free/cheap model presets. */
export class FreeLLMCatalog {
  constructor(private readonly _entries: FreeModelEntry[]) {}

  static load(registry?: ModelRegistry): FreeLLMCatalog {
    const reg = registry ?? ModelRegistry.load();
    const entries: FreeModelEntry[] = [];
    for (const row of reg.freeCatalogEntries()) {
      const entry = freeModelEntryFromCatalog(row);
      if (entry) entries.push(entry);
    }
    return new FreeLLMCatalog(entries);
  }

  get entries(): FreeModelEntry[] {
    return [...this._entries];
  }

  get length(): number {
    return this._entries.length;
  }

  get(name: string): FreeModelEntry | undefined {
    const needle = (name ?? '').trim().toLowerCase();
    if (!needle) return undefined;
    return this._entries.find(
      (e) => e.id.toLowerCase() === needle || e.config.toLowerCase() === needle,
    );
  }

  /** Entries whose API key (if any) is set and whose registry entry exists. */
  available(
    env: NodeJS.ProcessEnv = process.env,
    registry?: ModelRegistry,
  ): FreeModelEntry[] {
    const reg = registry ?? ModelRegistry.load();
    return this._entries.filter(
      (entry) => reg.hasModel(entry.config) && isEntryAvailable(entry, env),
    );
  }

  /** First available free config; optional preferred order by id/config. */
  pickDefault(
    env: NodeJS.ProcessEnv = process.env,
    registry?: ModelRegistry,
    preferred?: readonly string[],
  ): string | undefined {
    const available = this.available(env, registry);
    if (available.length === 0) return undefined;
    if (preferred) {
      const byKey = new Map<string, string>();
      for (const entry of available) {
        byKey.set(entry.id.toLowerCase(), entry.config);
        byKey.set(entry.config.toLowerCase(), entry.config);
      }
      for (const name of preferred) {
        const hit = byKey.get(name.trim().toLowerCase());
        if (hit) return hit;
      }
    }
    return available[0].config;
  }
}

// ── Failure classification (mirrors the Python markers) ────────────────

const FREE_ROUTING_FAILURE_MARKERS = [
  '502',
  '503',
  'invalid url',
  'provider_name',
  'stealth',
  'provider returned error',
  'no endpoints found',
  'support tool use',
  'supports tool use',
  'does not support tool',
  'does not support tools',
  'tools are not supported',
  'tool use is not supported',
  'tool calling is not supported',
  'function calling is not supported',
  'temporarily unavailable',
  'overloaded',
  'all providers failed',
  'model is currently overloaded',
  'not a valid model id',
  'invalid model',
  'model_not_found',
  'no healthy upstream',
  'bad gateway',
  'deprecated',
  'notfounderror',
  '404',
  'no longer available',
  // Rate limits: retry same model briefly, then fall through.
  '429',
  'rate_limit',
  'rate limit',
  'ratelimit',
  'rate_limit_exceeded',
  'too many requests',
  'tokens per minute',
  'tpm',
  // Context window overflows — switch to a model with more room / free fallback
  'context_length_exceeded',
  'context length',
  'context window',
  'maximum context',
  'max context',
  'too many tokens',
  'prompt is too long',
  'please reduce the length of the messages',
  'reduce the length of the messages or completion',
];

const RATE_LIMIT_MARKERS = [
  '429',
  'rate_limit',
  'rate limit',
  'ratelimit',
  'rate_limit_exceeded',
  'too many requests',
  'tokens per minute',
  'provider returned error',
  'context_length_exceeded',
  'please reduce the length of the messages',
];

const FATAL_MARKERS = [
  'invalid api key',
  'incorrect api key',
  'authentication',
  'unauthorized',
  '401',
  '403',
  'credits',
  'billing',
  'payment required',
  '402',
  'not found in environment',
  'not found in .env',
];

function errorText(error: unknown): string {
  if (error instanceof Error) return `${error.name}: ${error.message}`;
  return String(error ?? '');
}

/** True when the error is specifically a 429 / rate limit (retryable). */
export function isRateLimitFailure(error: unknown): boolean {
  const text = errorText(error).toLowerCase();
  if (!text) return false;
  return RATE_LIMIT_MARKERS.some((marker) => text.includes(marker));
}

/**
 * True when the error looks like a flaky free-router / upstream provider
 * failure that warrants falling through to the next free model. Auth,
 * billing, and missing-key errors are not routing failures.
 */
export function isFreeRoutingFailure(error: unknown): boolean {
  const text = errorText(error).toLowerCase();
  if (!text) return false;
  if (isRateLimitFailure(error)) return true;
  if (FATAL_MARKERS.some((marker) => text.includes(marker))) return false;
  if (text.includes('quota') && !isRateLimitFailure(error)) return false;
  return FREE_ROUTING_FAILURE_MARKERS.some((marker) => text.includes(marker));
}

/** True when the per-day free quota is used up (e.g. OpenRouter). */
export function isDailyFreeQuotaExhausted(error: unknown): boolean {
  const text = errorText(error).toLowerCase();
  if (!text) return false;
  const markers = [
    'free-models-per-day',
    'free models per day',
    'daily limit',
    'daily free quota',
    'remaining: 0',
    'remaining:0',
    'x-ratelimit-remaining: 0',
    'x-ratelimit-remaining:0',
    'quota exceeded',
    'daily quota',
  ];
  return markers.some((marker) => text.includes(marker));
}

const RETRY_AFTER_PATTERNS = [
  /try again in\s+(\d+(?:\.\d+)?)\s*s/i,
  /retry[_-]after[:\s]+(\d+(?:\.\d+)?)/i,
  /retry_after_seconds[:\s=]+(\d+(?:\.\d+)?)/i,
  /please retry in\s+(\d+(?:\.\d+)?)\s*s/i,
  /wait\s+(\d+(?:\.\d+)?)\s*s(?:ec(?:ond)?s?)?/i,
];

/** Cap on a single rate-limit "try again in Ns" hint, in seconds. */
export const DEFAULT_RETRY_AFTER_CAP_SECONDS = 60;

/**
 * Extracts a sleep duration from rate-limit messages like
 * "try again in 2.5s". Returns seconds capped at `cap`, or undefined.
 */
export function parseRetryAfterSeconds(
  errorOrText: unknown,
  cap: number = DEFAULT_RETRY_AFTER_CAP_SECONDS,
): number | undefined {
  const text = errorText(errorOrText);
  if (!text) return undefined;
  let best: number | undefined;
  for (const pattern of RETRY_AFTER_PATTERNS) {
    const match = pattern.exec(text);
    if (match) {
      const seconds = Number(match[1]);
      if (Number.isFinite(seconds) && seconds >= 0) {
        if (best === undefined || seconds > best) best = seconds;
      }
    }
  }
  if (best === undefined) return undefined;
  return cap > 0 ? Math.min(best, cap) : best;
}

/** Raised when the primary free model and all catalog fallbacks fail. */
export class FreeModelsExhaustedError extends Error {
  constructor(
    message: string,
    readonly tried: string[] = [],
    readonly lastError?: unknown,
  ) {
    super(message);
    this.name = 'FreeModelsExhaustedError';
  }
}

/** User-facing message when every free model attempt failed. */
export function formatFreeModelsExhaustedMessage(
  tried: readonly string[],
  lastError?: unknown,
): string {
  const triedList = tried.length > 0 ? tried.join(', ') : '(none)';
  let detail = '';
  if (lastError !== undefined) {
    let raw = errorText(lastError).replace(/\n/g, ' ').trim();
    if (raw.length > 180) raw = raw.slice(0, 177) + '...';
    detail = ` Last error: ${raw}`;
  }
  return (
    `All free / cheap models failed after trying: ${triedList}.${detail} ` +
    'Use /pick to choose a model or /byok to add an API key.'
  );
}

/** Matches a LiteLLM model id or config name to a free-catalog entry. */
export function matchCatalogEntry(
  model: string,
  catalog: FreeLLMCatalog,
  registry?: ModelRegistry,
): FreeModelEntry | undefined {
  const needle = (model ?? '').trim().toLowerCase();
  if (!needle) return undefined;
  const direct = catalog.get(model);
  if (direct) return direct;

  const reg = registry ?? ModelRegistry.load();
  for (const entry of catalog.entries) {
    const cfg = reg.getModel(entry.config);
    if (!cfg) continue;
    const litellmId = (cfg.model ?? '').trim().toLowerCase();
    if (!litellmId) continue;
    if (litellmId === needle) return entry;
    if (litellmId.endsWith('/' + needle) || needle.endsWith('/' + litellmId)) {
      return entry;
    }
  }
  return undefined;
}

function toCandidate(
  entry: FreeModelEntry,
  cfg: RegistryModelConfig,
): FallbackCandidate | undefined {
  const model = (cfg.model ?? entry.config).trim();
  if (!model) return undefined;
  return {
    config: entry.config,
    model,
    provider: (cfg.provider ?? entry.provider ?? '').trim(),
    apiBase: cfg.api_base ? String(cfg.api_base).trim() : undefined,
    temperature: typeof cfg.temperature === 'number' ? cfg.temperature : 0.1,
    maxTokens: typeof cfg.max_tokens === 'number' ? cfg.max_tokens : 4096,
  };
}

/**
 * Ordered alternate free models to try after `currentModel` fails.
 *
 * When the failing model routes through OpenRouter, jump to Groq /
 * Gemini / HF next (OpenRouter free-tier failures usually affect the
 * whole OR free pool). Otherwise prefer same-provider siblings first.
 * Local entries (Ollama / LM Studio) are always ordered last so they
 * act as the final fallback of the chain.
 */
export function freeFallbackCandidates(
  currentModel: string,
  options: {
    catalog?: FreeLLMCatalog;
    registry?: ModelRegistry;
    env?: NodeJS.ProcessEnv;
  } = {},
): FallbackCandidate[] {
  const registry = options.registry ?? ModelRegistry.load();
  const catalog = options.catalog ?? FreeLLMCatalog.load(registry);
  const env = options.env ?? process.env;

  const current = (currentModel ?? '').trim();
  const currentKey = current.toLowerCase();
  const matched = matchCatalogEntry(current, catalog, registry);

  const available = catalog.available(env, registry);
  if (available.length === 0) return [];

  let preferProvider = (matched?.provider ?? '').trim().toLowerCase();
  if (!preferProvider && currentKey.includes('openrouter')) {
    preferProvider = 'openrouter';
  }

  const remote = available.filter((e) => !isLocalEntry(e));
  const local = available.filter((e) => isLocalEntry(e));

  let buckets: FreeModelEntry[][];
  if (preferProvider === 'openrouter') {
    // Jump to Groq/Gemini/etc. before burning sibling OpenRouter slots.
    buckets = [
      remote.filter((e) => e.provider.toLowerCase() !== 'openrouter'),
      remote.filter((e) => e.provider.toLowerCase() === 'openrouter'),
    ];
  } else {
    buckets = [
      preferProvider
        ? remote.filter((e) => e.provider.toLowerCase() === preferProvider)
        : [],
      remote.filter(
        (e) => !preferProvider || e.provider.toLowerCase() !== preferProvider,
      ),
    ];
  }
  // Local models close out the chain as the final fallback.
  buckets.push(local);

  const ordered: FreeModelEntry[] = [];
  const seen = new Set<string>();
  for (const bucket of buckets) {
    for (const entry of bucket) {
      if (seen.has(entry.config)) continue;
      seen.add(entry.config);
      ordered.push(entry);
    }
  }

  const candidates: FallbackCandidate[] = [];
  for (const entry of ordered) {
    if (matched && entry.config === matched.config) continue;
    const cfg = registry.getModel(entry.config);
    if (!cfg) continue;
    const candidate = toCandidate(entry, cfg);
    if (!candidate) continue;
    if (
      candidate.model.toLowerCase() === currentKey ||
      entry.config.toLowerCase() === currentKey
    ) {
      continue;
    }
    candidates.push(candidate);
  }
  return candidates;
}

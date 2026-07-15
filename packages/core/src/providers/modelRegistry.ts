/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Single-file TOML model registry (`configs/models.toml`).
 *
 * TypeScript port of `libs/core/model_registry.py` from the original
 * Python code-interpreter project. All model metadata plus the curated
 * free/cheap catalog live in one human-editable file; users add their
 * own models/providers by editing that file — no code changes required.
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import TOML from '@iarna/toml';

/** Default location of the single-file model registry. */
export const DEFAULT_REGISTRY_PATH = path.join('configs', 'models.toml');

/** Hard fallback when nothing else resolves (kept in sync with models.toml). */
export const FALLBACK_DEFAULT_MODEL = 'gpt-4o';

export interface RegistryModelConfig {
  /** LiteLLM-style model id, e.g. "gemini/gemini-2.5-flash". */
  model: string;
  provider?: string;
  api_base?: string;
  temperature?: number;
  max_tokens?: number;
  tier?: string;
  notes?: string;
  timeout_seconds?: number;
  [key: string]: unknown;
}

export interface FreeCatalogEntry {
  id: string;
  model_key: string;
  provider: string;
  env_key: string;
  tier: string;
  notes: string;
}

export interface DefaultPriorityEntry {
  env: string;
  model: string;
}

interface RegistryData {
  schema_version?: number;
  default_model?: string;
  models?: Record<string, RegistryModelConfig>;
  free_catalog?: FreeCatalogEntry[];
  default_priority?: DefaultPriorityEntry[];
}

function resolveRegistryPath(registryPath?: string): string {
  const candidate = registryPath || DEFAULT_REGISTRY_PATH;
  try {
    if (fs.statSync(candidate).isDirectory()) {
      return path.join(candidate, 'models.toml');
    }
  } catch {
    // Fall through: treat as a (possibly missing) file path.
  }
  return candidate;
}

/** Parsed view of a `models.toml` registry file. */
export class ModelRegistry {
  private readonly models: Record<string, RegistryModelConfig>;
  private readonly freeCatalog: FreeCatalogEntry[];
  private readonly defaultPriority: DefaultPriorityEntry[];
  private readonly defaultModel: string;

  constructor(
    readonly path: string,
    data: RegistryData,
  ) {
    this.models = { ...(data.models ?? {}) };
    this.freeCatalog = [...(data.free_catalog ?? [])];
    this.defaultPriority = [...(data.default_priority ?? [])];
    this.defaultModel = String(data.default_model || FALLBACK_DEFAULT_MODEL);
  }

  /**
   * Loads the registry at `registryPath` (a `.toml` file or a directory
   * containing `models.toml`). Missing or invalid registries yield an
   * empty registry rather than throwing.
   */
  static load(registryPath?: string): ModelRegistry {
    const resolved = resolveRegistryPath(registryPath);
    let data: RegistryData = {};
    try {
      const raw = fs.readFileSync(resolved, 'utf8');
      // eslint-disable-next-line @typescript-eslint/no-unsafe-type-assertion
      data = TOML.parse(raw) as unknown as RegistryData;
    } catch {
      // Missing or malformed file: empty registry.
    }
    return new ModelRegistry(resolved, data);
  }

  hasModel(name: string): boolean {
    return Boolean(name) && name in this.models;
  }

  getModel(name: string): RegistryModelConfig | undefined {
    const entry = this.models[name];
    return entry ? { ...entry } : undefined;
  }

  listModelNames(): string[] {
    return Object.keys(this.models).sort();
  }

  /**
   * First `[[default_priority]]` row whose env var is set wins; falls
   * back to the registry's `default_model`.
   */
  defaultModelName(env: NodeJS.ProcessEnv = process.env): string {
    for (const row of this.defaultPriority) {
      const envName = (row.env ?? '').trim();
      const modelName = (row.model ?? '').trim();
      if (envName && modelName && env[envName]) {
        return modelName;
      }
    }
    return this.defaultModel;
  }

  /** Ordered list of curated free/cheap presets. */
  freeCatalogEntries(): FreeCatalogEntry[] {
    return this.freeCatalog.map((row) => ({ ...row }));
  }

  /**
   * Maps a user-facing model token to a `[models.<name>]` registry key:
   * a registry key itself, a free-catalog id, or a LiteLLM model id that
   * uniquely matches one registry entry.
   */
  resolveModelKey(name: string): string | undefined {
    const needle = (name ?? '').trim();
    if (!needle) return undefined;
    if (this.hasModel(needle)) return needle;

    const lower = needle.toLowerCase();
    for (const entry of this.freeCatalog) {
      if (
        (entry.id ?? '').toLowerCase() === lower &&
        this.hasModel(entry.model_key)
      ) {
        return entry.model_key;
      }
    }

    const matches = this.listModelNames().filter(
      (key) => (this.models[key]?.model ?? '').toLowerCase() === lower,
    );
    return matches.length === 1 ? matches[0] : undefined;
  }
}

let cached: { path: string; mtimeMs: number; registry: ModelRegistry } | null =
  null;

/** Cached accessor; reloads when the file's mtime changes. */
export function getModelRegistry(registryPath?: string): ModelRegistry {
  const resolved = resolveRegistryPath(registryPath);
  let mtimeMs = -1;
  try {
    mtimeMs = fs.statSync(resolved).mtimeMs;
  } catch {
    // Missing file: cache the empty registry under mtime -1.
  }
  if (cached && cached.path === resolved && cached.mtimeMs === mtimeMs) {
    return cached.registry;
  }
  const registry = ModelRegistry.load(resolved);
  cached = { path: resolved, mtimeMs, registry };
  return registry;
}

/** Test hook: clears the module-level registry cache. */
export function clearModelRegistryCache(): void {
  cached = null;
}

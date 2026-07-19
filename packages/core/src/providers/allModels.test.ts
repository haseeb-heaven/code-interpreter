/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Registry-wide checks over the real `configs/models.toml`: every single
 * model entry must parse, resolve, and route (the TypeScript analog of
 * the original project's `tests/test_all_model_configs.py`).
 */

import { describe, it, expect } from 'vitest';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { ModelRegistry } from './modelRegistry.js';
import {
  FreeLLMCatalog,
  isEntryAvailable,
  isLocalEntry,
} from './freeCatalog.js';
import { createMultiProviderGenerator } from './factory.js';
import { groupModelsByProvider } from './picker.js';
import { getProvider, splitModelId } from './providers.js';

const REPO_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../../../..',
);
const REGISTRY_PATH = path.join(REPO_ROOT, 'configs', 'models.toml');

const registry = ModelRegistry.load(REGISTRY_PATH);
const catalog = FreeLLMCatalog.load(registry);
const modelNames = registry.listModelNames();

const ALL_KEYS: NodeJS.ProcessEnv = {
  OPENAI_API_KEY: 'x',
  ANTHROPIC_API_KEY: 'x',
  GEMINI_API_KEY: 'x',
  GROQ_API_KEY: 'x',
  DEEPSEEK_API_KEY: 'x',
  NVIDIA_API_KEY: 'x',
  TOGETHER_API_KEY: 'x',
  HF_TOKEN: 'x',
  HUGGINGFACE_API_KEY: 'x',
  OPENROUTER_API_KEY: 'x',
  CEREBRAS_API_KEY: 'x',
  Z_AI_API_KEY: 'x',
  BROWSER_USE_API_KEY: 'x',
};

describe('configs/models.toml (real registry)', () => {
  it('loads the full catalog from the repository', () => {
    expect(modelNames.length).toBeGreaterThanOrEqual(76);
    expect(catalog.length).toBeGreaterThanOrEqual(19);
  });

  it.each(modelNames)('[models."%s"] is complete and well-formed', (name) => {
    const cfg = registry.getModel(name)!;
    expect(cfg.model, `${name} must set a litellm-style model id`).toBeTruthy();
    if (cfg.temperature !== undefined) {
      expect(cfg.temperature).toBeGreaterThanOrEqual(0);
      expect(cfg.temperature).toBeLessThanOrEqual(2);
    }
    if (cfg.max_tokens !== undefined) {
      expect(cfg.max_tokens).toBeGreaterThan(0);
    }
    if (cfg.api_base !== undefined) {
      expect(() => new URL(String(cfg.api_base))).not.toThrow();
    }
    if (cfg.tier !== undefined) {
      expect(['paid', 'free', 'free_tier', 'local']).toContain(cfg.tier);
    }
    // The registry key must round-trip through resolveModelKey.
    expect(registry.resolveModelKey(name)).toBe(name);
  });

  it.each(modelNames)('"%s" routes to a known provider', (name) => {
    const cfg = registry.getModel(name)!;
    const modelId = cfg.model;
    const prefixed = splitModelId(modelId).provider;
    const declared = cfg.provider ? getProvider(cfg.provider) : undefined;
    const local = cfg.provider === 'local';
    const hasApiBase = Boolean(cfg.api_base);
    // Every entry must be routable: a known provider prefix, an explicit
    // provider tag, a custom api_base, or a bare id (OpenAI-compatible
    // default, e.g. gpt-4o / claude-sonnet / deepseek-chat / bu-max).
    const routable =
      Boolean(prefixed) ||
      Boolean(declared) ||
      local ||
      hasApiBase ||
      !modelId.includes('/');
    expect(routable, `${name} (${modelId}) must be routable`).toBe(true);
  });

  it.each(catalog.entries.map((e) => e.id))(
    'free catalog id "%s" references a real model entry',
    (id) => {
      const entry = catalog.get(id)!;
      expect(registry.hasModel(entry.config)).toBe(true);
      // env_key must be empty exactly for local entries.
      if (isLocalEntry(entry)) {
        expect(entry.envKey).toBeNull();
        expect(isEntryAvailable(entry, {})).toBe(true);
      } else {
        expect(entry.envKey).toBeTruthy();
        expect(isEntryAvailable(entry, {})).toBe(false);
        expect(isEntryAvailable(entry, ALL_KEYS)).toBe(true);
      }
    },
  );

  it('every default_priority row points at an existing model', () => {
    // Exercise each row by giving it exactly its own env key.
    const rows: Array<[string, string]> = [
      ['OPENAI_API_KEY', 'gpt-4o'],
      ['OPENROUTER_API_KEY', 'openrouter-free'],
      ['GEMINI_API_KEY', 'gemini-2.5-flash'],
      ['ANTHROPIC_API_KEY', 'claude-sonnet-4-6'],
      ['GROQ_API_KEY', 'groq-gpt-oss-20b'],
      ['CEREBRAS_API_KEY', 'cerebras-gpt-oss-120b'],
      ['Z_AI_API_KEY', 'z-ai-glm-5'],
      ['NVIDIA_API_KEY', 'nvidia-nemotron'],
      ['DEEPSEEK_API_KEY', 'deepseek-chat'],
      ['HUGGINGFACE_API_KEY', 'hf-meta-llama-3'],
      ['BROWSER_USE_API_KEY', 'browser-use-bu-max'],
    ];
    for (const [env, expected] of rows) {
      expect(registry.defaultModelName({ [env]: 'x' })).toBe(expected);
      expect(registry.hasModel(expected)).toBe(true);
    }
    // Zero API keys configured -> the local, no-key-required route, not a
    // paid cloud model (picking "Free / open-source / local models" with no
    // keys set must not require gpt-4o's OPENAI_API_KEY).
    expect(registry.defaultModelName({})).toBe('local-model');
    expect(registry.hasModel('local-model')).toBe(true);
  });

  it.each(
    modelNames.filter((name) => {
      const cfg = registry.getModel(name)!;
      const provider = splitModelId(cfg.model).provider;
      return Boolean(provider) && provider!.id !== 'gemini';
    }),
  )('"%s" builds a working multi-provider generator', (name) => {
    const generator = createMultiProviderGenerator(name, ALL_KEYS, registry);
    expect(generator, `${name} must produce a generator`).toBeDefined();
    expect(generator!.apiBase).toMatch(/^https?:\/\//);
    expect(generator!.model.length).toBeGreaterThan(0);
  });

  it.each(
    modelNames.filter((name) => {
      const cfg = registry.getModel(name)!;
      return splitModelId(cfg.model).provider?.id === 'gemini';
    }),
  )(
    '"%s" stays on the native Gemini path (no multi-provider generator)',
    (name) => {
      // Regression test: createMultiProviderGenerator must stay in sync
      // with isMultiProviderModel and never build an OpenAI-compat shim
      // for a gemini model - that shim doesn't reproduce native Gemini
      // behavior (thought signatures, grounding metadata, Vertex headers).
      const generator = createMultiProviderGenerator(name, ALL_KEYS, registry);
      expect(
        generator,
        `${name} must NOT produce a multi-provider generator`,
      ).toBeUndefined();
    },
  );

  it('throws a clear, actionable error when the provider API key is missing', () => {
    expect(() =>
      createMultiProviderGenerator('cerebras-gpt-oss-120b', {}, registry),
    ).toThrow(/CEREBRAS_API_KEY/);
    expect(() =>
      createMultiProviderGenerator('groq/llama-3.1-8b-instant', {}, registry),
    ).toThrow(/GROQ_API_KEY/);
  });

  it('honors the OPENAGENT_MODELS_TOML env override when loading', () => {
    const prev = process.env['OPENAGENT_MODELS_TOML'];
    process.env['OPENAGENT_MODELS_TOML'] = REGISTRY_PATH;
    try {
      const fromEnv = ModelRegistry.load();
      expect(fromEnv.hasModel('cerebras-gpt-oss-120b')).toBe(true);
    } finally {
      if (prev === undefined) delete process.env['OPENAGENT_MODELS_TOML'];
      else process.env['OPENAGENT_MODELS_TOML'] = prev;
    }
  });

  it('resolves the shipped registry even from a foreign working directory', () => {
    const prevCwd = process.cwd();
    process.chdir(path.dirname(REPO_ROOT));
    try {
      const found = ModelRegistry.load();
      expect(found.hasModel('cerebras-gpt-oss-120b')).toBe(true);
    } finally {
      process.chdir(prevCwd);
    }
  });

  it('the picker surfaces every provider present in the registry', () => {
    const groups = groupModelsByProvider({ registry, env: ALL_KEYS });
    const ids = groups.map((g) => g.provider.id);
    for (const expected of [
      'ollama',
      'lmstudio',
      'openai',
      'anthropic',
      'gemini',
      'groq',
      'deepseek',
      'nvidia',
      'huggingface',
      'openrouter',
      'cerebras',
      'z-ai',
    ]) {
      expect(ids, `picker must include ${expected}`).toContain(expected);
    }
    const totalShown = groups.reduce((n, g) => n + g.models.length, 0);
    expect(totalShown).toBeGreaterThanOrEqual(70);
  });
});

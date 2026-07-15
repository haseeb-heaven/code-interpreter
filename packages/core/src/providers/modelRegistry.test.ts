/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fs from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import {
  ModelRegistry,
  clearModelRegistryCache,
  getModelRegistry,
} from './modelRegistry.js';

const SAMPLE = `
schema_version = 1
default_model = "gpt-4o"

[[default_priority]]
env = "OPENAI_API_KEY"
model = "gpt-4o"

[[default_priority]]
env = "GROQ_API_KEY"
model = "groq-llama-3.1-8b"

[models."gpt-4o"]
model = "gpt-4o"
temperature = 0.1
max_tokens = 4096
tier = "paid"

[models."groq-llama-3.1-8b"]
model = "groq/llama-3.1-8b-instant"
tier = "free_tier"
notes = "Groq Llama 3.1 8B Instant (generous free tier)"

[[free_catalog]]
id = "groq-llama-3.1-8b"
model_key = "groq-llama-3.1-8b"
provider = "groq"
env_key = "GROQ_API_KEY"
tier = "free_tier"
notes = "Groq Llama 3.1 8B Instant (generous free tier)"
`;

describe('ModelRegistry', () => {
  let dir: string;

  beforeEach(() => {
    dir = fs.mkdtempSync(path.join(os.tmpdir(), 'registry-test-'));
    fs.mkdirSync(path.join(dir, 'configs'));
    fs.writeFileSync(path.join(dir, 'configs', 'models.toml'), SAMPLE);
    clearModelRegistryCache();
  });

  afterEach(() => {
    fs.rmSync(dir, { recursive: true, force: true });
  });

  it('loads models from a .toml file or a directory containing it', () => {
    const byFile = ModelRegistry.load(path.join(dir, 'configs', 'models.toml'));
    const byDir = ModelRegistry.load(path.join(dir, 'configs'));
    for (const registry of [byFile, byDir]) {
      expect(registry.hasModel('gpt-4o')).toBe(true);
      expect(registry.getModel('groq-llama-3.1-8b')?.model).toBe(
        'groq/llama-3.1-8b-instant',
      );
      expect(registry.listModelNames()).toEqual([
        'gpt-4o',
        'groq-llama-3.1-8b',
      ]);
    }
  });

  it('returns an empty registry for missing files', () => {
    const registry = ModelRegistry.load(path.join(dir, 'nope.toml'));
    expect(registry.listModelNames()).toEqual([]);
    expect(registry.hasModel('gpt-4o')).toBe(false);
  });

  it('resolves the default model via [[default_priority]]', () => {
    const registry = ModelRegistry.load(path.join(dir, 'configs'));
    expect(registry.defaultModelName({})).toBe('gpt-4o');
    expect(registry.defaultModelName({ GROQ_API_KEY: 'x' })).toBe(
      'groq-llama-3.1-8b',
    );
    expect(
      registry.defaultModelName({ OPENAI_API_KEY: 'a', GROQ_API_KEY: 'b' }),
    ).toBe('gpt-4o');
  });

  it('exposes free catalog entries as plain rows', () => {
    const registry = ModelRegistry.load(path.join(dir, 'configs'));
    const rows = registry.freeCatalogEntries();
    expect(rows).toHaveLength(1);
    expect(rows[0].model_key).toBe('groq-llama-3.1-8b');
    expect(rows[0].env_key).toBe('GROQ_API_KEY');
  });

  it('resolveModelKey accepts keys, catalog ids, and unique litellm ids', () => {
    const registry = ModelRegistry.load(path.join(dir, 'configs'));
    expect(registry.resolveModelKey('gpt-4o')).toBe('gpt-4o');
    expect(registry.resolveModelKey('groq/llama-3.1-8b-instant')).toBe(
      'groq-llama-3.1-8b',
    );
    expect(registry.resolveModelKey('unknown')).toBeUndefined();
  });

  it('getModelRegistry caches per path until the file changes', () => {
    const configsDir = path.join(dir, 'configs');
    const first = getModelRegistry(configsDir);
    expect(getModelRegistry(configsDir)).toBe(first);
    clearModelRegistryCache();
    expect(getModelRegistry(configsDir)).not.toBe(first);
  });
});

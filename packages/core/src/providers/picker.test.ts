/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect } from 'vitest';
import { ModelRegistry } from './modelRegistry.js';
import {
  formatPickerGroups,
  groupModelsByProvider,
  modelSupportsVision,
} from './picker.js';
import { getProvider } from './providers.js';

const REGISTRY = new ModelRegistry('test://models.toml', {
  default_model: 'gpt-4o',
  models: {
    'gpt-4o': { model: 'gpt-4o', temperature: 0.1, max_tokens: 4096 },
    'groq-llama-3.1-8b': {
      model: 'groq/llama-3.1-8b-instant',
      tier: 'free_tier',
    },
    'gemini-2.5-flash': {
      model: 'gemini/gemini-2.5-flash',
      tier: 'free_tier',
    },
    'local-model': {
      model: 'llama3.1:8b',
      provider: 'local',
      api_base: 'http://localhost:11434/v1',
      tier: 'local',
    },
  },
  free_catalog: [],
  default_priority: [],
});

describe('groupModelsByProvider', () => {
  it('groups registry models by provider in declaration order', () => {
    const groups = groupModelsByProvider({
      registry: REGISTRY,
      env: { OPENAI_API_KEY: 'sk-test', GROQ_API_KEY: 'gsk-test' },
      detectedLocalModels: {},
    });
    const ids = groups.map((g) => g.provider.id);
    expect(ids).toEqual(['ollama', 'openai', 'gemini', 'groq']);
    // Local providers list before every cloud provider.
    expect(ids.indexOf('ollama')).toBeLessThan(ids.indexOf('openai'));
  });

  it('marks API key availability per provider', () => {
    const groups = groupModelsByProvider({
      registry: REGISTRY,
      env: { GROQ_API_KEY: 'gsk-test' },
      detectedLocalModels: {},
    });
    const byId = new Map(groups.map((g) => [g.provider.id, g]));
    expect(byId.get('groq')?.models[0]?.available).toBe(true);
    expect(byId.get('openai')?.models[0]?.available).toBe(false);
    expect(byId.get('gemini')?.models[0]?.available).toBe(false);
  });

  it('always shows detected local models as available', () => {
    const groups = groupModelsByProvider({
      registry: REGISTRY,
      env: {},
      detectedLocalModels: {
        ollama: ['llama3.1:8b', 'codellama:7b'],
        lmstudio: ['qwen2.5-coder-7b-instruct'],
      },
    });
    const byId = new Map(groups.map((g) => [g.provider.id, g]));
    const ollama = byId.get('ollama');
    expect(ollama?.models.map((m) => m.key)).toEqual([
      'ollama/codellama:7b',
      'ollama/llama3.1:8b',
    ]);
    expect(ollama?.models.every((m) => m.available)).toBe(true);
    expect(byId.get('lmstudio')?.models[0]?.available).toBe(true);
  });

  it('marks vision and streaming support per model', () => {
    const groups = groupModelsByProvider({
      registry: REGISTRY,
      env: { OPENAI_API_KEY: 'x', GROQ_API_KEY: 'y' },
      detectedLocalModels: {},
    });
    const byId = new Map(groups.map((g) => [g.provider.id, g]));
    const gpt4o = byId.get('openai')?.models.find((m) => m.key === 'gpt-4o');
    expect(gpt4o?.vision).toBe(true);
    expect(gpt4o?.streaming).toBe(true);
    // Groq is text-only today.
    expect(byId.get('groq')?.models[0]?.vision).toBe(false);
    expect(byId.get('groq')?.models[0]?.streaming).toBe(true);
  });
});

describe('modelSupportsVision', () => {
  it('gates on the provider first', () => {
    expect(modelSupportsVision(getProvider('groq'), 'gpt-4o')).toBe(false);
  });

  it('matches known multimodal model families', () => {
    expect(modelSupportsVision(getProvider('openai'), 'gpt-4o')).toBe(true);
    expect(modelSupportsVision(getProvider('ollama'), 'llava:13b')).toBe(true);
    expect(modelSupportsVision(getProvider('deepseek'), 'deepseek-chat')).toBe(
      false,
    );
  });
});

describe('formatPickerGroups', () => {
  it('renders availability and capability markers', () => {
    const text = formatPickerGroups(
      groupModelsByProvider({
        registry: REGISTRY,
        env: { OPENAI_API_KEY: 'x' },
        detectedLocalModels: { ollama: ['llama3.1:8b'] },
      }),
    );
    expect(text).toContain('Ollama (local)');
    expect(text).toContain('✓ ollama/llama3.1:8b');
    expect(text).toContain('✓ gpt-4o');
    expect(text).toContain('✗ gemini-2.5-flash');
  });

  it('explains what to do when no models exist', () => {
    expect(formatPickerGroups([])).toContain('No models found');
  });
});

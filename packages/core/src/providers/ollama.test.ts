/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  isOllamaRunning,
  listOllamaModels,
  litellmOllamaId,
  pickBestOllamaModel,
  resolveOllamaModel,
  OllamaError,
} from './ollama.js';

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('pickBestOllamaModel', () => {
  it('prefers codellama over other installed models', () => {
    expect(
      pickBestOllamaModel(['mistral:latest', 'codellama:7b', 'llama3']),
    ).toBe('codellama:7b');
  });

  it('falls back to the first installed model', () => {
    expect(pickBestOllamaModel(['custom-model'])).toBe('custom-model');
  });

  it('returns undefined when nothing is installed', () => {
    expect(pickBestOllamaModel([])).toBeUndefined();
  });
});

describe('litellmOllamaId', () => {
  it('prefixes bare model names', () => {
    expect(litellmOllamaId('llama3')).toBe('ollama/llama3');
  });

  it('keeps already-prefixed ids unchanged', () => {
    expect(litellmOllamaId('ollama/llama3')).toBe('ollama/llama3');
  });
});

describe('Ollama detection', () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    vi.stubGlobal('fetch', mockFetch);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetAllMocks();
  });

  it('isOllamaRunning returns true when /api/tags answers 200', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ models: [] }));
    await expect(isOllamaRunning()).resolves.toBe(true);
    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:11434/api/tags',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it('isOllamaRunning returns false when the server is down', async () => {
    mockFetch.mockRejectedValueOnce(new Error('ECONNREFUSED'));
    await expect(isOllamaRunning()).resolves.toBe(false);
  });

  it('isOllamaRunning returns false on non-2xx responses', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({}, 500));
    await expect(isOllamaRunning()).resolves.toBe(false);
  });

  it('listOllamaModels reads names from the /api/tags payload', async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        models: [
          { name: 'llama3.1:8b' },
          { model: 'mistral:latest' },
          'qwen2.5',
        ],
      }),
    );
    await expect(listOllamaModels()).resolves.toEqual([
      'llama3.1:8b',
      'mistral:latest',
      'qwen2.5',
    ]);
  });

  it('listOllamaModels returns an empty list on errors', async () => {
    mockFetch.mockRejectedValueOnce(new Error('boom'));
    await expect(listOllamaModels()).resolves.toEqual([]);
  });

  it('resolveOllamaModel picks the best installed model by default', async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({
        models: [{ name: 'mistral:latest' }, { name: 'llama3.1:8b' }],
      }),
    );
    await expect(resolveOllamaModel()).resolves.toBe('llama3.1:8b');
  });

  it('resolveOllamaModel matches a requested base name', async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ models: [{ name: 'llama3.1:8b' }] }),
    );
    await expect(resolveOllamaModel('ollama/llama3.1')).resolves.toBe(
      'llama3.1:8b',
    );
  });

  it('resolveOllamaModel throws OllamaError when the server is down', async () => {
    mockFetch.mockRejectedValue(new Error('ECONNREFUSED'));
    await expect(resolveOllamaModel()).rejects.toBeInstanceOf(OllamaError);
  });

  it('resolveOllamaModel throws when the requested model is missing', async () => {
    mockFetch.mockResolvedValue(
      jsonResponse({ models: [{ name: 'llama3.1:8b' }] }),
    );
    await expect(resolveOllamaModel('nope')).rejects.toThrow(/not installed/);
  });
});

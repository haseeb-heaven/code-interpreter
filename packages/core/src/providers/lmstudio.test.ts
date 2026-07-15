/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  isLMStudioRunning,
  listLMStudioModels,
  litellmLMStudioId,
} from './lmstudio.js';

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('LM Studio connection checking', () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    vi.stubGlobal('fetch', mockFetch);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetAllMocks();
  });

  it('isLMStudioRunning probes the OpenAI-compatible /v1/models endpoint', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ data: [] }));
    await expect(isLMStudioRunning()).resolves.toBe(true);
    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:1234/v1/models',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it('isLMStudioRunning returns false when the server is down', async () => {
    mockFetch.mockRejectedValueOnce(new Error('ECONNREFUSED'));
    await expect(isLMStudioRunning()).resolves.toBe(false);
  });

  it('isLMStudioRunning returns false on non-2xx responses', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({}, 503));
    await expect(isLMStudioRunning()).resolves.toBe(false);
  });

  it('listLMStudioModels reads ids from the /v1/models payload', async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        data: [{ id: 'qwen2.5-coder-7b-instruct' }, { id: 'llama-3.2-3b' }],
      }),
    );
    await expect(listLMStudioModels()).resolves.toEqual([
      'qwen2.5-coder-7b-instruct',
      'llama-3.2-3b',
    ]);
  });

  it('listLMStudioModels returns an empty list on errors', async () => {
    mockFetch.mockRejectedValueOnce(new Error('boom'));
    await expect(listLMStudioModels()).resolves.toEqual([]);
  });

  it('litellmLMStudioId prefixes bare model names', () => {
    expect(litellmLMStudioId('llama-3.2-3b')).toBe('lmstudio/llama-3.2-3b');
    expect(litellmLMStudioId('lmstudio/x')).toBe('lmstudio/x');
  });
});

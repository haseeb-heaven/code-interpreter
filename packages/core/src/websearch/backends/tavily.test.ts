/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { tavilyBackend } from './tavily.js';

describe('tavilyBackend', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('is unavailable without TAVILY_API_KEY', () => {
    expect(tavilyBackend.isAvailable({})).toBe(false);
  });

  it('parses Tavily results and answer', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          answer: 'Short answer.',
          results: [
            {
              title: 'Tavily Hit',
              url: 'https://example.com/t',
              content: 'snippet text',
            },
          ],
        }),
      })),
    );

    const result = await tavilyBackend.search('agent search', {
      env: { TAVILY_API_KEY: 'tvly-test' },
    });
    expect(result.provider).toBe('tavily');
    expect(result.hits[0].title).toBe('Tavily Hit');
    expect(result.summary).toContain('Short answer');
  });
});

/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { braveBackend } from './brave.js';

describe('braveBackend', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('is unavailable without BRAVE_API_KEY', () => {
    expect(braveBackend.isAvailable({})).toBe(false);
  });

  it('parses Brave web results', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          web: {
            results: [
              {
                title: 'Example Doc',
                url: 'https://example.com/doc',
                description: 'A sample result',
              },
            ],
          },
        }),
      })),
    );

    const result = await braveBackend.search('sample query', {
      env: { BRAVE_API_KEY: 'test-key' },
    });
    expect(result.provider).toBe('brave');
    expect(result.hits).toHaveLength(1);
    expect(result.hits[0].title).toBe('Example Doc');
    expect(result.hits[0].url).toBe('https://example.com/doc');
    expect(result.summary).toContain('Example Doc');
  });

  it('throws when key missing on search', async () => {
    await expect(braveBackend.search('q', { env: {} })).rejects.toThrow(
      /BRAVE_API_KEY/,
    );
  });
});

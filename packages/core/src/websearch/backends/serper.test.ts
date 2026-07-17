/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { serperBackend } from './serper.js';

describe('serperBackend', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('is unavailable without SERPER_API_KEY', () => {
    expect(serperBackend.isAvailable({})).toBe(false);
  });

  it('parses Serper organic results', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          organic: [
            {
              title: 'Serper Result',
              link: 'https://example.com/s',
              snippet: 'google-like',
            },
          ],
        }),
      })),
    );

    const result = await serperBackend.search('serp query', {
      env: { SERPER_API_KEY: 'serper-test' },
    });
    expect(result.provider).toBe('serper');
    expect(result.hits[0].title).toBe('Serper Result');
  });
});

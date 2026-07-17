/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { exaBackend } from './exa.js';

describe('exaBackend', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('is unavailable without EXA_API_KEY', () => {
    expect(exaBackend.isAvailable({})).toBe(false);
  });

  it('parses Exa results', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          results: [
            {
              title: 'Exa Paper',
              url: 'https://example.com/exa',
              text: 'neural snippet',
            },
          ],
        }),
      })),
    );

    const result = await exaBackend.search('neural query', {
      env: { EXA_API_KEY: 'exa-test' },
    });
    expect(result.provider).toBe('exa');
    expect(result.hits[0].url).toBe('https://example.com/exa');
  });
});

/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, expect, it } from 'vitest';
import { duckduckgoBackend } from './duckduckgo.js';

describe('duckduckgoBackend', () => {
  it('is always available without keys', () => {
    expect(duckduckgoBackend.isAvailable({})).toBe(true);
    expect(duckduckgoBackend.meta.freeNoKey).toBe(true);
  });

  it('returns live results for a simple query', async () => {
    const result = await duckduckgoBackend.search('OpenAgent');
    expect(result.hits.length + result.summary.length).toBeGreaterThan(0);
    expect(result.provider).toMatch(/duckduckgo/);
  }, 30000);
});

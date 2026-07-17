/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect } from 'vitest';
import {
  searchDuckDuckGoInstant,
  searchWebFallback,
} from './webSearchProviders.js';

describe('webSearchProviders', () => {
  it('DuckDuckGo Instant Answer returns something for a well-known query', async () => {
    const result = await searchDuckDuckGoInstant('DuckDuckGo');
    // Instant Answer may be thin; at least should not throw and ideally has content
    if (result) {
      expect(result.provider).toBe('duckduckgo-instant');
      expect(result.summary.length > 0 || result.hits.length > 0).toBe(true);
    }
  }, 20000);

  it('searchWebFallback returns hits or summary for a technical query', async () => {
    const result = await searchWebFallback('C++17 features overview');
    expect(result.summary.length).toBeGreaterThan(20);
    expect(result.provider).toMatch(/duckduckgo/);
  }, 30000);
});

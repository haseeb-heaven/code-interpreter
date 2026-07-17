/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fs from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import { recordProviderUsage, getProviderUsage } from './usageStore.js';

describe('usageStore', () => {
  let dir: string;
  let filePath: string;

  beforeEach(() => {
    dir = fs.mkdtempSync(path.join(os.tmpdir(), 'usage-store-test-'));
    filePath = path.join(dir, 'provider-usage.json');
  });

  afterEach(() => {
    fs.rmSync(dir, { recursive: true, force: true });
  });

  it('returns an empty store when no file exists yet', () => {
    expect(getProviderUsage({ filePath })).toEqual({});
  });

  it('accumulates usage across multiple calls for the same provider', () => {
    recordProviderUsage(
      'openrouter',
      { promptTokens: 10, completionTokens: 5, totalTokens: 15 },
      { filePath, now: () => '2026-01-01T00:00:00.000Z' },
    );
    recordProviderUsage(
      'openrouter',
      { promptTokens: 20, completionTokens: 8, totalTokens: 28 },
      { filePath, now: () => '2026-01-02T00:00:00.000Z' },
    );

    const store = getProviderUsage({ filePath });
    expect(store['openrouter']).toEqual({
      promptTokens: 30,
      completionTokens: 13,
      totalTokens: 43,
      requestCount: 2,
      lastUsedAt: '2026-01-02T00:00:00.000Z',
    });
  });

  it('tracks separate providers independently', () => {
    recordProviderUsage(
      'gemini',
      { promptTokens: 1, completionTokens: 1, totalTokens: 2 },
      { filePath, now: () => '2026-01-01T00:00:00.000Z' },
    );
    recordProviderUsage(
      'openai',
      { promptTokens: 4, completionTokens: 2, totalTokens: 6 },
      { filePath, now: () => '2026-01-01T00:00:00.000Z' },
    );

    const store = getProviderUsage({ filePath });
    expect(Object.keys(store).sort()).toEqual(['gemini', 'openai']);
    expect(store['gemini'].totalTokens).toBe(2);
    expect(store['openai'].totalTokens).toBe(6);
  });

  it('persists across separate reads (survives "restart")', () => {
    recordProviderUsage(
      'anthropic',
      { promptTokens: 3, completionTokens: 3, totalTokens: 6 },
      { filePath, now: () => '2026-01-01T00:00:00.000Z' },
    );

    const reread = getProviderUsage({ filePath });
    expect(reread['anthropic'].requestCount).toBe(1);
  });

  it('ignores corrupt store files instead of throwing', () => {
    fs.writeFileSync(filePath, 'not json', 'utf8');
    expect(getProviderUsage({ filePath })).toEqual({});
  });
});

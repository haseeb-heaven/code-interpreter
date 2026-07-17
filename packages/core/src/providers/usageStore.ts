/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Cross-session, per-provider token usage tracking.
 *
 * Every completion response (native Gemini or any OpenAI-compatible
 * provider routed through openaiCompatGenerator.ts) already returns its
 * own `usage`/`usageMetadata` field. LoggingContentGenerator forwards each
 * response's usage here so accumulated totals survive across CLI restarts,
 * independent of any single provider exposing an account-balance API.
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import { Storage } from '../config/storage.js';

export interface ProviderUsageEntry {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  requestCount: number;
  lastUsedAt: string;
}

export type ProviderUsageStore = Record<string, ProviderUsageEntry>;

function isRecord(val: unknown): val is Record<string, unknown> {
  return typeof val === 'object' && val !== null && !Array.isArray(val);
}

function isNumber(val: unknown): val is number {
  return typeof val === 'number';
}

function isString(val: unknown): val is string {
  return typeof val === 'string';
}

function emptyEntry(): ProviderUsageEntry {
  return {
    promptTokens: 0,
    completionTokens: 0,
    totalTokens: 0,
    requestCount: 0,
    lastUsedAt: '',
  };
}

function toEntry(value: unknown): ProviderUsageEntry {
  const record = isRecord(value) ? value : {};
  const num = (key: string) => (isNumber(record[key]) ? record[key] : 0);
  const str = (key: string) => (isString(record[key]) ? record[key] : '');
  return {
    promptTokens: num('promptTokens'),
    completionTokens: num('completionTokens'),
    totalTokens: num('totalTokens'),
    requestCount: num('requestCount'),
    lastUsedAt: str('lastUsedAt'),
  };
}

function readStore(filePath: string): ProviderUsageStore {
  try {
    const raw = fs.readFileSync(filePath, 'utf8');
    const parsed: unknown = JSON.parse(raw);
    if (!isRecord(parsed)) return {};
    const store: ProviderUsageStore = {};
    for (const [providerId, value] of Object.entries(parsed)) {
      store[providerId] = toEntry(value);
    }
    return store;
  } catch {
    return {};
  }
}

function writeStore(filePath: string, store: ProviderUsageStore): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(store, null, 2), 'utf8');
}

export function recordProviderUsage(
  providerId: string,
  usage: {
    promptTokens?: number;
    completionTokens?: number;
    totalTokens?: number;
  },
  options: { filePath?: string; now?: () => string } = {},
): void {
  const filePath = options.filePath ?? Storage.getProviderUsagePath();
  const now = options.now ?? (() => new Date().toISOString());
  const store = readStore(filePath);
  const entry = store[providerId] ?? emptyEntry();
  entry.promptTokens += usage.promptTokens ?? 0;
  entry.completionTokens += usage.completionTokens ?? 0;
  entry.totalTokens += usage.totalTokens ?? 0;
  entry.requestCount += 1;
  entry.lastUsedAt = now();
  store[providerId] = entry;
  writeStore(filePath, store);
}

export function getProviderUsage(
  options: { filePath?: string } = {},
): ProviderUsageStore {
  return readStore(options.filePath ?? Storage.getProviderUsagePath());
}

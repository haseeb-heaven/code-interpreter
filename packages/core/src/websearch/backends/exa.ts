/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import {
  asString,
  fetchJson,
  formatHitsSummary,
  isRecord,
} from '../httpJson.js';
import type {
  WebSearchBackend,
  WebSearchHit,
  WebSearchResult,
} from '../types.js';

const ENV = 'EXA_API_KEY';
const ENDPOINT = 'https://api.exa.ai/search';

export const exaBackend: WebSearchBackend = {
  meta: {
    id: 'exa',
    displayName: 'Exa',
    envKey: ENV,
    signupUrl: 'https://dashboard.exa.ai/api-keys',
    notes: 'Neural / semantic search; strong for research-style discovery.',
    freeNoKey: false,
    recommendedFor: ['open_source', 'openai', 'anthropic', 'unknown'],
  },
  isAvailable(env = process.env): boolean {
    return Boolean(env[ENV]?.trim());
  },
  async search(query, options): Promise<WebSearchResult> {
    const env = options?.env ?? process.env;
    const key = env[ENV]?.trim();
    if (!key) throw new Error(`${ENV} is not set`);

    const raw = await fetchJson(ENDPOINT, {
      method: 'POST',
      signal: options?.signal,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        'x-api-key': key,
      },
      body: JSON.stringify({
        query,
        numResults: 8,
        type: 'auto',
        contents: { text: { maxCharacters: 400 } },
      }),
    });

    const hits: WebSearchHit[] = [];
    if (isRecord(raw) && Array.isArray(raw['results'])) {
      for (const item of raw['results']) {
        if (!isRecord(item)) continue;
        const title = asString(item['title']) || asString(item['url']);
        const link = asString(item['url']);
        if (!title || !link) continue;
        let snippet = asString(item['text']);
        if (!snippet && isRecord(item['contents'])) {
          snippet = asString(item['contents']['text']);
        }
        hits.push({ title, url: link, snippet });
        if (hits.length >= 8) break;
      }
    }
    if (hits.length === 0) {
      throw new Error('Exa returned no results');
    }
    return {
      hits,
      provider: 'exa',
      summary: formatHitsSummary(query, hits, 'exa'),
    };
  },
};

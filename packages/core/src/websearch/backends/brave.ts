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

const ENV = 'BRAVE_API_KEY';
const ENDPOINT = 'https://api.search.brave.com/res/v1/web/search';

export const braveBackend: WebSearchBackend = {
  meta: {
    id: 'brave',
    displayName: 'Brave Search',
    envKey: ENV,
    signupUrl: 'https://api.search.brave.com/app/keys',
    notes:
      'Independent index, cheap, privacy-friendly. Recommended for open-source / multi-provider models.',
    freeNoKey: false,
    recommendedFor: ['open_source', 'openai', 'anthropic', 'local', 'unknown'],
  },
  isAvailable(env = process.env): boolean {
    return Boolean(env[ENV]?.trim());
  },
  async search(query, options): Promise<WebSearchResult> {
    const env = options?.env ?? process.env;
    const key = env[ENV]?.trim();
    if (!key) throw new Error(`${ENV} is not set`);

    const url = new URL(ENDPOINT);
    url.searchParams.set('q', query);
    url.searchParams.set('count', '8');

    const raw = await fetchJson(url.toString(), {
      method: 'GET',
      signal: options?.signal,
      headers: {
        Accept: 'application/json',
        'X-Subscription-Token': key,
        'User-Agent': 'OpenAgent/4.0',
      },
    });

    const hits: WebSearchHit[] = [];
    if (
      isRecord(raw) &&
      isRecord(raw['web']) &&
      Array.isArray(raw['web']['results'])
    ) {
      for (const item of raw['web']['results']) {
        if (!isRecord(item)) continue;
        const title = asString(item['title']);
        const link = asString(item['url']);
        if (!title || !link) continue;
        hits.push({
          title,
          url: link,
          snippet: asString(item['description']),
        });
        if (hits.length >= 8) break;
      }
    }
    if (hits.length === 0) {
      throw new Error('Brave Search returned no results');
    }
    return {
      hits,
      provider: 'brave',
      summary: formatHitsSummary(query, hits, 'brave'),
    };
  },
};

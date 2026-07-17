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

const ENV = 'TAVILY_API_KEY';
const ENDPOINT = 'https://api.tavily.com/search';

export const tavilyBackend: WebSearchBackend = {
  meta: {
    id: 'tavily',
    displayName: 'Tavily',
    envKey: ENV,
    signupUrl: 'https://app.tavily.com/home',
    notes: 'AI-agent oriented search with clean snippets. Strong free tier.',
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
      },
      body: JSON.stringify({
        api_key: key,
        query,
        max_results: 8,
        include_answer: true,
      }),
    });

    const hits: WebSearchHit[] = [];
    if (isRecord(raw) && Array.isArray(raw['results'])) {
      for (const item of raw['results']) {
        if (!isRecord(item)) continue;
        const title = asString(item['title']);
        const link = asString(item['url']);
        if (!title || !link) continue;
        hits.push({
          title,
          url: link,
          snippet: asString(item['content']),
        });
        if (hits.length >= 8) break;
      }
    }

    const answer = isRecord(raw) ? asString(raw['answer']) : undefined;
    if (hits.length === 0 && !answer) {
      throw new Error('Tavily returned no results');
    }

    const parts: string[] = [];
    if (answer) parts.push(answer, '');
    if (hits.length > 0) {
      parts.push(formatHitsSummary(query, hits, 'tavily'));
    } else {
      parts.push(
        `Web search results for "${query}" (via tavily):\n\n${answer}`,
      );
    }

    return {
      hits,
      provider: 'tavily',
      summary: parts.join('\n'),
    };
  },
};

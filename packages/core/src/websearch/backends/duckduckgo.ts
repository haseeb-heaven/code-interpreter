/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import {
  searchDuckDuckGoHtml,
  searchDuckDuckGoInstant,
  searchWebFallback,
} from '../../utils/webSearchProviders.js';
import type { WebSearchBackend, WebSearchResult } from '../types.js';

export const duckduckgoBackend: WebSearchBackend = {
  meta: {
    id: 'duckduckgo',
    displayName: 'DuckDuckGo (no key)',
    envKey: null,
    signupUrl: null,
    notes: 'Zero-key fallback. Works offline from signup; quality varies.',
    freeNoKey: true,
    recommendedFor: ['local', 'open_source', 'unknown'],
  },
  isAvailable(): boolean {
    return true;
  },
  async search(query, options): Promise<WebSearchResult> {
    const r = await searchWebFallback(query, options?.signal);
    return {
      summary: r.summary,
      hits: r.hits,
      provider: r.provider.startsWith('duckduckgo')
        ? r.provider
        : `duckduckgo/${r.provider}`,
    };
  },
};

/** Exposed for unit tests that only want Instant Answer. */
export async function searchDuckDuckGoInstantOnly(
  query: string,
  signal?: AbortSignal,
): Promise<WebSearchResult | null> {
  const r = await searchDuckDuckGoInstant(query, signal);
  return r ? { summary: r.summary, hits: r.hits, provider: r.provider } : null;
}

export async function searchDuckDuckGoHtmlOnly(
  query: string,
  signal?: AbortSignal,
): Promise<WebSearchResult | null> {
  const r = await searchDuckDuckGoHtml(query, signal);
  return r ? { summary: r.summary, hits: r.hits, provider: r.provider } : null;
}

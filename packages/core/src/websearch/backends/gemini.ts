/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Gemini Google Search grounding is executed inside WebSearchTool (needs
 * GeminiClient). This backend only reports availability + metadata so the
 * wizard/router can recommend it when a Gemini key (or active Gemini model)
 * is present.
 */

import type { WebSearchBackend, WebSearchResult } from '../types.js';

const ENV_KEYS = ['GEMINI_API_KEY', 'GOOGLE_API_KEY'] as const;

export function hasGeminiSearchKey(
  env: NodeJS.ProcessEnv = process.env,
): boolean {
  return ENV_KEYS.some((k) => Boolean(env[k]?.trim()));
}

export const geminiBackendMeta = {
  id: 'gemini',
  displayName: 'Google Search (Gemini grounding)',
  envKey: 'GEMINI_API_KEY',
  signupUrl: 'https://aistudio.google.com/apikey',
  notes:
    'Uses Gemini API Google Search grounding. Recommended when the active model is Gemini or GEMINI_API_KEY is set.',
  freeNoKey: false,
  recommendedFor: ['gemini' as const],
};

/**
 * Placeholder backend — real Gemini search runs in WebSearchTool via the
 * client. `search()` should not be called by the HTTP router for gemini.
 */
export const geminiBackend: WebSearchBackend = {
  meta: {
    ...geminiBackendMeta,
    recommendedFor: ['gemini'],
  },
  isAvailable(env = process.env): boolean {
    return hasGeminiSearchKey(env);
  },
  async search(): Promise<WebSearchResult> {
    throw new Error(
      'Gemini Google Search is executed via the LLM client, not the HTTP router',
    );
  },
};

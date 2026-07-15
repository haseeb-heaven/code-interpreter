/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * LM Studio detection via its OpenAI-compatible API at
 * `http://localhost:1234`. No API key is required.
 */

import { LMSTUDIO_BASE_URL } from './providers.js';

async function fetchModels(
  baseUrl: string,
  timeoutMs: number,
): Promise<Response> {
  const url = `${baseUrl.replace(/\/+$/, '')}/v1/models`;
  return fetch(url, { signal: AbortSignal.timeout(timeoutMs) });
}

/** Returns true when the LM Studio server responds at `baseUrl`. */
export async function isLMStudioRunning(
  baseUrl: string = LMSTUDIO_BASE_URL,
  timeoutMs = 2000,
): Promise<boolean> {
  try {
    const resp = await fetchModels(baseUrl, timeoutMs);
    return resp.ok;
  } catch {
    return false;
  }
}

/** Returns models loaded in LM Studio (OpenAI `/v1/models` shape). */
export async function listLMStudioModels(
  baseUrl: string = LMSTUDIO_BASE_URL,
  timeoutMs = 3000,
): Promise<string[]> {
  try {
    const resp = await fetchModels(baseUrl, timeoutMs);
    if (!resp.ok) return [];
    // eslint-disable-next-line @typescript-eslint/no-unsafe-type-assertion
    const payload = (await resp.json()) as {
      data?: Array<{ id?: string } | string>;
    };
    const names: string[] = [];
    for (const item of payload.data ?? []) {
      if (typeof item === 'string') {
        names.push(item);
      } else if (item && typeof item === 'object' && item.id) {
        names.push(String(item.id));
      }
    }
    return names;
  } catch {
    return [];
  }
}

/** Normalizes a bare LM Studio model name to its LiteLLM-style id. */
export function litellmLMStudioId(model: string): string {
  const name = (model ?? '').trim();
  return name.startsWith('lmstudio/') ? name : `lmstudio/${name}`;
}

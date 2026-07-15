/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Ollama detection and model picking for local-only runs.
 *
 * Port of `libs/local/ollama_helper.py` from the original Python
 * code-interpreter project. Ollama is the default provider: when no
 * provider is specified we probe `http://localhost:11434/api/tags` and,
 * if it answers, use the best installed model with no API key at all.
 */

import { OLLAMA_BASE_URL } from './providers.js';

/** Preferred model families, best first (mirrors the Python helper). */
export const OLLAMA_DEFAULT_PRIORITY: readonly string[] = [
  'codellama',
  'llama3.1',
  'llama3',
  'mistral',
  'deepseek',
  'qwen',
  'phi',
];

export class OllamaError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'OllamaError';
  }
}

async function fetchTags(
  baseUrl: string,
  timeoutMs: number,
): Promise<Response> {
  const url = `${baseUrl.replace(/\/+$/, '')}/api/tags`;
  return fetch(url, { signal: AbortSignal.timeout(timeoutMs) });
}

/** Returns true when the Ollama HTTP API responds at `baseUrl`. */
export async function isOllamaRunning(
  baseUrl: string = OLLAMA_BASE_URL,
  timeoutMs = 2000,
): Promise<boolean> {
  try {
    const resp = await fetchTags(baseUrl, timeoutMs);
    return resp.ok;
  } catch {
    return false;
  }
}

/** Returns locally installed Ollama model names (may be empty). */
export async function listOllamaModels(
  baseUrl: string = OLLAMA_BASE_URL,
  timeoutMs = 3000,
): Promise<string[]> {
  try {
    const resp = await fetchTags(baseUrl, timeoutMs);
    if (!resp.ok) return [];
    // eslint-disable-next-line @typescript-eslint/no-unsafe-type-assertion
    const payload = (await resp.json()) as {
      models?: Array<{ name?: string; model?: string } | string>;
    };
    const names: string[] = [];
    for (const item of payload.models ?? []) {
      if (typeof item === 'string') {
        names.push(item);
      } else if (item && typeof item === 'object') {
        const name = item.name ?? item.model;
        if (name) names.push(String(name));
      }
    }
    return names;
  } catch {
    return [];
  }
}

/**
 * Picks the best installed model by family priority; falls back to the
 * first installed model, or `undefined` when nothing is installed.
 */
export function pickBestOllamaModel(
  installed: readonly string[],
  priority: readonly string[] = OLLAMA_DEFAULT_PRIORITY,
): string | undefined {
  if (installed.length === 0) return undefined;
  for (const family of priority) {
    const match = installed.find((name) =>
      name.toLowerCase().startsWith(family.toLowerCase()),
    );
    if (match) return match;
  }
  return installed[0];
}

/** Normalizes a bare Ollama model name to its LiteLLM-style id. */
export function litellmOllamaId(model: string): string {
  const name = (model ?? '').trim();
  return name.startsWith('ollama/') ? name : `ollama/${name}`;
}

/**
 * Resolves the model to run against a live Ollama server.
 *
 * - `requested` set: verified against the installed list (exact or
 *   prefix match on the base name).
 * - `requested` empty: best installed model by priority.
 *
 * @throws OllamaError when the server is down, has no models, or the
 *   requested model is not installed.
 */
export async function resolveOllamaModel(
  requested?: string,
  baseUrl: string = OLLAMA_BASE_URL,
): Promise<string> {
  if (!(await isOllamaRunning(baseUrl))) {
    throw new OllamaError(
      `Ollama is not reachable at ${baseUrl}. Start it with \`ollama serve\`.`,
    );
  }
  const installed = await listOllamaModels(baseUrl);
  if (installed.length === 0) {
    throw new OllamaError(
      'Ollama is running but no models are installed. Pull one with `ollama pull llama3.1`.',
    );
  }
  const wanted = (requested ?? '').replace(/^ollama\//, '').trim();
  if (!wanted) {
    const best = pickBestOllamaModel(installed);
    if (best) return best;
    throw new OllamaError('No Ollama model could be selected.');
  }
  const exact = installed.find((name) => name === wanted);
  if (exact) return exact;
  const prefix = installed.find((name) => name.split(':')[0] === wanted);
  if (prefix) return prefix;
  throw new OllamaError(
    `Model "${wanted}" is not installed in Ollama. Installed: ${installed.join(', ')}`,
  );
}

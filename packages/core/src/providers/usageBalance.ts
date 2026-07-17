/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Live account-balance lookups, where a provider actually exposes one.
 *
 * Only OpenRouter has a stable, standard-API-key-compatible credits
 * endpoint. OpenAI's legacy billing endpoints are deprecated/unreliable
 * for standard keys and Anthropic exposes no public equivalent, so those
 * providers are intentionally not covered here — callers should fall back
 * to the accumulated local usage from usageStore.ts and label it as such.
 */

const OPENROUTER_CREDITS_URL = 'https://openrouter.ai/api/v1/credits';

export interface OpenRouterCredits {
  totalCredits: number;
  totalUsage: number;
  remainingFraction: number;
}

function isRecord(val: unknown): val is Record<string, unknown> {
  return typeof val === 'object' && val !== null && !Array.isArray(val);
}

function isNumber(val: unknown): val is number {
  return typeof val === 'number';
}

export async function fetchOpenRouterCredits(
  apiKey: string,
): Promise<OpenRouterCredits | undefined> {
  try {
    const res = await fetch(OPENROUTER_CREDITS_URL, {
      headers: { Authorization: `Bearer ${apiKey}` },
    });
    if (!res.ok) return undefined;
    const body: unknown = await res.json();
    const data = isRecord(body) ? body['data'] : undefined;
    const record = isRecord(data) ? data : undefined;
    const totalCredits = record?.['total_credits'];
    const totalUsage = record?.['total_usage'];
    if (!isNumber(totalCredits) || !isNumber(totalUsage)) {
      return undefined;
    }
    const remainingFraction =
      totalCredits > 0 ? (totalCredits - totalUsage) / totalCredits : 0;
    return { totalCredits, totalUsage, remainingFraction };
  } catch {
    return undefined;
  }
}

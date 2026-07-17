/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

export function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

export function asString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value : undefined;
}

export async function fetchJson(
  url: string,
  init: RequestInit,
): Promise<unknown> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(
      `HTTP ${res.status} ${res.statusText}${body ? `: ${body.slice(0, 200)}` : ''}`,
    );
  }
  return res.json() as Promise<unknown>;
}

export function formatHitsSummary(
  query: string,
  hits: Array<{ title: string; url: string; snippet?: string }>,
  provider: string,
): string {
  const lines = [
    `Web search results for "${query}" (via ${provider}):`,
    '',
    ...hits.map(
      (h, i) =>
        `[${i + 1}] ${h.title}\n    ${h.url}${h.snippet ? `\n    ${h.snippet}` : ''}`,
    ),
  ];
  return lines.join('\n');
}

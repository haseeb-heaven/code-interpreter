/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Provider-agnostic web search backends.
 * Used when Gemini Google Search grounding is unavailable (multi-provider /
 * free models without a Gemini key, or Gemini search failures).
 */

export interface WebSearchHit {
  title: string;
  url: string;
  snippet?: string;
}

export interface WebSearchProviderResult {
  summary: string;
  hits: WebSearchHit[];
  provider: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function asString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value : undefined;
}

function decodeHtmlEntities(text: string): string {
  return text
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&#x27;/g, "'")
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(Number(n)))
    .replace(/&#x([0-9a-fA-F]+);/g, (_, h) =>
      String.fromCharCode(parseInt(h, 16)),
    )
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * DuckDuckGo Instant Answer API (no key). Good for facts; thin for pure SERP.
 */
export async function searchDuckDuckGoInstant(
  query: string,
  signal?: AbortSignal,
): Promise<WebSearchProviderResult | null> {
  const url = new URL('https://api.duckduckgo.com/');
  url.searchParams.set('q', query);
  url.searchParams.set('format', 'json');
  url.searchParams.set('no_html', '1');
  url.searchParams.set('skip_disambig', '1');

  const res = await fetch(url, {
    signal,
    headers: {
      Accept: 'application/json',
      'User-Agent':
        'OpenAgent/4.0 (web-search; +https://github.com/haseeb-heaven/open-agent)',
    },
  });
  if (!res.ok) {
    throw new Error(`DuckDuckGo Instant Answer HTTP ${res.status}`);
  }
  const raw: unknown = await res.json();
  if (!isRecord(raw)) {
    return null;
  }
  const data = raw;

  const hits: WebSearchHit[] = [];
  const parts: string[] = [];

  const heading = asString(data['Heading']);
  if (heading) {
    parts.push(`# ${heading}`);
  }
  const abstractText = asString(data['AbstractText']);
  const abstractUrl = asString(data['AbstractURL']);
  const abstractSource = asString(data['AbstractSource']);
  if (abstractText) {
    parts.push(abstractText);
    if (abstractUrl) {
      hits.push({
        title: abstractSource || heading || 'Abstract',
        url: abstractUrl,
        snippet: abstractText,
      });
    }
  }
  const answer = asString(data['Answer']);
  if (answer) {
    parts.push(`Answer: ${answer}`);
  }
  const definition = asString(data['Definition']);
  const definitionUrl = asString(data['DefinitionURL']);
  if (definition) {
    parts.push(`Definition: ${definition}`);
    if (definitionUrl) {
      hits.push({
        title: 'Definition',
        url: definitionUrl,
        snippet: definition,
      });
    }
  }

  const pushTopic = (t: unknown) => {
    if (!isRecord(t)) return;
    const text = asString(t['Text']);
    const firstUrl = asString(t['FirstURL']);
    if (!text && !firstUrl) return;
    hits.push({
      title: (text || firstUrl || 'Result').slice(0, 120),
      url: firstUrl || '',
      snippet: text,
    });
  };

  const results = data['Results'];
  if (Array.isArray(results)) {
    for (const item of results) {
      pushTopic(item);
    }
  }
  const related = data['RelatedTopics'];
  if (Array.isArray(related)) {
    for (const item of related) {
      if (!isRecord(item)) continue;
      const nested = item['Topics'];
      if (Array.isArray(nested)) {
        for (const sub of nested.slice(0, 5)) {
          pushTopic(sub);
        }
      } else {
        pushTopic(item);
      }
    }
  }

  if (hits.length === 0 && parts.length === 0) {
    return null;
  }

  if (hits.length > 0) {
    parts.push(
      '',
      'Sources:',
      ...hits
        .filter((h) => h.url)
        .slice(0, 8)
        .map((h, i) => `[${i + 1}] ${h.title} (${h.url})`),
    );
  }

  return {
    summary: parts.join('\n').trim(),
    hits: hits.filter((h) => h.url).slice(0, 8),
    provider: 'duckduckgo-instant',
  };
}

/**
 * DuckDuckGo HTML SERP scrape (no key). Best-effort parsing of result cards.
 */
export async function searchDuckDuckGoHtml(
  query: string,
  signal?: AbortSignal,
): Promise<WebSearchProviderResult | null> {
  const url = new URL('https://html.duckduckgo.com/html/');
  url.searchParams.set('q', query);

  const res = await fetch(url, {
    signal,
    headers: {
      Accept: 'text/html',
      'User-Agent':
        'Mozilla/5.0 (compatible; OpenAgent/4.0; +https://github.com/haseeb-heaven/open-agent)',
    },
    redirect: 'follow',
  });
  if (!res.ok) {
    throw new Error(`DuckDuckGo HTML HTTP ${res.status}`);
  }
  const html = await res.text();

  // Result links: class="result__a" href="..."
  const hits: WebSearchHit[] = [];
  const linkRe = /class="result__a"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/gi;
  const snippetRe = /class="result__snippet"[^>]*>([\s\S]*?)<\/(?:a|td|div)>/gi;
  const snippets: string[] = [];
  let m: RegExpExecArray | null;
  while ((m = snippetRe.exec(html)) !== null) {
    snippets.push(decodeHtmlEntities(m[1]));
  }

  let i = 0;
  while ((m = linkRe.exec(html)) !== null && hits.length < 8) {
    let href = m[1];
    // DDG sometimes wraps redirects: //duckduckgo.com/l/?uddg=<encoded>
    try {
      const u = new URL(href, 'https://duckduckgo.com');
      const uddg = u.searchParams.get('uddg');
      if (uddg) href = decodeURIComponent(uddg);
    } catch {
      // keep raw
    }
    const title = decodeHtmlEntities(m[2]);
    if (!title || !href.startsWith('http')) continue;
    hits.push({
      title,
      url: href,
      snippet: snippets[i],
    });
    i += 1;
  }

  if (hits.length === 0) {
    return null;
  }

  const summary = [
    `Web search results for "${query}":`,
    '',
    ...hits.map(
      (h, idx) =>
        `[${idx + 1}] ${h.title}\n    ${h.url}${h.snippet ? `\n    ${h.snippet}` : ''}`,
    ),
  ].join('\n');

  return {
    summary,
    hits,
    provider: 'duckduckgo-html',
  };
}

/**
 * Run independent search backends and return the best non-empty result.
 */
export async function searchWebFallback(
  query: string,
  signal?: AbortSignal,
): Promise<WebSearchProviderResult> {
  const errors: string[] = [];

  try {
    const instant = await searchDuckDuckGoInstant(query, signal);
    // Prefer HTML SERP when Instant Answer is thin (no related topics)
    if (instant && instant.hits.length >= 2) {
      return instant;
    }
    try {
      const html = await searchDuckDuckGoHtml(query, signal);
      if (html && html.hits.length > 0) {
        // Merge abstract if present
        if (instant?.summary) {
          return {
            summary: `${instant.summary}\n\n${html.summary}`,
            hits: [...(instant.hits ?? []), ...html.hits].slice(0, 10),
            provider: 'duckduckgo-combined',
          };
        }
        return html;
      }
    } catch (e) {
      errors.push(e instanceof Error ? e.message : String(e));
    }
    if (instant) return instant;
  } catch (e) {
    errors.push(e instanceof Error ? e.message : String(e));
  }

  try {
    const html = await searchDuckDuckGoHtml(query, signal);
    if (html) return html;
  } catch (e) {
    errors.push(e instanceof Error ? e.message : String(e));
  }

  throw new Error(
    `All web search backends failed for "${query}": ${errors.join('; ') || 'no results'}`,
  );
}

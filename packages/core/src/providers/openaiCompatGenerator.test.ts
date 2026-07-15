/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect, vi } from 'vitest';
import {
  OpenAICompatContentGenerator,
  toOpenAIMessages,
  toOpenAITools,
} from './openaiCompatGenerator.js';
import { getProvider } from './providers.js';
import type { GenerateContentParameters } from '@google/genai';

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function sseResponse(lines: string[]): Response {
  const body = lines.map((line) => `data: ${line}\n`).join('\n') + '\n';
  return new Response(body, {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  });
}

const REQUEST: GenerateContentParameters = {
  model: 'llama3.1:8b',
  contents: [{ role: 'user', parts: [{ text: 'hello' }] }],
  config: {
    systemInstruction: { role: 'user', parts: [{ text: 'be brief' }] },
    temperature: 0.2,
    maxOutputTokens: 64,
  },
};

describe('toOpenAIMessages', () => {
  it('maps system instruction and user turns', () => {
    expect(toOpenAIMessages(REQUEST)).toEqual([
      { role: 'system', content: 'be brief' },
      { role: 'user', content: 'hello' },
    ]);
  });

  it('maps model turns with function calls to assistant tool_calls', () => {
    const messages = toOpenAIMessages({
      model: 'm',
      contents: [
        {
          role: 'model',
          parts: [
            { functionCall: { id: 'call_1', name: 'ls', args: { dir: '.' } } },
          ],
        },
        {
          role: 'user',
          parts: [
            {
              functionResponse: {
                id: 'call_1',
                name: 'ls',
                response: { output: 'README.md' },
              },
            },
          ],
        },
      ],
    });
    expect(messages).toEqual([
      {
        role: 'assistant',
        content: null,
        tool_calls: [
          {
            id: 'call_1',
            type: 'function',
            function: { name: 'ls', arguments: '{"dir":"."}' },
          },
        ],
      },
      {
        role: 'tool',
        tool_call_id: 'call_1',
        content: '{"output":"README.md"}',
      },
    ]);
  });

  it('maps inline images to image_url content parts', () => {
    const messages = toOpenAIMessages({
      model: 'm',
      contents: [
        {
          role: 'user',
          parts: [
            { text: 'what is this?' },
            { inlineData: { mimeType: 'image/png', data: 'aGk=' } },
          ],
        },
      ],
    });
    expect(messages[0].content).toEqual([
      { type: 'text', text: 'what is this?' },
      { type: 'image_url', image_url: { url: 'data:image/png;base64,aGk=' } },
    ]);
  });
});

describe('toOpenAITools', () => {
  it('maps function declarations to OpenAI tool definitions', () => {
    const tools = toOpenAITools({
      model: 'm',
      contents: 'x',
      config: {
        tools: [
          {
            functionDeclarations: [
              {
                name: 'read_file',
                description: 'Reads a file',
                parametersJsonSchema: { type: 'object' },
              },
            ],
          },
        ],
      },
    });
    expect(tools).toEqual([
      {
        type: 'function',
        function: {
          name: 'read_file',
          description: 'Reads a file',
          parameters: { type: 'object' },
        },
      },
    ]);
  });

  it('returns undefined without tools', () => {
    expect(toOpenAITools({ model: 'm', contents: 'x' })).toBeUndefined();
  });
});

describe('OpenAICompatContentGenerator', () => {
  it('routes generateContent through the provider base URL', async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(
      jsonResponse({
        model: 'llama3.1:8b',
        choices: [{ message: { content: 'hi there' }, finish_reason: 'stop' }],
        usage: { prompt_tokens: 3, completion_tokens: 2, total_tokens: 5 },
      }),
    );
    const generator = new OpenAICompatContentGenerator({
      modelId: 'ollama/llama3.1:8b',
      provider: getProvider('ollama')!,
      fetchImpl,
    });
    const response = await generator.generateContent(REQUEST, 'prompt-id');

    expect(fetchImpl).toHaveBeenCalledWith(
      'http://localhost:11434/v1/chat/completions',
      expect.objectContaining({ method: 'POST' }),
    );
    const body = JSON.parse(
      (fetchImpl.mock.calls[0][1] as { body: string }).body,
    );
    expect(body.model).toBe('llama3.1:8b');
    expect(body.stream).toBe(false);
    expect(body.temperature).toBe(0.2);
    expect(body.max_tokens).toBe(64);

    expect(response.candidates?.[0]?.content?.parts?.[0]?.text).toBe(
      'hi there',
    );
    expect(response.usageMetadata?.totalTokenCount).toBe(5);
  });

  it('sends a Bearer key for cloud providers but none for local', async () => {
    const fetchImpl = vi
      .fn()
      .mockImplementation(() =>
        Promise.resolve(jsonResponse({ choices: [{ message: {} }] })),
      );
    const groq = new OpenAICompatContentGenerator({
      modelId: 'groq/llama-3.1-8b-instant',
      provider: getProvider('groq')!,
      env: { GROQ_API_KEY: 'gsk-test' },
      fetchImpl,
    });
    await groq.generateContent(REQUEST, 'p');
    const groqHeaders = (
      fetchImpl.mock.calls[0][1] as { headers: Record<string, string> }
    ).headers;
    expect(groqHeaders['Authorization']).toBe('Bearer gsk-test');

    const ollama = new OpenAICompatContentGenerator({
      modelId: 'ollama/llama3.1:8b',
      provider: getProvider('ollama')!,
      env: {},
      fetchImpl,
    });
    await ollama.generateContent(REQUEST, 'p');
    const ollamaHeaders = (
      fetchImpl.mock.calls[1][1] as { headers: Record<string, string> }
    ).headers;
    expect(ollamaHeaders['Authorization']).toBeUndefined();
  });

  it('maps tool_calls in responses to functionCall parts', async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(
      jsonResponse({
        choices: [
          {
            message: {
              tool_calls: [
                {
                  id: 'call_9',
                  function: { name: 'ls', arguments: '{"dir":"/"}' },
                },
              ],
            },
            finish_reason: 'tool_calls',
          },
        ],
      }),
    );
    const generator = new OpenAICompatContentGenerator({
      modelId: 'ollama/llama3.1:8b',
      provider: getProvider('ollama')!,
      fetchImpl,
    });
    const response = await generator.generateContent(REQUEST, 'p');
    expect(response.candidates?.[0]?.content?.parts?.[0]?.functionCall).toEqual(
      { id: 'call_9', name: 'ls', args: { dir: '/' } },
    );
  });

  it('throws a provider-tagged error on HTTP failures', async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(new Response('rate limited', { status: 429 }));
    const generator = new OpenAICompatContentGenerator({
      modelId: 'groq/llama-3.1-8b-instant',
      provider: getProvider('groq')!,
      env: { GROQ_API_KEY: 'x' },
      fetchImpl,
    });
    await expect(generator.generateContent(REQUEST, 'p')).rejects.toThrow(
      /groq request failed \(429\)/,
    );
  });

  it('streams text deltas and trailing usage', async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(
      sseResponse([
        JSON.stringify({ choices: [{ delta: { content: 'Hel' } }] }),
        JSON.stringify({ choices: [{ delta: { content: 'lo' } }] }),
        JSON.stringify({
          choices: [{ delta: {}, finish_reason: 'stop' }],
          usage: { prompt_tokens: 1, completion_tokens: 2, total_tokens: 3 },
        }),
        '[DONE]',
      ]),
    );
    const generator = new OpenAICompatContentGenerator({
      modelId: 'ollama/llama3.1:8b',
      provider: getProvider('ollama')!,
      fetchImpl,
    });
    const chunks = [];
    for await (const chunk of await generator.generateContentStream(
      REQUEST,
      'p',
    )) {
      chunks.push(chunk);
    }
    const texts = chunks
      .map((c) => c.candidates?.[0]?.content?.parts?.[0]?.text)
      .filter(Boolean);
    expect(texts).toEqual(['Hel', 'lo']);
    expect(chunks.at(-1)?.usageMetadata?.totalTokenCount).toBe(3);
  });

  it('estimates countTokens and rejects embedContent', async () => {
    const generator = new OpenAICompatContentGenerator({
      modelId: 'ollama/llama3.1:8b',
      provider: getProvider('ollama')!,
      fetchImpl: vi.fn(),
    });
    const counted = await generator.countTokens({
      model: 'm',
      contents: [{ role: 'user', parts: [{ text: 'x'.repeat(40) }] }],
    });
    expect(counted.totalTokens).toBeGreaterThan(0);
    await expect(
      generator.embedContent({ model: 'm', contents: [] }),
    ).rejects.toThrow(/not supported/);
  });
});

/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * LiteLLM-style multi-provider routing implemented as a
 * {@link ContentGenerator}: translates Gemini `GenerateContentParameters`
 * to OpenAI-compatible chat completions and back, so every provider with
 * an OpenAI-compatible endpoint (Ollama, LM Studio, OpenAI, Groq,
 * DeepSeek, NVIDIA, Together, HuggingFace, OpenRouter, Cerebras, Z.ai,
 * Gemini's OpenAI endpoint, Anthropic via gateway) plugs into the CLI
 * without touching the rest of the codebase.
 */

import {
  GenerateContentResponse,
  FinishReason,
  type Content,
  type Part,
  type CountTokensParameters,
  type CountTokensResponse,
  type EmbedContentParameters,
  type EmbedContentResponse,
  type GenerateContentParameters,
  type FunctionDeclaration,
} from '@google/genai';
import type { ContentGenerator } from '../core/contentGenerator.js';
import {
  providerApiKey,
  splitModelId,
  type ProviderDefinition,
} from './providers.js';

interface OpenAIMessage {
  role: 'system' | 'user' | 'assistant' | 'tool';
  content: string | null | Array<Record<string, unknown>>;
  tool_calls?: Array<{
    id: string;
    type: 'function';
    function: { name: string; arguments: string };
  }>;
  tool_call_id?: string;
}

interface OpenAIChoiceDelta {
  role?: string;
  content?: string | null;
  tool_calls?: Array<{
    index?: number;
    id?: string;
    function?: { name?: string; arguments?: string };
  }>;
}

export interface OpenAICompatOptions {
  /** LiteLLM-style model id, e.g. "ollama/llama3.1:8b" or "groq/llama-3.1-8b-instant". */
  modelId: string;
  provider: ProviderDefinition;
  /** Overrides the provider's default OpenAI-compatible base URL. */
  apiBase?: string;
  apiKey?: string;
  temperature?: number;
  maxTokens?: number;
  env?: NodeJS.ProcessEnv;
  fetchImpl?: typeof fetch;
}

function contentsToList(
  contents: GenerateContentParameters['contents'],
): Content[] {
  if (Array.isArray(contents)) {
    return contents.map((c) =>
      typeof c === 'string'
        ? { role: 'user', parts: [{ text: c }] }
        : // eslint-disable-next-line @typescript-eslint/no-unsafe-type-assertion
          (c as Content),
    );
  }
  if (typeof contents === 'string') {
    return [{ role: 'user', parts: [{ text: contents }] }];
  }
  // eslint-disable-next-line @typescript-eslint/no-unsafe-type-assertion
  return [contents as Content];
}

function partText(part: Part): string | undefined {
  return typeof part.text === 'string' ? part.text : undefined;
}

/** Maps Gemini contents to OpenAI chat messages. */
export function toOpenAIMessages(
  request: GenerateContentParameters,
): OpenAIMessage[] {
  const messages: OpenAIMessage[] = [];

  const system = request.config?.systemInstruction;
  if (system) {
    const systemContents = contentsToList(
      system as GenerateContentParameters['contents'],
    );
    const text = systemContents
      .flatMap((c) => (c.parts ?? []).map(partText))
      .filter((t): t is string => Boolean(t))
      .join('\n');
    if (text) messages.push({ role: 'system', content: text });
  }

  for (const content of contentsToList(request.contents)) {
    const role = content.role === 'model' ? 'assistant' : 'user';
    const parts = content.parts ?? [];

    const toolCalls: NonNullable<OpenAIMessage['tool_calls']> = [];
    const toolResults: Array<{ id: string; output: string }> = [];
    const textParts: string[] = [];
    const imageParts: Array<Record<string, unknown>> = [];

    for (const part of parts) {
      const text = partText(part);
      if (text !== undefined) {
        textParts.push(text);
      } else if (part.functionCall) {
        toolCalls.push({
          id: part.functionCall.id ?? `call_${toolCalls.length}`,
          type: 'function',
          function: {
            name: part.functionCall.name ?? '',
            arguments: JSON.stringify(part.functionCall.args ?? {}),
          },
        });
      } else if (part.functionResponse) {
        toolResults.push({
          id: part.functionResponse.id ?? part.functionResponse.name ?? '',
          output: JSON.stringify(part.functionResponse.response ?? {}),
        });
      } else if (part.inlineData?.data) {
        imageParts.push({
          type: 'image_url',
          image_url: {
            url: `data:${part.inlineData.mimeType ?? 'image/png'};base64,${part.inlineData.data}`,
          },
        });
      }
    }

    for (const result of toolResults) {
      messages.push({
        role: 'tool',
        tool_call_id: result.id,
        content: result.output,
      });
    }

    if (toolCalls.length > 0) {
      messages.push({
        role: 'assistant',
        content: textParts.length > 0 ? textParts.join('\n') : null,
        tool_calls: toolCalls,
      });
    } else if (imageParts.length > 0) {
      messages.push({
        role,
        content: [
          ...textParts.map((text) => ({ type: 'text', text })),
          ...imageParts,
        ],
      });
    } else if (textParts.length > 0) {
      messages.push({ role, content: textParts.join('\n') });
    }
  }
  return messages;
}

/** Maps Gemini tool declarations to OpenAI tool definitions. */
export function toOpenAITools(
  request: GenerateContentParameters,
): Array<Record<string, unknown>> | undefined {
  const tools = request.config?.tools;
  if (!tools) return undefined;
  const declarations: FunctionDeclaration[] = [];
  // eslint-disable-next-line @typescript-eslint/no-unsafe-type-assertion
  for (const tool of tools as Array<{
    functionDeclarations?: FunctionDeclaration[];
  }>) {
    for (const decl of tool.functionDeclarations ?? []) {
      declarations.push(decl);
    }
  }
  if (declarations.length === 0) return undefined;
  return declarations.map((decl) => ({
    type: 'function',
    function: {
      name: decl.name,
      description: decl.description ?? '',
      parameters: decl.parametersJsonSchema ?? decl.parameters ?? {},
    },
  }));
}

function makeResponse(
  parts: Part[],
  options: {
    finishReason?: FinishReason;
    usage?: {
      prompt_tokens?: number;
      completion_tokens?: number;
      total_tokens?: number;
    };
    modelVersion?: string;
  } = {},
): GenerateContentResponse {
  const response = {
    candidates: [
      {
        content: { role: 'model', parts },
        index: 0,
        ...(options.finishReason ? { finishReason: options.finishReason } : {}),
      },
    ],
    ...(options.usage
      ? {
          usageMetadata: {
            promptTokenCount: options.usage.prompt_tokens ?? 0,
            candidatesTokenCount: options.usage.completion_tokens ?? 0,
            totalTokenCount: options.usage.total_tokens ?? 0,
          },
        }
      : {}),
    ...(options.modelVersion ? { modelVersion: options.modelVersion } : {}),
  };
  Object.setPrototypeOf(response, GenerateContentResponse.prototype);
  // eslint-disable-next-line @typescript-eslint/no-unsafe-type-assertion
  return response as GenerateContentResponse;
}

function mapFinishReason(reason: string | undefined): FinishReason {
  switch (reason) {
    case 'length':
      return FinishReason.MAX_TOKENS;
    case 'content_filter':
      return FinishReason.SAFETY;
    case 'stop':
    case 'tool_calls':
    default:
      return FinishReason.STOP;
  }
}

/**
 * ContentGenerator that routes to any OpenAI-compatible endpoint.
 */
export class OpenAICompatContentGenerator implements ContentGenerator {
  private readonly fetchImpl: typeof fetch;
  readonly provider: ProviderDefinition;
  readonly model: string;
  readonly apiBase: string;
  private readonly apiKey?: string;
  private readonly temperature?: number;
  private readonly maxTokens?: number;

  constructor(options: OpenAICompatOptions) {
    this.provider = options.provider;
    const { model } = splitModelId(options.modelId);
    this.model = model;
    this.apiBase = (options.apiBase ?? options.provider.apiBase).replace(
      /\/+$/,
      '',
    );
    this.apiKey =
      options.apiKey ?? providerApiKey(options.provider, options.env);
    this.temperature = options.temperature;
    this.maxTokens = options.maxTokens;
    this.fetchImpl = options.fetchImpl ?? fetch;
  }

  private buildBody(
    request: GenerateContentParameters,
    stream: boolean,
  ): Record<string, unknown> {
    const tools = toOpenAITools(request);
    return {
      model: this.model,
      messages: toOpenAIMessages(request),
      stream,
      ...(stream ? { stream_options: { include_usage: true } } : {}),
      temperature: request.config?.temperature ?? this.temperature ?? 0.1,
      ...((request.config?.maxOutputTokens ?? this.maxTokens)
        ? { max_tokens: request.config?.maxOutputTokens ?? this.maxTokens }
        : {}),
      ...(tools ? { tools } : {}),
    };
  }

  private headers(): Record<string, string> {
    return {
      'Content-Type': 'application/json',
      ...(this.apiKey ? { Authorization: `Bearer ${this.apiKey}` } : {}),
    };
  }

  async generateContent(
    request: GenerateContentParameters,
    _userPromptId: string,
    _role?: unknown,
  ): Promise<GenerateContentResponse> {
    const resp = await this.fetchImpl(`${this.apiBase}/chat/completions`, {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify(this.buildBody(request, false)),
    });
    if (!resp.ok) {
      const detail = await resp.text().catch(() => '');
      throw new Error(
        `${this.provider.id} request failed (${resp.status}): ${detail.slice(0, 500)}`,
      );
    }
    // eslint-disable-next-line @typescript-eslint/no-unsafe-type-assertion
    const payload = (await resp.json()) as {
      choices?: Array<{
        message?: OpenAIChoiceDelta & {
          tool_calls?: Array<{
            id?: string;
            function?: { name?: string; arguments?: string };
          }>;
        };
        finish_reason?: string;
      }>;
      usage?: {
        prompt_tokens?: number;
        completion_tokens?: number;
        total_tokens?: number;
      };
      model?: string;
    };
    const choice = payload.choices?.[0];
    const parts: Part[] = [];
    if (choice?.message?.content) {
      parts.push({ text: String(choice.message.content) });
    }
    for (const call of choice?.message?.tool_calls ?? []) {
      let args: Record<string, unknown> = {};
      try {
        // eslint-disable-next-line @typescript-eslint/no-unsafe-type-assertion
        args = JSON.parse(call.function?.arguments || '{}') as Record<
          string,
          unknown
        >;
      } catch {
        // Malformed tool arguments: surface an empty args object.
      }
      parts.push({
        functionCall: {
          id: call.id,
          name: call.function?.name ?? '',
          args,
        },
      });
    }
    return makeResponse(parts, {
      finishReason: mapFinishReason(choice?.finish_reason),
      usage: payload.usage,
      modelVersion: payload.model ?? this.model,
    });
  }

  async generateContentStream(
    request: GenerateContentParameters,
    _userPromptId: string,
    _role?: unknown,
  ): Promise<AsyncGenerator<GenerateContentResponse>> {
    const resp = await this.fetchImpl(`${this.apiBase}/chat/completions`, {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify(this.buildBody(request, true)),
    });
    if (!resp.ok || !resp.body) {
      const detail = await resp.text().catch(() => '');
      throw new Error(
        `${this.provider.id} stream failed (${resp.status}): ${detail.slice(0, 500)}`,
      );
    }
    const body = resp.body;
    const model = this.model;

    async function* stream(): AsyncGenerator<GenerateContentResponse> {
      const decoder = new TextDecoder();
      let buffer = '';
      // Streamed tool calls arrive fragmented; accumulate by index.
      const toolCalls = new Map<
        number,
        { id?: string; name: string; args: string }
      >();
      let usage:
        | {
            prompt_tokens?: number;
            completion_tokens?: number;
            total_tokens?: number;
          }
        | undefined;
      let finish: string | undefined;

      const reader = body.getReader();
      try {
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          let newline: number;
          while ((newline = buffer.indexOf('\n')) >= 0) {
            const line = buffer.slice(0, newline).trim();
            buffer = buffer.slice(newline + 1);
            if (!line.startsWith('data:')) continue;
            const data = line.slice(5).trim();
            if (!data || data === '[DONE]') continue;
            let chunk: {
              choices?: Array<{
                delta?: OpenAIChoiceDelta;
                finish_reason?: string;
              }>;
              usage?: typeof usage;
            };
            try {
              // eslint-disable-next-line @typescript-eslint/no-unsafe-type-assertion
              chunk = JSON.parse(data) as typeof chunk;
            } catch {
              continue;
            }
            if (chunk.usage) usage = chunk.usage;
            const choice = chunk.choices?.[0];
            if (!choice) continue;
            if (choice.finish_reason) finish = choice.finish_reason;
            const delta = choice.delta;
            if (!delta) continue;
            if (delta.content) {
              yield makeResponse([{ text: delta.content }], {
                modelVersion: model,
              });
            }
            for (const call of delta.tool_calls ?? []) {
              const index = call.index ?? 0;
              const entry = toolCalls.get(index) ?? { name: '', args: '' };
              if (call.id) entry.id = call.id;
              if (call.function?.name) entry.name += call.function.name;
              if (call.function?.arguments) {
                entry.args += call.function.arguments;
              }
              toolCalls.set(index, entry);
            }
          }
        }
      } finally {
        reader.releaseLock();
      }

      const finalParts: Part[] = [];
      for (const [, call] of [...toolCalls.entries()].sort(
        (a, b) => a[0] - b[0],
      )) {
        let args: Record<string, unknown> = {};
        try {
          // eslint-disable-next-line @typescript-eslint/no-unsafe-type-assertion
          args = JSON.parse(call.args || '{}') as Record<string, unknown>;
        } catch {
          // Malformed streamed tool arguments: emit empty args.
        }
        finalParts.push({
          functionCall: { id: call.id, name: call.name, args },
        });
      }
      if (finalParts.length > 0 || usage || finish) {
        yield makeResponse(finalParts, {
          finishReason: mapFinishReason(finish),
          usage,
          modelVersion: model,
        });
      }
    }
    return stream();
  }

  async countTokens(
    request: CountTokensParameters,
  ): Promise<CountTokensResponse> {
    // OpenAI-compatible endpoints expose no token counting; estimate at
    // ~4 characters per token, which is what LiteLLM falls back to.
    const text = JSON.stringify(request.contents ?? '');
    return { totalTokens: Math.ceil(text.length / 4) };
  }

  async embedContent(
    _request: EmbedContentParameters,
  ): Promise<EmbedContentResponse> {
    throw new Error(
      `embedContent is not supported for provider "${this.provider.id}".`,
    );
  }
}

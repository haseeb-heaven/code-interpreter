/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Runtime free-model fallback chain. Wraps an OpenAI-compatible generator
 * and, when a request fails with a rate limit or free-router routing
 * error, retries down the curated free catalog (freeFallbackCandidates)
 * until a model answers or the chain is exhausted. Once a fallback model
 * succeeds it stays active for subsequent requests, so a session does not
 * keep re-probing a dead model.
 */

import type {
  CountTokensParameters,
  CountTokensResponse,
  EmbedContentParameters,
  EmbedContentResponse,
  GenerateContentParameters,
  GenerateContentResponse,
} from '@google/genai';
import type { ContentGenerator } from '../core/contentGenerator.js';
import type { LlmRole } from '../telemetry/llmRole.js';
import { getProvider } from './providers.js';
import { OpenAICompatContentGenerator } from './openaiCompatGenerator.js';
import type {
  FreeLLMCatalog,
  FreeModelsExhaustedError,
  formatFreeModelsExhaustedMessage,
  freeFallbackCandidates,
  isFreeRoutingFailure,
  type FallbackCandidate,
} from './freeCatalog.js';
import type { ModelRegistry } from './modelRegistry.js';

function generatorForCandidate(
  candidate: FallbackCandidate,
  env?: NodeJS.ProcessEnv,
): OpenAICompatContentGenerator | undefined {
  const provider = getProvider(candidate.provider);
  if (!provider) return undefined;
  return new OpenAICompatContentGenerator({
    modelId: candidate.model,
    provider,
    apiBase: candidate.apiBase,
    temperature: candidate.temperature,
    maxTokens: candidate.maxTokens,
    env,
  });
}

export class FreeFallbackContentGenerator implements ContentGenerator {
  private active: OpenAICompatContentGenerator;

  constructor(
    primary: OpenAICompatContentGenerator,
    private readonly env?: NodeJS.ProcessEnv,
    private readonly options: {
      registry?: ModelRegistry;
      catalog?: FreeLLMCatalog;
    } = {},
  ) {
    this.active = primary;
  }

  /** Full "provider/model" id of the generator currently answering. */
  get activeModelId(): string {
    return `${this.active.provider.id}/${this.active.model}`;
  }

  get model(): string {
    return this.active.model;
  }

  get apiBase(): string {
    return this.active.apiBase;
  }

  private async withFallback<T>(
    attempt: (generator: OpenAICompatContentGenerator) => Promise<T>,
  ): Promise<T> {
    try {
      return await attempt(this.active);
    } catch (primaryError) {
      if (!isFreeRoutingFailure(primaryError)) throw primaryError;
      const tried = [this.activeModelId];
      let lastError: unknown = primaryError;
      for (const candidate of freeFallbackCandidates(this.activeModelId, {
        env: this.env,
        registry: this.options.registry,
        catalog: this.options.catalog,
      })) {
        const generator = generatorForCandidate(candidate, this.env);
        if (!generator) continue;
        tried.push(candidate.model);
        try {
          const result = await attempt(generator);
          this.active = generator;
          return result;
        } catch (candidateError) {
          // Local servers that are down or further rate limits: move on.
          lastError = candidateError;
        }
      }
      throw new FreeModelsExhaustedError(
        formatFreeModelsExhaustedMessage(tried, lastError),
        tried,
        lastError,
      );
    }
  }

  async generateContent(
    request: GenerateContentParameters,
    userPromptId: string,
    role: LlmRole,
  ): Promise<GenerateContentResponse> {
    return this.withFallback((generator) =>
      generator.generateContent(request, userPromptId, role),
    );
  }

  async generateContentStream(
    request: GenerateContentParameters,
    userPromptId: string,
    role: LlmRole,
  ): Promise<AsyncGenerator<GenerateContentResponse>> {
    // The compat generator performs the HTTP request (where routing
    // failures surface) before returning the async generator, so
    // falling back here never drops already-yielded chunks.
    return this.withFallback((generator) =>
      generator.generateContentStream(request, userPromptId, role),
    );
  }

  async countTokens(
    request: CountTokensParameters,
  ): Promise<CountTokensResponse> {
    return this.active.countTokens(request);
  }

  async embedContent(
    request: EmbedContentParameters,
  ): Promise<EmbedContentResponse> {
    return this.active.embedContent(request);
  }
}

/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import type { ModelFamilyHint } from './types.js';

/**
 * Infer a coarse model family from a registry key or provider/model id.
 * Used only to badge “recommended” search backends in the wizard — not to
 * hard-code any user query topics.
 */
export function inferModelFamily(
  modelId: string | undefined | null,
): ModelFamilyHint {
  const m = (modelId ?? '').toLowerCase().trim();
  if (!m) return 'unknown';

  if (
    m.includes('ollama') ||
    m.includes('lmstudio') ||
    m.includes('local') ||
    m.startsWith('local-')
  ) {
    return 'local';
  }
  if (
    m.includes('gemini') ||
    m.includes('google/') ||
    m.startsWith('models/gemini')
  ) {
    return 'gemini';
  }
  if (
    m.includes('gpt-') ||
    m.includes('o1') ||
    m.includes('o3') ||
    m.includes('o4') ||
    m.includes('openai')
  ) {
    return 'openai';
  }
  if (m.includes('claude') || m.includes('anthropic')) {
    return 'anthropic';
  }
  // Free/open-weight hosts and OSS model names
  if (
    m.includes('openrouter') ||
    m.includes('groq') ||
    m.includes('cerebras') ||
    m.includes('deepseek') ||
    m.includes('llama') ||
    m.includes('qwen') ||
    m.includes('mistral') ||
    m.includes('gemma') ||
    m.includes('gpt-oss') ||
    m.includes('nemotron') ||
    m.includes('hf-') ||
    m.includes('huggingface') ||
    m.includes('together') ||
    m.includes('z-ai') ||
    m.includes('glm')
  ) {
    return 'open_source';
  }
  return 'unknown';
}

/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * OpenAgent default authentication resolution.
 *
 * Unlike Gemini CLI (Google / Gemini API key / Vertex first), OpenAgent
 * defaults to multi-provider BYOK + local models. The Gemini AuthDialog is
 * only for optional Google-family methods via /auth.
 */

import {
  AuthType,
  isMultiProviderModel,
  PROVIDERS,
  readCliEnvAlias,
  ENV_KEY_ALIASES,
} from '@open-agent/core';

function envHasKey(name: string, env: NodeJS.ProcessEnv): boolean {
  return Boolean(env[name]?.trim());
}

/**
 * True when any non-Gemini cloud key is set, or a local-only path is fine.
 * Local providers need no key; they always count as a multi-provider option.
 */
export function hasOpenAgentProviderPath(
  env: NodeJS.ProcessEnv = process.env,
): boolean {
  if (readCliEnvAlias('PROVIDER', env)) {
    return true;
  }
  for (const provider of PROVIDERS) {
    if (provider.id === 'gemini') continue;
    if (provider.local) {
      return true; // Ollama / LM Studio always an option
    }
    if (provider.envKey && envHasKey(provider.envKey, env)) {
      return true;
    }
    for (const alias of ENV_KEY_ALIASES[provider.id] ?? []) {
      if (envHasKey(alias, env)) return true;
    }
  }
  return false;
}

/**
 * Pick the default AuthType for OpenAgent startup when the user has not
 * chosen one (or when migrating off a stale gemini-api-key-only setting).
 */
export function resolveOpenAgentDefaultAuth(
  model: string | undefined,
  env: NodeJS.ProcessEnv = process.env,
): AuthType {
  // Explicit multi-provider pin from --provider / setup wizard.
  if (readCliEnvAlias('PROVIDER', env)) {
    return AuthType.MULTI_PROVIDER;
  }

  // Active / saved model is OpenRouter, NVIDIA, Groq, Ollama, …
  if (model && isMultiProviderModel(model)) {
    return AuthType.MULTI_PROVIDER;
  }

  // Any open-source / BYOK cloud key or local server path.
  if (hasOpenAgentProviderPath(env)) {
    return AuthType.MULTI_PROVIDER;
  }

  // Gemini-only key → native Gemini path.
  if (envHasKey('GEMINI_API_KEY', env) || envHasKey('GOOGLE_API_KEY', env)) {
    return AuthType.USE_GEMINI;
  }

  if (env['GOOGLE_GENAI_USE_GCA'] === 'true') {
    return AuthType.LOGIN_WITH_GOOGLE;
  }
  if (env['GOOGLE_GENAI_USE_VERTEXAI'] === 'true') {
    return AuthType.USE_VERTEX_AI;
  }

  // Default for OpenAgent: multi-provider (free/local/BYOK). Never force the
  // Gemini CLI Google/Vertex startup dialog.
  return AuthType.MULTI_PROVIDER;
}

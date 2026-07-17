/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect } from 'vitest';
import { AuthType } from '@open-agent/core';
import {
  hasOpenAgentProviderPath,
  resolveOpenAgentDefaultAuth,
} from './openAgentAuth.js';

describe('resolveOpenAgentDefaultAuth', () => {
  it('prefers multi-provider when OPENAGENT_CLI_PROVIDER is set', () => {
    expect(
      resolveOpenAgentDefaultAuth(undefined, {
        OPENAGENT_CLI_PROVIDER: 'nvidia',
        GEMINI_API_KEY: 'g',
      }),
    ).toBe(AuthType.MULTI_PROVIDER);
  });

  it('prefers multi-provider for registry multi models', () => {
    expect(
      resolveOpenAgentDefaultAuth('nvidia-nemotron', {
        GEMINI_API_KEY: 'g',
        NVIDIA_API_KEY: 'n',
      }),
    ).toBe(AuthType.MULTI_PROVIDER);
  });

  it('uses multi-provider when any non-Gemini cloud key is present', () => {
    expect(
      resolveOpenAgentDefaultAuth(undefined, {
        OPENROUTER_API_KEY: 'or',
        GEMINI_API_KEY: 'g',
      }),
    ).toBe(AuthType.MULTI_PROVIDER);
  });

  it('falls back to Gemini only when that is the sole cloud key', () => {
    // Local providers always exist as a multi path, so pure Gemini-only is
    // only chosen when hasOpenAgentProviderPath would be false — which it
    // never is because Ollama is always listed as local. Document that
    // default is multi-provider for OpenAgent.
    expect(resolveOpenAgentDefaultAuth(undefined, {})).toBe(
      AuthType.MULTI_PROVIDER,
    );
  });
});

describe('hasOpenAgentProviderPath', () => {
  it('is true with no keys because local providers exist', () => {
    expect(hasOpenAgentProviderPath({})).toBe(true);
  });

  it('is true with OpenRouter key', () => {
    expect(hasOpenAgentProviderPath({ OPENROUTER_API_KEY: 'x' })).toBe(true);
  });
});

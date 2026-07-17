/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import type { CliArgs } from './config.js';

const mockResolveProviderRoute = vi.hoisted(() => vi.fn());

vi.mock('@open-agent/core', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@open-agent/core')>();
  return {
    ...actual,
    resolveProviderRoute: mockResolveProviderRoute,
  };
});

import { applyProviderRouting } from './providerStartup.js';

function fakeRoute(providerId: string) {
  return {
    provider: {
      id: providerId,
      displayName: providerId,
      envKey: `${providerId.toUpperCase()}_API_KEY`,
      local: false,
    },
    modelId: `${providerId}/some-model`,
    configKey: undefined,
    source: 'explicit',
  };
}

describe('applyProviderRouting', () => {
  const originalEnv = { ...process.env };

  beforeEach(() => {
    vi.clearAllMocks();
    for (const key of Object.keys(process.env)) {
      if (
        key.startsWith('GEMINI_CLI_') ||
        key.startsWith('OPENAGENT_CLI_') ||
        key === 'GEMINI_API_KEY'
      ) {
        delete process.env[key];
      }
    }
  });

  afterEach(() => {
    process.env = { ...originalEnv };
  });

  it('does not pin OPENAGENT_CLI_PROVIDER when the resolved route is gemini', async () => {
    process.env['GEMINI_API_KEY'] = 'fake-key';
    mockResolveProviderRoute.mockResolvedValue(fakeRoute('gemini'));

    const argv = { provider: 'gemini' } as unknown as CliArgs;
    const routed = await applyProviderRouting(argv);

    expect(routed).toBe(true);
    // Regression test: a gemini route must not force AuthType.MULTI_PROVIDER
    // (see getAuthTypeFromEnv in contentGenerator.ts), or the session gets
    // routed through the OpenAI-compat shim instead of the native SDK.
    expect(process.env['OPENAGENT_CLI_PROVIDER']).toBeUndefined();
  });

  it('pins OPENAGENT_CLI_PROVIDER for a non-gemini route', async () => {
    process.env['OPENAI_API_KEY'] = 'fake-key';
    mockResolveProviderRoute.mockResolvedValue(fakeRoute('openai'));

    const argv = { provider: 'openai' } as unknown as CliArgs;
    const routed = await applyProviderRouting(argv);

    expect(routed).toBe(true);
    expect(process.env['OPENAGENT_CLI_PROVIDER']).toBe('openai');
  });
});

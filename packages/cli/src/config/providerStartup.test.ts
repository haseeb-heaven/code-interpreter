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

  it('routes from settings.model.name even when GEMINI_API_KEY is set', async () => {
    process.env['GEMINI_API_KEY'] = 'fake-gemini';
    process.env['NVIDIA_API_KEY'] = 'fake-nvidia';
    mockResolveProviderRoute.mockResolvedValue(fakeRoute('nvidia'));

    const argv = {} as unknown as CliArgs;
    const settings = {
      merged: { model: { name: 'nvidia-nemotron' }, general: {} },
      setValue: vi.fn(),
    };

    const routed = await applyProviderRouting(
      argv,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      settings as any,
    );

    expect(routed).toBe(true);
    expect(argv.model).toBe('nvidia/some-model');
    expect(process.env['OPENAGENT_CLI_PROVIDER']).toBe('nvidia');
    expect(mockResolveProviderRoute).toHaveBeenCalledWith(
      expect.objectContaining({ model: 'nvidia-nemotron' }),
    );
  });

  it('does not early-exit on GEMINI_API_KEY when no model is set (allows local auto)', async () => {
    // Without this regression, GEMINI_API_KEY alone skipped all routing and
    // the first-run wizard never ran for users who also use other providers.
    process.env['GEMINI_API_KEY'] = 'fake-gemini';
    mockResolveProviderRoute.mockResolvedValue(undefined);

    const argv = {} as unknown as CliArgs;
    const settings = {
      merged: { general: { setupWizardCompleted: true }, model: {} },
      setValue: vi.fn(),
    };

    const routed = await applyProviderRouting(
      argv,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      settings as any,
    );

    // Wizard already completed + Gemini key + no multi model → false (native)
    expect(routed).toBe(false);
  });
});

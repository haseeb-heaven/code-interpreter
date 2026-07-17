/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect, vi } from 'vitest';
import { renderWithProviders } from '../../test-utils/render.js';
import { AppHeader } from './AppHeader.js';
import { makeFakeConfig, AuthType } from '@open-agent/core';
import type { ContentGeneratorConfig } from '@open-agent/core';

describe('AppHeader Icon Rendering', () => {
  it('renders the OA block logo in standard terminals', async () => {
    const mockConfig = makeFakeConfig();
    vi.spyOn(mockConfig, 'getContentGeneratorConfig').mockReturnValue({
      authType: AuthType.USE_GEMINI,
      model: 'gemini-pro',
    } as unknown as ContentGeneratorConfig);

    const result = await renderWithProviders(<AppHeader version="4.0.0" />, {
      config: mockConfig,
      uiState: { terminalWidth: 120 },
    });
    await result.waitUntilReady();

    const frame = result.lastFrame() ?? '';
    expect(frame).toContain('██████╗');
    expect(frame).toContain('█████╗');
    expect(frame).toContain('OpenAgent');
    expect(frame).toContain('v4.0.0');
    // Triangle glyph logo should no longer appear.
    expect(frame).not.toContain('▝▜▄');
    result.unmount();
  });

  it('renders the OA logo when authenticated with a multi-provider model', async () => {
    const mockConfig = makeFakeConfig();
    vi.spyOn(mockConfig, 'getContentGeneratorConfig').mockReturnValue({
      authType: AuthType.MULTI_PROVIDER,
    } as unknown as ContentGeneratorConfig);
    vi.spyOn(mockConfig, 'getModel').mockReturnValue('openrouter/free');

    const result = await renderWithProviders(<AppHeader version="4.0.0" />, {
      config: mockConfig,
      uiState: { terminalWidth: 120 },
    });
    await result.waitUntilReady();

    const frame = result.lastFrame() ?? '';
    expect(frame).toContain('██████╗');
    expect(frame).toMatch(/Authenticated with .+ API key\./);
    expect(frame).not.toContain('gemini-api-key');
    expect(frame).not.toContain('multi-provider');
    result.unmount();
  });
});

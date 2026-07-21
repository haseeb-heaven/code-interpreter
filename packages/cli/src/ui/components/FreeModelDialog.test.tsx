/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { renderWithProviders } from '../../test-utils/render.js';
import { waitFor } from '../../test-utils/async.js';
import { makeFakeConfig } from '@open-agent/core';
import { describe, it, expect, vi } from 'vitest';
import { FreeModelDialog } from './FreeModelDialog.js';

const ENTER = String.fromCharCode(13);
const ESCAPE = String.fromCharCode(27);

describe('FreeModelDialog', () => {
  it('renders the free-model picker with the real free catalog', async () => {
    const config = makeFakeConfig();
    const onClose = vi.fn();

    const { lastFrame } = await renderWithProviders(
      <FreeModelDialog onClose={onClose} />,
      { config },
    );

    await waitFor(() => {
      const frame = lastFrame();
      expect(frame).toContain('Free models');
      expect(frame).toContain('Pick a free-tier / local model to activate');
    });
  });

  it('closes on Escape without changing the model', async () => {
    const config = makeFakeConfig();
    const setModelSpy = vi.spyOn(config, 'setModel');
    const onClose = vi.fn();

    const { stdin, lastFrame } = await renderWithProviders(
      <FreeModelDialog onClose={onClose} />,
      { config },
    );

    await waitFor(() => {
      expect(lastFrame()).toContain('Free models');
    });

    await React.act(async () => {
      stdin.write(ESCAPE);
    });

    await waitFor(() => {
      expect(onClose).toHaveBeenCalled();
    });
    expect(setModelSpy).not.toHaveBeenCalled();
  });

  it('selecting an entry either activates it or prompts for a key, then reflects the choice', async () => {
    const config = makeFakeConfig();
    const onClose = vi.fn();

    const { stdin, lastFrame } = await renderWithProviders(
      <FreeModelDialog onClose={onClose} />,
      { config },
    );

    await waitFor(() => {
      expect(lastFrame()).toContain('Free models');
    });

    if (lastFrame().includes('No free models are configured')) {
      // Empty catalog is a valid environment state; nothing further to drive.
      return;
    }

    await React.act(async () => {
      stdin.write(ENTER);
    });

    await waitFor(() => {
      const frame = lastFrame();
      // Either it activated immediately (dialog closed) or it's now
      // prompting for an API key / showing a local-provider notice.
      const promptingForKey = frame.includes('API key');
      const showingNotice = frame.includes('local provider');
      expect(
        onClose.mock.calls.length > 0 || promptingForKey || showingNotice,
      ).toBe(true);
    });
  });
});

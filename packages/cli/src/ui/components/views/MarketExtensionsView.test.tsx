/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { renderWithProviders } from '../../../test-utils/render.js';
import { waitFor } from '../../../test-utils/async.js';
import { makeFakeConfig } from '@open-agent/core';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  MarketExtensionsView,
  GEMINI_CLI_SOURCE,
  CLAUDE_CODE_SOURCE,
  CODEX_SOURCE,
} from './MarketExtensionsView.js';
import { type ExtensionManager } from '../../../config/extension-manager.js';
import { useExtensionRegistry } from '../../hooks/useExtensionRegistry.js';
import { useExtensionUpdates } from '../../hooks/useExtensionUpdates.js';
import { useRegistrySearch } from '../../hooks/useRegistrySearch.js';
import { type RegistryExtension } from '../../../config/extensionRegistryClient.js';
import { type UIState } from '../../contexts/UIStateContext.js';
import {
  type SearchListState,
  type GenericListItem,
} from '../shared/SearchableList.js';
import { type TextBuffer } from '../shared/text-buffer.js';
import { type UseHistoryManagerReturn } from '../../hooks/useHistoryManager.js';

const ENTER = String.fromCharCode(13);
const DOWN_ARROW = String.fromCharCode(27) + '[B';
const ESCAPE = String.fromCharCode(27);

vi.mock('../../hooks/useExtensionRegistry.js');
vi.mock('../../hooks/useExtensionUpdates.js');
vi.mock('../../hooks/useRegistrySearch.js');
vi.mock('../../../config/extension-manager.js');

const mockExtensions: RegistryExtension[] = [
  {
    id: 'ext1',
    extensionName: 'Test Extension 1',
    extensionDescription: 'Description 1',
    fullName: 'author/ext1',
    extensionVersion: '1.0.0',
    rank: 1,
    stars: 10,
    url: 'http://example.com',
    repoDescription: 'Repo Desc 1',
    avatarUrl: 'http://avatar.com',
    lastUpdated: '2023-01-01',
    hasMCP: false,
    hasContext: false,
    hasHooks: false,
    hasSkills: false,
    hasCustomCommands: false,
    isGoogleOwned: false,
    licenseKey: 'mit',
    registryName: 'Gemini CLI',
  },
];

describe('MarketExtensionsView', () => {
  let mockExtensionManager: ExtensionManager;
  let mockOnSelectExtension: ReturnType<typeof vi.fn>;
  let mockOnLinkExtension: ReturnType<typeof vi.fn>;
  let mockOnMarketSelected: ReturnType<typeof vi.fn>;
  let mockOnClose: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();

    mockExtensionManager = {
      getExtensions: vi.fn().mockReturnValue([]),
    } as unknown as ExtensionManager;

    mockOnSelectExtension = vi.fn();
    mockOnLinkExtension = vi.fn();
    mockOnMarketSelected = vi.fn();
    mockOnClose = vi.fn();

    vi.mocked(useExtensionRegistry).mockReturnValue({
      extensions: mockExtensions,
      loading: false,
      error: null,
      search: vi.fn(),
    });

    vi.mocked(useExtensionUpdates).mockReturnValue({
      extensionsUpdateState: new Map(),
      dispatchExtensionStateUpdate: vi.fn(),
    } as unknown as ReturnType<typeof useExtensionUpdates>);

    vi.mocked(useRegistrySearch).mockImplementation(
      (props: { items: GenericListItem[]; onSearch?: (q: string) => void }) =>
        ({
          filteredItems: props.items,
          searchBuffer: {
            text: '',
            cursorOffset: 0,
            viewport: { width: 10, height: 1 },
            visualCursor: [0, 0] as [number, number],
            viewportVisualLines: [{ text: '', visualRowIndex: 0 }],
            visualScrollRow: 0,
            lines: [''],
            cursor: [0, 0] as [number, number],
            selectionAnchor: undefined,
            handleInput: () => false,
          } as unknown as TextBuffer,
          searchQuery: '',
          setSearchQuery: vi.fn(),
          maxLabelWidth: 10,
        }) as unknown as SearchListState<GenericListItem>,
    );
  });

  const renderView = async () =>
    renderWithProviders(
      <MarketExtensionsView
        extensionManager={mockExtensionManager}
        allSources={[
          GEMINI_CLI_SOURCE,
          { name: 'Custom', uri: 'https://example.com/registry' },
        ]}
        onSelectExtension={mockOnSelectExtension}
        onLinkExtension={mockOnLinkExtension}
        onMarketSelected={mockOnMarketSelected}
        onClose={mockOnClose}
      />,
      {
        config: makeFakeConfig(),
        uiState: {
          staticExtraHeight: 5,
          terminalHeight: 40,
          historyManager: {
            addItem: vi.fn(),
          } as unknown as UseHistoryManagerReturn,
        } as Partial<UIState>,
      },
    );

  it('renders the market picker with all four options', async () => {
    const { lastFrame } = await renderView();

    await waitFor(() => {
      const frame = lastFrame();
      expect(frame).toContain('Extension marketplace');
      expect(frame).toContain('Gemini CLI');
      expect(frame).toContain('Claude Code');
      expect(frame).toContain('Codex');
      expect(frame).toContain('All markets');
    });
  });

  it('closes on Escape while the picker is showing', async () => {
    const { stdin } = await renderView();

    await waitFor(() => {
      expect(mockOnClose).not.toHaveBeenCalled();
    });

    await React.act(async () => {
      stdin.write(ESCAPE);
    });

    await waitFor(() => {
      expect(mockOnClose).toHaveBeenCalled();
    });
  });

  it('selecting Gemini CLI scopes the registry view to only that source', async () => {
    const { stdin, lastFrame } = await renderView();

    await waitFor(() => {
      expect(lastFrame()).toContain('Extension marketplace');
    });

    // First item (Gemini CLI) is preselected; Enter picks it.
    await React.act(async () => {
      stdin.write(ENTER);
    });

    await waitFor(() => {
      expect(useExtensionRegistry).toHaveBeenLastCalledWith('', [
        GEMINI_CLI_SOURCE,
      ]);
    });

    await waitFor(() => {
      expect(lastFrame()).toContain('Test Extension 1');
    });
  });

  it('selecting All markets passes every configured source through', async () => {
    const { stdin } = await renderView();

    await waitFor(() => undefined);

    // Down x3 to reach "All markets" (Gemini CLI, Claude Code, Codex, All markets)
    await React.act(async () => {
      stdin.write(DOWN_ARROW);
      stdin.write(DOWN_ARROW);
      stdin.write(DOWN_ARROW);
    });
    await React.act(async () => {
      stdin.write(ENTER);
    });

    await waitFor(() => {
      expect(useExtensionRegistry).toHaveBeenLastCalledWith('', [
        GEMINI_CLI_SOURCE,
        { name: 'Custom', uri: 'https://example.com/registry' },
      ]);
    });
  });

  it('selecting Claude Code scopes the registry view to only that source', async () => {
    const { stdin, lastFrame } = await renderView();

    await waitFor(() => {
      expect(lastFrame()).toContain('Extension marketplace');
    });

    // Gemini CLI (0), Claude Code (1).
    await React.act(async () => {
      stdin.write(DOWN_ARROW);
    });
    await React.act(async () => {
      stdin.write(ENTER);
    });

    await waitFor(() => {
      expect(useExtensionRegistry).toHaveBeenLastCalledWith('', [
        CLAUDE_CODE_SOURCE,
      ]);
    });

    expect(mockOnClose).not.toHaveBeenCalled();
  });

  it('selecting Codex scopes the registry view to only that source', async () => {
    const { stdin } = await renderView();

    await waitFor(() => undefined);

    // Gemini CLI (0), Claude Code (1), Codex (2).
    await React.act(async () => {
      stdin.write(DOWN_ARROW);
      stdin.write(DOWN_ARROW);
    });
    await React.act(async () => {
      stdin.write(ENTER);
    });

    await waitFor(() => {
      expect(useExtensionRegistry).toHaveBeenLastCalledWith('', [CODEX_SOURCE]);
    });

    expect(mockOnClose).not.toHaveBeenCalled();
  });

  it('calls onMarketSelected with the market id and resolved sources when a market is picked', async () => {
    const { stdin } = await renderView();

    await waitFor(() => undefined);

    await React.act(async () => {
      stdin.write(ENTER);
    });

    await waitFor(() => {
      expect(mockOnMarketSelected).toHaveBeenCalledWith('gemini-cli', [
        GEMINI_CLI_SOURCE,
      ]);
    });
  });
});

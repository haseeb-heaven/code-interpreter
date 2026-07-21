/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import type React from 'react';
import { useState } from 'react';
import { Box, Text } from 'ink';
import type { RegistrySource } from '@open-agent/core';
import type { RegistryExtension } from '../../../config/extensionRegistryClient.js';
import type { ExtensionManager } from '../../../config/extension-manager.js';
import { theme } from '../../semantic-colors.js';
import { useKeypress } from '../../hooks/useKeypress.js';
import { DescriptiveRadioButtonSelect } from '../shared/DescriptiveRadioButtonSelect.js';
import { ExtensionRegistryView } from './ExtensionRegistryView.js';

export type MarketId = 'gemini-cli' | 'claude-code' | 'codex' | 'all';

export const GEMINI_CLI_SOURCE: RegistrySource = {
  name: 'Gemini CLI',
  uri: 'https://geminicli.com/extensions.json',
};

export const CLAUDE_CODE_SOURCE: RegistrySource = {
  name: 'Claude Code',
  uri: 'https://raw.githubusercontent.com/anthropics/claude-plugins-official/main/.claude-plugin/marketplace.json',
};

export const CODEX_SOURCE: RegistrySource = {
  name: 'Codex',
  uri: 'https://www.codex-marketplace.com/api/plugins',
};

const MARKET_SOURCES: Record<Exclude<MarketId, 'all'>, RegistrySource> = {
  'gemini-cli': GEMINI_CLI_SOURCE,
  'claude-code': CLAUDE_CODE_SOURCE,
  codex: CODEX_SOURCE,
};

interface MarketExtensionsViewProps {
  extensionManager: ExtensionManager;
  allSources: RegistrySource[];
  onSelectExtension: (
    extension: RegistryExtension,
    requestConsentOverride?: (consent: string) => Promise<boolean>,
  ) => void | Promise<void>;
  onLinkExtension: (
    extension: RegistryExtension,
    requestConsentOverride?: (consent: string) => Promise<boolean>,
  ) => void | Promise<void>;
  /** Called as soon as a market is picked, so the selection can be persisted for future `/extensions` calls. */
  onMarketSelected?: (market: MarketId, sources: RegistrySource[]) => void;
  onClose: () => void;
}

interface MarketItem {
  key: string;
  title: string;
  description?: string;
  value: MarketId;
}

const MARKET_ITEMS: MarketItem[] = [
  {
    key: 'gemini-cli',
    title: 'Gemini CLI',
    description: 'geminicli.com/extensions — browse & install in this view',
    value: 'gemini-cli',
  },
  {
    key: 'claude-code',
    title: 'Claude Code',
    description:
      'github.com/anthropics/claude-plugins-official — browse & install in this view',
    value: 'claude-code',
  },
  {
    key: 'codex',
    title: 'Codex',
    description:
      'codex-marketplace.com/api/plugins — browse & install in this view',
    value: 'codex',
  },
  {
    key: 'all',
    title: 'All markets',
    description: 'Search every configured registry at the same time',
    value: 'all',
  },
];

export function MarketExtensionsView({
  extensionManager,
  allSources,
  onSelectExtension,
  onLinkExtension,
  onMarketSelected,
  onClose,
}: MarketExtensionsViewProps): React.JSX.Element {
  const [selectedMarket, setSelectedMarket] = useState<MarketId | null>(null);

  useKeypress(
    (key) => {
      if (key.name !== 'escape') return false;
      if (selectedMarket === null) {
        onClose();
        return true;
      }
      return false;
    },
    { isActive: selectedMarket === null },
  );

  const handleSelectMarket = (market: MarketId) => {
    const sources = market === 'all' ? allSources : [MARKET_SOURCES[market]];
    setSelectedMarket(market);
    onMarketSelected?.(market, sources);
  };

  if (selectedMarket === null) {
    return (
      <Box
        borderStyle="round"
        borderColor={theme.ui.focus}
        flexDirection="column"
        padding={1}
        width="100%"
      >
        <Box>
          <Text color={theme.text.accent}>? </Text>
          <Text bold color={theme.text.primary}>
            Extension marketplace
          </Text>
        </Box>
        <Box marginTop={1}>
          <Text color={theme.text.primary}>
            Pick a marketplace to browse for extensions
          </Text>
        </Box>
        <Box marginTop={1}>
          <DescriptiveRadioButtonSelect
            items={MARKET_ITEMS}
            onSelect={handleSelectMarket}
            showNumbers={true}
          />
        </Box>
        <Box marginTop={1}>
          <Text color={theme.text.secondary}>
            (Use Enter to select · Esc to close)
          </Text>
        </Box>
      </Box>
    );
  }

  const sources =
    selectedMarket === 'all' ? allSources : [MARKET_SOURCES[selectedMarket]];

  return (
    <ExtensionRegistryView
      extensionManager={extensionManager}
      sources={sources}
      onSelect={onSelectExtension}
      onLink={onLinkExtension}
      onClose={onClose}
    />
  );
}

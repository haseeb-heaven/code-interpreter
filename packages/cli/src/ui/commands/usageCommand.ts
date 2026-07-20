/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import {
  getProvider,
  getProviderUsage,
  fetchOpenRouterCredits,
} from '@open-agent/core';
import {
  type CommandContext,
  CommandKind,
  type SlashCommand,
} from './types.js';
import {
  MessageType,
  type UsageProviderRow,
  type HistoryItemUsageStats,
} from '../types.js';

export const usageCommand: SlashCommand = {
  name: 'usage',
  description: 'Show accumulated token usage per provider, across sessions',
  kind: CommandKind.BUILT_IN,
  action: async (context: CommandContext): Promise<void> => {
    try {
      const store = getProviderUsage();
      const providers: UsageProviderRow[] = Object.keys(store).map(
        (providerId) => {
          const entry = store[providerId];
          return {
            id: providerId,
            displayName: getProvider(providerId)?.displayName ?? providerId,
            requestCount: entry.requestCount,
            promptTokens: entry.promptTokens,
            completionTokens: entry.completionTokens,
            totalTokens: entry.totalTokens,
            lastUsedAt: entry.lastUsedAt,
          };
        },
      );

      const openRouterApiKey = process.env['OPENROUTER_API_KEY'];
      const hasOpenRouterUsage = 'openrouter' in store;
      const openRouterCredits =
        hasOpenRouterUsage && openRouterApiKey
          ? await fetchOpenRouterCredits(openRouterApiKey)
          : undefined;

      context.ui.addItem(
        {
          type: MessageType.USAGE_STATS,
          providers,
          openRouterCredits,
          openRouterKeyMissing: hasOpenRouterUsage && !openRouterApiKey,
        } as HistoryItemUsageStats,
        Date.now(),
      );
    } catch (error) {
      context.ui.addItem(
        {
          type: MessageType.ERROR,
          text: error instanceof Error ? error.message : String(error),
        },
        Date.now(),
      );
    }
  },
};

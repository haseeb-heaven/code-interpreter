/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import {
  getProvider,
  getProviderUsage,
  fetchOpenRouterCredits,
  type ProviderUsageStore,
} from '@open-agent/core';
import {
  type CommandContext,
  CommandKind,
  type SlashCommand,
} from './types.js';
import { MessageType } from '../types.js';

async function usageTable(
  store: ProviderUsageStore,
  env: NodeJS.ProcessEnv,
): Promise<string> {
  const providerIds = Object.keys(store).sort();
  if (providerIds.length === 0) {
    return 'No provider usage recorded yet. Usage accumulates as you use the CLI.';
  }

  const lines = ['Cross-provider usage (accumulated across sessions):', ''];
  for (const providerId of providerIds) {
    const entry = store[providerId];
    const displayName = getProvider(providerId)?.displayName ?? providerId;
    lines.push(`${displayName}`);
    lines.push(
      `  requests: ${entry.requestCount}   tokens: ${entry.totalTokens} (prompt ${entry.promptTokens} / completion ${entry.completionTokens})`,
    );
    lines.push(`  last used: ${entry.lastUsedAt || 'unknown'}`);

    if (providerId === 'openrouter') {
      const apiKey = env['OPENROUTER_API_KEY'];
      const credits = apiKey ? await fetchOpenRouterCredits(apiKey) : undefined;
      if (credits) {
        lines.push(
          `  remaining balance: ${(credits.remainingFraction * 100).toFixed(1)}% (${(
            credits.totalCredits - credits.totalUsage
          ).toFixed(2)} of ${credits.totalCredits.toFixed(2)} credits)`,
        );
      } else {
        lines.push(
          '  remaining balance: unavailable (set OPENROUTER_API_KEY, or the credits API is unreachable)',
        );
      }
    } else if (providerId === 'openai' || providerId === 'anthropic') {
      lines.push(
        '  remaining balance: not available via API — showing accumulated local usage only',
      );
    }
    lines.push('');
  }
  return lines.join('\n').trimEnd();
}

export const usageCommand: SlashCommand = {
  name: 'usage',
  description: 'Show accumulated token usage per provider, across sessions',
  kind: CommandKind.BUILT_IN,
  action: async (context: CommandContext): Promise<void> => {
    try {
      const store = getProviderUsage();
      const text = await usageTable(store, process.env);
      context.ui.addItem({ type: MessageType.INFO, text }, Date.now());
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

/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import * as path from 'node:path';
import {
  byokProvider,
  byokProviders,
  newlyAvailableModels,
  writeEnvKey,
} from '@open-agent/core';
import {
  type CommandContext,
  CommandKind,
  type SlashCommand,
} from './types.js';
import { MessageType } from '../types.js';

function providerTable(env: NodeJS.ProcessEnv): string {
  const lines = [
    'Bring your own key — add a provider API key to .env:',
    '',
    '  /byok <provider> <api-key>',
    '',
    'Providers:',
  ];
  for (const provider of byokProviders()) {
    const set =
      provider.envKey && env[provider.envKey] ? '✓ key set' : '✗ no key';
    lines.push(
      `  ${provider.id.padEnd(12)} ${String(provider.envKey).padEnd(20)} ${set}`,
    );
  }
  lines.push('');
  lines.push('Local providers (Ollama, LM Studio) need no key.');
  return lines.join('\n');
}

export const byokCommand: SlashCommand = {
  name: 'byok',
  description:
    'Add a provider API key: /byok lists providers; /byok <provider> <key> saves the key to .env',
  kind: CommandKind.BUILT_IN,
  autoExecute: false,
  action: async (context: CommandContext, args: string): Promise<void> => {
    const parts = args.trim().split(/\s+/).filter(Boolean);

    if (parts.length === 0) {
      context.ui.addItem(
        { type: MessageType.INFO, text: providerTable(process.env) },
        Date.now(),
      );
      return;
    }

    if (parts.length !== 2) {
      context.ui.addItem(
        {
          type: MessageType.ERROR,
          text: 'Usage: /byok <provider> <api-key>  (or /byok to list providers)',
        },
        Date.now(),
      );
      return;
    }

    const [providerId, apiKey] = parts;
    try {
      const provider = byokProvider(providerId);
      const envKey = String(provider.envKey);
      const envPath = path.join(process.cwd(), '.env');
      writeEnvKey(envPath, envKey, apiKey);
      process.env[envKey] = apiKey;

      const unlocked = newlyAvailableModels(envKey);
      const unlockedText =
        unlocked.length > 0
          ? `Newly available models:\n${unlocked.map((m) => `  • ${m}`).join('\n')}`
          : 'No catalog presets were waiting on this key, but the provider is now usable.';
      context.ui.addItem(
        {
          type: MessageType.INFO,
          text: `Saved ${envKey} to ${envPath}.\n${unlockedText}`,
        },
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

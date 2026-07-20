/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import {
  FreeLLMCatalog,
  getModelRegistry,
  isEntryAvailable,
} from '@open-agent/core';
import {
  type CommandContext,
  CommandKind,
  type SlashCommand,
} from './types.js';
import {
  MessageType,
  type FreeModelsListRow,
  type HistoryItemFreeModelsList,
} from '../types.js';

export const freeModelsCommand: SlashCommand = {
  name: 'free-models',
  description: 'List all free models available in the catalog',
  kind: CommandKind.BUILT_IN,
  action: async (context: CommandContext): Promise<void> => {
    try {
      const registry = getModelRegistry();
      const catalog = FreeLLMCatalog.load(registry);
      const entries: FreeModelsListRow[] = catalog.entries.map((entry) => ({
        id: entry.id,
        provider: entry.provider,
        tier: entry.tier,
        available: isEntryAvailable(entry, process.env),
        notes: entry.notes,
      }));

      context.ui.addItem(
        {
          type: MessageType.FREE_MODELS_LIST,
          entries,
        } as HistoryItemFreeModelsList,
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

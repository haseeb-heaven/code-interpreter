/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import {
  FreeLLMCatalog,
  getModelRegistry,
  ModelSlashCommandEvent,
  logModelSlashCommand,
} from '@open-agent/core';
import {
  type CommandContext,
  CommandKind,
  type SlashCommand,
} from './types.js';
import { MessageType } from '../types.js';

export const freeCommand: SlashCommand = {
  name: 'free',
  description: 'Randomly select and activate an available free model',
  kind: CommandKind.BUILT_IN,
  autoExecute: true,
  action: async (context: CommandContext): Promise<void> => {
    try {
      const registry = getModelRegistry();
      const catalog = FreeLLMCatalog.load(registry);
      const available = catalog.available(process.env, registry);

      if (available.length === 0) {
        context.ui.addItem(
          {
            type: MessageType.ERROR,
            text: 'No free model is currently available. Set an API key for one of the free-catalog providers, or run a local model (Ollama/LM Studio), then try again.',
          },
          Date.now(),
        );
        return;
      }

      const picked = available[Math.floor(Math.random() * available.length)];

      if (context.services.agentContext?.config) {
        context.services.agentContext.config.setModel(picked.config, true);
        const event = new ModelSlashCommandEvent(picked.config);
        logModelSlashCommand(context.services.agentContext.config, event);
      }

      context.ui.addItem(
        {
          type: MessageType.INFO,
          text: `Selected free model: ${picked.id} (${picked.provider}, ${picked.tier})`,
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

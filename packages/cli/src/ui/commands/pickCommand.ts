/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import {
  ModelRegistry,
  formatPickerGroups,
  groupModelsByProvider,
  isLMStudioRunning,
  isOllamaRunning,
  listLMStudioModels,
  listOllamaModels,
} from '@google/gemini-cli-core';
import {
  type CommandContext,
  CommandKind,
  type SlashCommand,
} from './types.js';
import { MessageType } from '../types.js';

/** Detects live local servers and returns their model lists. */
async function detectLocalModels(): Promise<{
  ollama?: string[];
  lmstudio?: string[];
}> {
  const detected: { ollama?: string[]; lmstudio?: string[] } = {};
  const [ollamaUp, lmStudioUp] = await Promise.all([
    isOllamaRunning(),
    isLMStudioRunning(),
  ]);
  if (ollamaUp) detected.ollama = await listOllamaModels();
  if (lmStudioUp) detected.lmstudio = await listLMStudioModels();
  return detected;
}

export const pickCommand: SlashCommand = {
  name: 'pick',
  description:
    'Pick a model: /pick lists all models grouped by provider; /pick <name> switches to one',
  kind: CommandKind.BUILT_IN,
  autoExecute: true,
  action: async (context: CommandContext, args: string): Promise<void> => {
    const registry = ModelRegistry.load();
    const wanted = args.trim();

    if (wanted) {
      const key = registry.resolveModelKey(wanted) ?? wanted;
      const cfg = registry.getModel(key);
      const modelId = cfg?.model ?? key;
      if (context.services.agentContext?.config) {
        context.services.agentContext.config.setModel(modelId, true);
        context.ui.addItem(
          { type: MessageType.INFO, text: `Model set to ${modelId}` },
          Date.now(),
        );
      } else {
        context.ui.addItem(
          { type: MessageType.ERROR, text: 'No active session config.' },
          Date.now(),
        );
      }
      return;
    }

    const detected = await detectLocalModels();
    const groups = groupModelsByProvider({
      registry,
      detectedLocalModels: detected,
    });
    context.ui.addItem(
      { type: MessageType.INFO, text: formatPickerGroups(groups) },
      Date.now(),
    );
  },
};

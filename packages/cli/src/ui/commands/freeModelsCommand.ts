/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { CommandKind, type SlashCommand } from './types.js';

export const freeModelsCommand: SlashCommand = {
  name: 'free-models',
  description: 'Pick and activate a free-tier / local model',
  kind: CommandKind.BUILT_IN,
  autoExecute: true,
  action: async () => ({
    type: 'dialog',
    dialog: 'free-model',
  }),
};

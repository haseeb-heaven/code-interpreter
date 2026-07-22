/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import { type VariableSchema, VARIABLE_SCHEMA } from './variableSchema.js';
import { OPENAGENT_DIR } from '@open-agent/core';

/**
 * Represents a set of keys that will be considered invalid while unmarshalling
 * JSON in recursivelyHydrateStrings.
 */
const UNMARSHALL_KEY_IGNORE_LIST: Set<string> = new Set<string>([
  '__proto__',
  'constructor',
  'prototype',
]);

/** User extensions live under `~/.openagent/extensions` (not `.gemini`). */
export const EXTENSIONS_DIRECTORY_NAME = path.join(OPENAGENT_DIR, 'extensions');

/**
 * Extension manifest filename. New extensions write `EXTENSIONS_CONFIG_FILENAME`;
 * discovery also accepts the legacy gemini-cli name so extensions installed
 * before the rebrand keep loading.
 */
export const EXTENSIONS_CONFIG_FILENAME = 'open-agent-extension.json';
export const LEGACY_EXTENSIONS_CONFIG_FILENAME = 'gemini-extension.json';
/**
 * Claude Code plugin manifest, living at `.claude-plugin/plugin.json` inside
 * a plugin directory. Recognized last so OpenAgent / legacy Gemini-CLI
 * manifests always win when both are present, but a plugin-structured source
 * (e.g. the anthropics/claude-plugins-official marketplace) loads cleanly
 * instead of failing with "Configuration file not found".
 */
export const CLAUDE_PLUGIN_CONFIG_FILENAME = path.join(
  '.claude-plugin',
  'plugin.json',
);
export const EXTENSIONS_CONFIG_FILENAMES = [
  EXTENSIONS_CONFIG_FILENAME,
  LEGACY_EXTENSIONS_CONFIG_FILENAME,
  CLAUDE_PLUGIN_CONFIG_FILENAME,
];

export const INSTALL_METADATA_FILENAME = '.open-agent-extension-install.json';
export const LEGACY_INSTALL_METADATA_FILENAME =
  '.gemini-extension-install.json';
export const INSTALL_METADATA_FILENAMES = [
  INSTALL_METADATA_FILENAME,
  LEGACY_INSTALL_METADATA_FILENAME,
];

export const EXTENSION_SETTINGS_FILENAME = '.env';

/**
 * Resolves the path to a file within `dir` that may exist under either the
 * current name or a legacy fallback name, preferring `candidates[0]`.
 * If none of the candidates exist on disk yet, returns `candidates[0]`'s
 * path (the name a fresh write should use).
 */
export function resolveExistingOrDefaultPath(
  dir: string,
  candidates: readonly string[],
): string {
  for (const name of candidates) {
    const candidatePath = path.join(dir, name);
    if (fs.existsSync(candidatePath)) {
      return candidatePath;
    }
  }
  return path.join(dir, candidates[0]);
}

export type JsonObject = { [key: string]: JsonValue };
export type JsonArray = JsonValue[];
export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonObject
  | JsonArray;

export type VariableContext = {
  [key: string]: string | undefined;
};

export function validateVariables(
  variables: VariableContext,
  schema: VariableSchema,
) {
  for (const key in schema) {
    const definition = schema[key];
    if (definition.required && !variables[key]) {
      throw new Error(`Missing required variable: ${key}`);
    }
  }
}

export function hydrateString(str: string, context: VariableContext): string {
  validateVariables(context, VARIABLE_SCHEMA);
  const regex = /\${(.*?)}/g;
  return str.replace(regex, (match, key) => {
    const val = context[key];
    return val == null ? match : String(val);
  });
}

export function recursivelyHydrateStrings<T>(
  obj: T,
  values: VariableContext,
): T {
  if (typeof obj === 'string') {
    // eslint-disable-next-line @typescript-eslint/no-unsafe-type-assertion
    return hydrateString(obj, values) as unknown as T;
  }
  if (Array.isArray(obj)) {
    // eslint-disable-next-line @typescript-eslint/no-unsafe-type-assertion
    return (obj as unknown[]).map((item) =>
      recursivelyHydrateStrings(item, values),
    ) as unknown as T;
  }
  if (typeof obj === 'object' && obj !== null) {
    const newObj: Record<string, unknown> = {};
    for (const key in obj) {
      if (
        !UNMARSHALL_KEY_IGNORE_LIST.has(key) &&
        Object.prototype.hasOwnProperty.call(obj, key)
      ) {
        newObj[key] = recursivelyHydrateStrings(
          // eslint-disable-next-line @typescript-eslint/no-unsafe-type-assertion
          (obj as Record<string, unknown>)[key],
          values,
        );
      }
    }
    // eslint-disable-next-line @typescript-eslint/no-unsafe-type-assertion
    return newObj as T;
  }
  return obj;
}

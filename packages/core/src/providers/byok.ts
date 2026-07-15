/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * BYOK (bring your own key) support: writes provider API keys to a
 * `.env` file and reports which models become newly available.
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import {
  PROVIDERS,
  getProvider,
  type ProviderDefinition,
} from './providers.js';
import { FreeLLMCatalog } from './freeCatalog.js';
import { ModelRegistry } from './modelRegistry.js';

/** Cloud providers that accept a BYOK key, in walkthrough order. */
export function byokProviders(): ProviderDefinition[] {
  return PROVIDERS.filter((p) => !p.local && p.envKey !== null);
}

/**
 * Writes (or replaces) `KEY=value` in the `.env` file at `envPath`,
 * preserving every other line. Creates the file when missing. Returns
 * the env var name that was written.
 */
export function writeEnvKey(
  envPath: string,
  envKey: string,
  value: string,
): string {
  const key = envKey.trim();
  if (!/^[A-Z][A-Z0-9_]*$/.test(key)) {
    throw new Error(`Invalid environment variable name: ${envKey}`);
  }
  const cleanValue = value.trim();
  if (!cleanValue) {
    throw new Error('API key value must not be empty');
  }
  if (/[\r\n]/.test(cleanValue)) {
    throw new Error('API key value must not contain newlines');
  }

  let lines: string[] = [];
  try {
    lines = fs.readFileSync(envPath, 'utf8').split(/\r?\n/);
  } catch {
    // Missing file: start fresh.
  }

  const assignment = `${key}=${cleanValue}`;
  let replaced = false;
  const next = lines.map((line) => {
    const match = /^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=/.exec(line);
    if (match && match[1] === key && !replaced) {
      replaced = true;
      return assignment;
    }
    return line;
  });
  while (next.length > 0 && next[next.length - 1] === '') next.pop();
  if (!replaced) {
    next.push(assignment);
  }

  fs.mkdirSync(path.dirname(path.resolve(envPath)), { recursive: true });
  fs.writeFileSync(envPath, next.join('\n') + '\n', { mode: 0o600 });
  return key;
}

/**
 * Registry model keys that become available with `envKey` set, i.e.
 * models unusable before but usable after. Availability is derived from
 * the provider tag / env requirements of the free catalog and the
 * provider definitions.
 */
export function newlyAvailableModels(
  envKey: string,
  options: {
    registry?: ModelRegistry;
    catalog?: FreeLLMCatalog;
    env?: NodeJS.ProcessEnv;
  } = {},
): string[] {
  const registry = options.registry ?? ModelRegistry.load();
  const catalog = options.catalog ?? FreeLLMCatalog.load(registry);
  const baseEnv = options.env ?? process.env;

  const before: NodeJS.ProcessEnv = { ...baseEnv };
  delete before[envKey];
  const after: NodeJS.ProcessEnv = { ...baseEnv, [envKey]: 'set' };

  const availableBefore = new Set(
    catalog.available(before, registry).map((e) => e.config),
  );
  const models = catalog
    .available(after, registry)
    .map((e) => e.config)
    .filter((config) => !availableBefore.has(config));
  return [...new Set(models)];
}

/** Resolves a provider by id for the BYOK flow, throwing on unknowns. */
export function byokProvider(providerId: string): ProviderDefinition {
  const provider = getProvider(providerId);
  if (!provider) {
    const known = byokProviders()
      .map((p) => p.id)
      .join(', ');
    throw new Error(`Unknown provider "${providerId}". Known: ${known}`);
  }
  if (provider.local || !provider.envKey) {
    throw new Error(`Provider "${provider.id}" is local and needs no API key.`);
  }
  return provider;
}

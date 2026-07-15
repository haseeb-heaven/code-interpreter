/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Startup handling for the multi-provider flags:
 *
 *   --pick       print every model grouped by provider, then exit
 *   --byok       interactive walkthrough that saves API keys to .env
 *   --provider   pin a provider (ollama, lmstudio, openai, groq, ...)
 *   --free       prefer free presets from configs/models.toml
 *
 * With none of these set and no explicit model, Ollama at
 * localhost:11434 is probed first and used automatically when running.
 */

import * as path from 'node:path';
import * as readline from 'node:readline/promises';
import {
  ModelRegistry,
  byokProviders,
  formatPickerGroups,
  groupModelsByProvider,
  isLMStudioRunning,
  isMultiProviderModel,
  isOllamaRunning,
  listLMStudioModels,
  listOllamaModels,
  newlyAvailableModels,
  resolveProviderRoute,
  writeEnvKey,
} from '@google/gemini-cli-core';
import type { CliArgs } from './config.js';

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

/** Renders the picker to stdout (used by --pick). */
export async function printModelPicker(): Promise<void> {
  const registry = ModelRegistry.load();
  const detected = await detectLocalModels();
  const groups = groupModelsByProvider({
    registry,
    detectedLocalModels: detected,
  });
  process.stdout.write(formatPickerGroups(groups) + '\n');
}

/** Interactive BYOK walkthrough (used by --byok). */
export async function runByokWalkthrough(): Promise<void> {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });
  const envPath = path.join(process.cwd(), '.env');
  try {
    process.stdout.write(
      'Bring your own key: press Enter to skip a provider, Ctrl+C to stop.\n' +
        `Keys are written to ${envPath}\n\n`,
    );
    for (const provider of byokProviders()) {
      const envKey = String(provider.envKey);
      const existing = process.env[envKey] ? ' (already set)' : '';
      const answer = (
        await rl.question(`${provider.displayName} ${envKey}${existing}: `)
      ).trim();
      if (!answer) continue;
      writeEnvKey(envPath, envKey, answer);
      process.env[envKey] = answer;
      const unlocked = newlyAvailableModels(envKey);
      process.stdout.write(
        unlocked.length > 0
          ? `  Newly available models: ${unlocked.join(', ')}\n`
          : '  Key saved.\n',
      );
    }
    process.stdout.write('\nDone. Run with --pick to see all models.\n');
  } finally {
    rl.close();
  }
}

/**
 * Applies --provider / --free / local auto-detection to the parsed args.
 * Mutates `argv.model` to the resolved LiteLLM-style id and marks the
 * process for multi-provider auth via GEMINI_CLI_PROVIDER. Returns true
 * when a multi-provider route was installed.
 */
export async function applyProviderRouting(argv: CliArgs): Promise<boolean> {
  const wantsRouting =
    Boolean(argv.provider) ||
    Boolean(argv.free) ||
    (argv.model !== undefined && isMultiProviderModel(argv.model));

  // Without explicit routing flags, only auto-route when nothing Google
  // is configured (Ollama-first default for key-less local runs).
  const googleConfigured = Boolean(
    process.env['GEMINI_API_KEY'] ||
      process.env['GOOGLE_API_KEY'] ||
      process.env['GOOGLE_GENAI_USE_GCA'] ||
      process.env['GOOGLE_GENAI_USE_VERTEXAI'],
  );
  if (!wantsRouting && (argv.model !== undefined || googleConfigured)) {
    return false;
  }

  const route = await resolveProviderRoute({
    model: argv.model,
    provider: argv.provider,
    free: argv.free,
  });
  if (!route) {
    if (argv.provider || argv.free) {
      process.stderr.write(
        'No usable provider route found. Is the local server running / the API key set? ' +
          'Try --pick to list models or --byok to add keys.\n',
      );
    }
    return false;
  }

  argv.model = route.modelId;
  process.env['GEMINI_CLI_PROVIDER'] = route.provider.id;
  return true;
}

/**
 * Entry point called from gemini.tsx right after argument parsing.
 * Handles --pick / --byok (both exit) and installs provider routing.
 */
export async function handleProviderStartupFlags(argv: CliArgs): Promise<void> {
  if (argv.pick) {
    await printModelPicker();
    process.exit(0);
  }
  if (argv.byok) {
    await runByokWalkthrough();
    process.exit(0);
  }
  await applyProviderRouting(argv);
}

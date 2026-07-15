/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Startup handling for the multi-provider flags:
 *
 *   --models     print every model grouped by provider, then exit
 *   --byok       interactive walkthrough that saves API keys to .env
 *   --provider   pin a provider (ollama, lmstudio, openai, groq, ...)
 *   --free       prefer free presets from configs/models.toml
 *
 * With none of these set and no explicit model, Ollama at
 * localhost:11434 is probed first and used automatically when running.
 */

import * as path from 'node:path';
import * as readline from 'node:readline/promises';
import { Writable } from 'node:stream';
import {
  writeToStdout,
  writeToStderr,
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

/** Renders the picker to stdout (used by --models). */
export async function printModelPicker(): Promise<void> {
  const registry = ModelRegistry.load();
  const detected = await detectLocalModels();
  const groups = groupModelsByProvider({
    registry,
    detectedLocalModels: detected,
  });
  // main() patches process.stdout before argv handling, so plain
  // process.stdout.write is swallowed; write to the real stream and wait
  // for the flush because process.exit(0) follows immediately.
  await new Promise<void>((resolve) => {
    writeToStdout(formatPickerGroups(groups) + '\n', undefined, () =>
      resolve(),
    );
  });
}

/** Interactive BYOK walkthrough (used by --byok). */
export async function runByokWalkthrough(): Promise<void> {
  // Route readline's prompts around the patched process.stdout (see
  // printModelPicker) so the walkthrough stays visible.
  const realStdout = new Writable({
    write(chunk, _encoding, callback) {
      writeToStdout(chunk);
      callback();
    },
  });
  const rl = readline.createInterface({
    input: process.stdin,
    output: realStdout,
  });
  const envPath = path.join(process.cwd(), '.env');
  try {
    writeToStdout(
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
      writeToStdout(
        unlocked.length > 0
          ? `  Newly available models: ${unlocked.join(', ')}\n`
          : '  Key saved.\n',
      );
    }
    writeToStdout('\nDone. Run with --models to see all models.\n');
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
      writeToStderr(
        'No usable provider route found. Is the local server running / the API key set? ' +
          'Try --models to list models or --byok to add keys.\n',
      );
    }
    return false;
  }

  // Registry keys are unique; LiteLLM ids can be shared by alias entries
  // and would lose the api_base/provider overrides on re-resolution.
  argv.model = route.configKey ?? route.modelId;
  process.env['GEMINI_CLI_PROVIDER'] = route.provider.id;
  if (argv.free) {
    // Arms the runtime free-model fallback chain in the generator factory.
    process.env['GEMINI_CLI_FREE'] = '1';
  }
  return true;
}

/**
 * Entry point called from gemini.tsx right after argument parsing.
 * Handles --models / --byok (both exit) and installs provider routing.
 */
export async function handleProviderStartupFlags(argv: CliArgs): Promise<void> {
  if (argv.models) {
    await printModelPicker();
    process.exit(0);
  }
  if (argv.byok) {
    await runByokWalkthrough();
    process.exit(0);
  }
  await applyProviderRouting(argv);
}

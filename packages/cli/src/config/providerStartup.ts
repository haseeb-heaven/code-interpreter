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

import * as readline from 'node:readline/promises';
import { Writable } from 'node:stream';
import {
  AuthType,
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
  getDefaultEnvFilePath,
  ENV_KEY_ALIASES,
} from '@open-agent/core';
import type { CliArgs } from './config.js';
import { SettingScope, type LoadedSettings } from './settings.js';

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
  const envPath = getDefaultEnvFilePath();
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
 * process for multi-provider auth via OPENAGENT_CLI_PROVIDER. Returns true
 * when a multi-provider route was installed.
 */
function isNonInteractiveTestEnv(): boolean {
  return Boolean(process.env['VITEST']) || process.env['NODE_ENV'] === 'test';
}

/**
 * Env flag: open the Ink multi-model picker (ProviderModelDialog) on UI start.
 * Replaces the old single-line "Enter NVIDIA API key:" console prompt and the
 * numbered readline setup wizard — same TUI as /model.
 */
export const OPEN_MODEL_SETUP_ENV = 'OPENAGENT_CLI_OPEN_MODEL_DIALOG';

export function requestModelSetupUi(): void {
  process.env[OPEN_MODEL_SETUP_ENV] = '1';
}

export function shouldOpenModelSetupOnStart(): boolean {
  return process.env[OPEN_MODEL_SETUP_ENV] === '1';
}

export function clearModelSetupUiRequest(): void {
  delete process.env[OPEN_MODEL_SETUP_ENV];
}

export async function applyProviderRouting(
  argv: CliArgs,
  settings?: LoadedSettings,
): Promise<boolean> {
  // Honor the last model saved in settings when the CLI didn't pass -m/--model.
  // Without this, a session on nvidia-nemotron still starts as Gemini auth
  // because only GEMINI_API_KEY was present in the environment.
  if (argv.model === undefined || argv.model === '') {
    const saved = settings?.merged?.model?.name;
    if (typeof saved === 'string' && saved.trim()) {
      argv.model = saved.trim();
    }
  }

  const wantsRouting =
    Boolean(argv.provider) ||
    Boolean(argv.free) ||
    (argv.model !== undefined && isMultiProviderModel(String(argv.model)));

  // First-run / no model: open the Ink multi-model picker (same UI as /model),
  // not a console single-key textbox and not the Gemini auth dialog.
  const isFirstRunCandidate =
    !argv.provider &&
    !argv.free &&
    (argv.model === undefined || argv.model === '') &&
    Boolean(process.stdin.isTTY) &&
    settings !== undefined &&
    !settings.merged.general?.setupWizardCompleted &&
    !isNonInteractiveTestEnv();

  if (isFirstRunCandidate && settings) {
    requestModelSetupUi();
    settings.setValue(SettingScope.User, 'general.setupWizardCompleted', true);
    // Multi-provider auth so the app boots; user picks model+key in the TUI.
    settings.setValue(
      SettingScope.User,
      'security.auth.selectedType',
      AuthType.MULTI_PROVIDER,
    );
    return false;
  }

  // Pure Gemini (or non-multi) model with no multi-provider flags: stay on
  // the native Google path. Do not force Ollama auto-routing just because
  // GEMINI_API_KEY exists alongside a multi-provider model selection.
  if (!wantsRouting) {
    const googleConfigured = Boolean(
      process.env['GEMINI_API_KEY'] ||
        process.env['GOOGLE_API_KEY'] ||
        process.env['GOOGLE_GENAI_USE_GCA'] ||
        process.env['GOOGLE_GENAI_USE_VERTEXAI'],
    );
    if (argv.model !== undefined || googleConfigured) {
      return false;
    }
    // No model + no Google key → fall through for Ollama-first auto-detect.
  }

  const route = await resolveProviderRoute({
    model: argv.model,
    provider: argv.provider,
    free: argv.free,
    allowUnavailable: true,
  });
  if (!route) {
    if (argv.provider || argv.free) {
      writeToStderr(
        'No usable provider route found. Is the local server running / the API key set? ' +
          'Try --models to list models or --byok to add keys.\n',
      );
    } else if (process.stdin.isTTY && !isNonInteractiveTestEnv()) {
      // No route at all → open multi-model TUI instead of a blank fail.
      requestModelSetupUi();
    }
    return false;
  }

  // Missing API key for the chosen cloud provider: NEVER prompt with a bare
  // "Enter NVIDIA API key:" line. Open the multi-model picker (same as /model)
  // so the user can pick any model and paste a key in the dialog.
  if (!route.provider.local && route.provider.envKey) {
    const envKey = route.provider.envKey;
    const hasKey = process.env[envKey] && process.env[envKey]?.trim();
    const hasAlias = (ENV_KEY_ALIASES[route.provider.id] ?? []).some(
      (alias) => process.env[alias] && process.env[alias]?.trim(),
    );
    if (!hasKey && !hasAlias) {
      if (process.stdin.isTTY && !isNonInteractiveTestEnv()) {
        requestModelSetupUi();
        // Still pin multi-provider auth; do not force the unavailable model.
        if (route.provider.id !== 'gemini') {
          process.env['OPENAGENT_CLI_PROVIDER'] = route.provider.id;
          settings?.setValue(
            SettingScope.User,
            'security.auth.selectedType',
            AuthType.MULTI_PROVIDER,
          );
        }
        return false;
      }
      writeToStderr(
        `Error: ${route.provider.displayName} API key is required but not set.\n` +
          `Please set the ${envKey} environment variable, or run interactively to use the model picker.\n`,
      );
      return false;
    }
  }

  // Registry keys are unique; LiteLLM ids can be shared by alias entries
  // and would lose the api_base/provider overrides on re-resolution.
  argv.model = route.configKey ?? route.modelId;
  // Gemini has its own native auth path (GEMINI_API_KEY -> AuthType.USE_GEMINI)
  // and must not be pinned to the multi-provider (OpenAI-compat) route.
  if (route.provider.id !== 'gemini') {
    process.env['OPENAGENT_CLI_PROVIDER'] = route.provider.id;
    // Persist multi-provider auth so the header /auth line and subsequent
    // restarts match the active model (NVIDIA, OpenRouter, …) instead of
    // stale security.auth.selectedType = gemini-api-key.
    settings?.setValue(
      SettingScope.User,
      'security.auth.selectedType',
      AuthType.MULTI_PROVIDER,
    );
  } else {
    // A prior session may have persisted MULTI_PROVIDER auth (e.g. from
    // --provider ollama). Routing back to gemini must clear that, or
    // contentGenerator sees authType === MULTI_PROVIDER with a bare
    // "gemini/..." model id and throws "No provider route found" (the
    // multi-provider factory deliberately refuses to route gemini ids).
    delete process.env['OPENAGENT_CLI_PROVIDER'];
    if (
      settings?.merged?.security?.auth?.selectedType === AuthType.MULTI_PROVIDER
    ) {
      settings.setValue(
        SettingScope.User,
        'security.auth.selectedType',
        AuthType.USE_GEMINI,
      );
    }
  }
  if (argv.free) {
    // Arms the runtime free-model fallback chain in the generator factory.
    process.env['OPENAGENT_CLI_FREE'] = '1';
  }
  return true;
}

/**
 * Entry point called from gemini.tsx right after argument parsing.
 * Handles --models / --byok (both exit) and installs provider routing.
 */
export async function handleProviderStartupFlags(
  argv: CliArgs,
  settings?: LoadedSettings,
): Promise<void> {
  if (argv.models) {
    await printModelPicker();
    process.exit(0);
  }
  if (argv.byok) {
    await runByokWalkthrough();
    process.exit(0);
  }
  await applyProviderRouting(argv, settings);
}

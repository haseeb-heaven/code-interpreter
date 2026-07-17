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
  ENV_KEY_ALIASES,
  type ResolvedRoute,
  type ProviderDefinition,
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
 * process for multi-provider auth via OPENAGENT_CLI_PROVIDER. Returns true
 * when a multi-provider route was installed.
 */
function isNonInteractiveTestEnv(): boolean {
  return Boolean(process.env['VITEST']) || process.env['NODE_ENV'] === 'test';
}

async function promptForProviderKey(
  provider: ProviderDefinition,
): Promise<boolean> {
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
  const envKey = String(provider.envKey);
  writeToStdout(
    `\n[Setup] Configuration not found: ${provider.displayName} requires an API key (${envKey}).\n` +
      `Enter ${provider.displayName} API key: `,
  );
  try {
    const answer = (await rl.question('')).trim();
    if (answer) {
      writeEnvKey(envPath, envKey, answer);
      process.env[envKey] = answer;
      writeToStdout(`Key successfully saved to ${envPath}.\n\n`);
      return true;
    }
  } catch (err) {
    writeToStderr(`Error saving API key: ${err instanceof Error ? err.message : err}\n`);
  } finally {
    rl.close();
  }
  return false;
}

function maskKey(key: string): string {
  if (key.length <= 4) return '*'.repeat(key.length);
  return `${'*'.repeat(key.length - 4)}${key.slice(-4)}`;
}

const APPROVAL_MODE_CHOICES: ReadonlyArray<{ value: string; label: string }> = [
  { value: 'default', label: 'Edit mode - approve each file edit/command' },
  {
    value: 'auto_edit',
    label: 'Auto-edit mode - auto-approve edits, ask before commands',
  },
  { value: 'plan', label: 'Plan mode - plan first, then ask before executing' },
  {
    value: 'yolo',
    label: 'YOLO mode - auto-approve everything (use with caution)',
  },
];

/**
 * First-run setup wizard: reuses the same model list as --models / /model,
 * plus an approval-mode pick and the --byok key-save helper. Linear and
 * skippable (Enter accepts the recommended default, "s" skips entirely).
 */
async function runSetupWizard(
  argv: CliArgs,
  settings: LoadedSettings,
  defaultRoute: ResolvedRoute | undefined,
): Promise<boolean> {
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
    const registry = ModelRegistry.load();
    const detected = await detectLocalModels();
    const groups = groupModelsByProvider({
      registry,
      detectedLocalModels: detected,
    });
    const entries = groups.flatMap((group) =>
      group.models.map((model) => ({ model, provider: group.provider })),
    );

    if (entries.length === 0) {
      writeToStderr(
        '[Setup] No models found in configs/models.toml. Skipping setup wizard.\n',
      );
      settings.setValue(SettingScope.User, 'general.setupWizardCompleted', true);
      return false;
    }

    writeToStdout(
      "\n[Setup] Welcome to OpenAgent! Let's pick a model to get started.\n" +
        '(Press Enter to accept the recommended option, or "s" to skip setup.)\n\n',
    );

    let defaultIndex = entries.findIndex((entry) => entry.model.available);
    if (defaultRoute) {
      const wantedKey = defaultRoute.configKey ?? defaultRoute.modelId;
      const match = entries.findIndex(
        (entry) =>
          entry.model.key === wantedKey || entry.model.model === defaultRoute.modelId,
      );
      if (match !== -1) defaultIndex = match;
    }
    if (defaultIndex === -1) defaultIndex = 0;

    entries.forEach((entry, index) => {
      const ready = entry.model.available ? '✓' : '✗';
      const marker = index === defaultIndex ? '*' : ' ';
      const needsKey =
        !entry.model.available && entry.provider.envKey
          ? ` (needs ${String(entry.provider.envKey)})`
          : '';
      writeToStdout(
        `${marker}${String(index + 1).padStart(3)}. ${ready} ${entry.provider.displayName} / ${entry.model.key}${needsKey}\n`,
      );
    });

    const answer = (await rl.question(`\nModel [${defaultIndex + 1}]: `)).trim();
    if (answer.toLowerCase() === 's') {
      writeToStdout(
        '\n[Setup] Skipped. Run with --byok or --models any time to configure providers.\n\n',
      );
      settings.setValue(SettingScope.User, 'general.setupWizardCompleted', true);
      return false;
    }

    let selectedIndex = defaultIndex;
    if (answer) {
      const parsed = Number.parseInt(answer, 10);
      if (Number.isFinite(parsed) && parsed >= 1 && parsed <= entries.length) {
        selectedIndex = parsed - 1;
      } else {
        writeToStdout('  Not a valid choice, using the recommended option.\n');
      }
    }
    const selected = entries[selectedIndex];

    if (!selected.model.available) {
      if (!selected.provider.envKey) {
        writeToStdout(
          `  ${selected.provider.displayName} is a local provider - start its server ` +
            '(Ollama: localhost:11434, LM Studio: localhost:1234) and rerun.\n\n',
        );
        return false;
      }
      const envKey = String(selected.provider.envKey);
      const aliasKey = (ENV_KEY_ALIASES[selected.provider.id] ?? []).find(
        (alias) => process.env[alias]?.trim(),
      );
      const existingKey = process.env[envKey]?.trim() || (aliasKey && process.env[aliasKey]) || '';
      if (existingKey) {
        writeToStdout(
          `  Using existing ${selected.provider.displayName} key (${maskKey(existingKey)}).\n`,
        );
      } else {
        const keyAnswer = (
          await rl.question(
            `  Enter ${selected.provider.displayName} API key (${envKey}), or Enter to skip: `,
          )
        ).trim();
        if (!keyAnswer) {
          writeToStdout('\n[Setup] No key entered. Skipped setup.\n\n');
          settings.setValue(SettingScope.User, 'general.setupWizardCompleted', true);
          return false;
        }
        writeEnvKey(envPath, envKey, keyAnswer);
        process.env[envKey] = keyAnswer;
        writeToStdout(`  Key saved to ${envPath}.\n`);
      }
    }

    writeToStdout('\nApproval mode - how much should OpenAgent auto-approve?\n');
    APPROVAL_MODE_CHOICES.forEach((choice, index) => {
      writeToStdout(
        `  ${index + 1}. ${choice.label}${index === 0 ? ' (default)' : ''}\n`,
      );
    });
    const modeAnswer = (await rl.question('\nMode [1]: ')).trim();
    let mode = APPROVAL_MODE_CHOICES[0].value;
    if (modeAnswer) {
      const parsed = Number.parseInt(modeAnswer, 10);
      if (Number.isFinite(parsed) && parsed >= 1 && parsed <= APPROVAL_MODE_CHOICES.length) {
        mode = APPROVAL_MODE_CHOICES[parsed - 1].value;
      }
    }
    if (mode !== 'default') {
      settings.setValue(SettingScope.User, 'general.defaultApprovalMode', mode);
    }

    argv.model = selected.model.key;
    if (selected.provider.id !== 'gemini') {
      process.env['OPENAGENT_CLI_PROVIDER'] = selected.provider.id;
    }
    writeToStdout(
      `\n[Setup] All set - using ${selected.provider.displayName} / ${selected.model.key}.\n\n`,
    );
    settings.setValue(SettingScope.User, 'general.setupWizardCompleted', true);
    return true;
  } finally {
    rl.close();
  }
}

export async function applyProviderRouting(
  argv: CliArgs,
  settings?: LoadedSettings,
): Promise<boolean> {
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

  // First run only: no explicit --provider/--model/--free flag, no prior
  // provider configuration to preserve (mirrors the --byok trigger), the
  // wizard hasn't already run/been dismissed, and we're not inside a test
  // runner (vitest reports stdin as TTY-like, which would otherwise hang
  // on the interactive prompt).
  const isFirstRunCandidate =
    !wantsRouting &&
    Boolean(process.stdin.isTTY) &&
    settings !== undefined &&
    !settings.merged.general?.setupWizardCompleted &&
    !isNonInteractiveTestEnv();

  const route = await resolveProviderRoute({
    model: argv.model,
    provider: argv.provider,
    free: argv.free,
    allowUnavailable: true,
  });
  if (!route) {
    if (isFirstRunCandidate && settings) {
      return runSetupWizard(argv, settings, undefined);
    }
    if (argv.provider || argv.free) {
      writeToStderr(
        'No usable provider route found. Is the local server running / the API key set? ' +
          'Try --models to list models or --byok to add keys.\n',
      );
    }
    return false;
  }

  // Check if API key is missing for the resolved provider
  if (!route.provider.local && route.provider.envKey) {
    const envKey = route.provider.envKey;
    const hasKey = process.env[envKey] && process.env[envKey]?.trim();
    const hasAlias = (ENV_KEY_ALIASES[route.provider.id] ?? []).some(
      (alias) => process.env[alias] && process.env[alias]?.trim(),
    );
    if (!hasKey && !hasAlias) {
      if (isFirstRunCandidate && settings) {
        return runSetupWizard(argv, settings, route);
      }
      if (process.stdin.isTTY && !isNonInteractiveTestEnv()) {
        const keyEntered = await promptForProviderKey(route.provider);
        if (!keyEntered) {
          writeToStderr(
            `Error: ${route.provider.displayName} API key is required but not set.\n` +
            `Please run the command again and enter the key, or set the ${envKey} environment variable.\n`
          );
          return false;
        }
      } else {
        writeToStderr(
          `Error: ${route.provider.displayName} API key is required but not set.\n` +
          `Please set the ${envKey} environment variable.\n`
        );
        return false;
      }
    }
  }

  // Registry keys are unique; LiteLLM ids can be shared by alias entries
  // and would lose the api_base/provider overrides on re-resolution.
  argv.model = route.configKey ?? route.modelId;
  // Gemini has its own native auth path (GEMINI_API_KEY -> AuthType.USE_GEMINI)
  // and must not be pinned to the multi-provider (OpenAI-compat) route.
  if (route.provider.id !== 'gemini') {
    process.env['OPENAGENT_CLI_PROVIDER'] = route.provider.id;
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

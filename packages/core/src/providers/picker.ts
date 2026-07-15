/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Model picker grouping logic for `/pick` and `--pick`.
 *
 * Pure functions: the CLI layer renders the resulting groups. Models are
 * grouped by provider with vision support, streaming support, and API
 * key availability marked. Detected local models (Ollama / LM Studio)
 * always show as available.
 */

import {
  PROVIDERS,
  getProvider,
  isProviderAvailable,
  splitModelId,
  type ProviderDefinition,
} from './providers.js';
import { ModelRegistry } from './modelRegistry.js';

export interface PickerModel {
  /** Registry key or detected local model id (LiteLLM-style). */
  key: string;
  /** LiteLLM-style model id used for routing. */
  model: string;
  vision: boolean;
  streaming: boolean;
  /** Usable right now (local detected, or provider API key set). */
  available: boolean;
  tier?: string;
  notes?: string;
}

export interface PickerGroup {
  provider: ProviderDefinition;
  models: PickerModel[];
}

const VISION_MODEL_HINTS = [
  'gpt-4o',
  'gpt-4.1',
  'gpt-5',
  'gemini',
  'claude',
  'llava',
  'vision',
  'pixtral',
  'gemma-4',
];

/** Heuristic vision-support check by model id (provider gates first). */
export function modelSupportsVision(
  provider: ProviderDefinition | undefined,
  modelId: string,
): boolean {
  if (provider && !provider.vision) return false;
  const id = modelId.toLowerCase();
  return VISION_MODEL_HINTS.some((hint) => id.includes(hint));
}

function providerForConfig(
  configProvider: string | undefined,
  modelId: string,
): ProviderDefinition | undefined {
  if (configProvider) {
    const direct = getProvider(configProvider);
    if (direct) return direct;
    if (configProvider === 'local') return getProvider('ollama');
  }
  const { provider } = splitModelId(modelId);
  if (provider) return provider;
  // Bare ids follow the original project's conventions.
  const id = modelId.toLowerCase();
  if (id.startsWith('gpt') || /^o\d/.test(id)) return getProvider('openai');
  if (id.startsWith('claude')) return getProvider('anthropic');
  if (id.startsWith('deepseek')) return getProvider('deepseek');
  if (id.startsWith('glm')) return getProvider('z-ai');
  return undefined;
}

/**
 * Groups every model in the registry (plus detected local models) by
 * provider. `detectedLocalModels` maps a local provider id to the model
 * names its server reports; those are always marked available.
 */
export function groupModelsByProvider(options: {
  registry?: ModelRegistry;
  env?: NodeJS.ProcessEnv;
  detectedLocalModels?: Partial<Record<'ollama' | 'lmstudio', string[]>>;
}): PickerGroup[] {
  const registry = options.registry ?? ModelRegistry.load();
  const env = options.env ?? process.env;
  const detected = options.detectedLocalModels ?? {};

  const groups = new Map<string, PickerGroup>();
  const ensureGroup = (provider: ProviderDefinition): PickerGroup => {
    let group = groups.get(provider.id);
    if (!group) {
      group = { provider, models: [] };
      groups.set(provider.id, group);
    }
    return group;
  };

  // Detected local models first: always available.
  for (const providerId of ['ollama', 'lmstudio'] as const) {
    const provider = getProvider(providerId);
    const models = detected[providerId] ?? [];
    if (!provider) continue;
    for (const name of models) {
      const model = `${providerId}/${name.replace(new RegExp(`^${providerId}/`), '')}`;
      ensureGroup(provider).models.push({
        key: model,
        model,
        vision: modelSupportsVision(provider, model),
        streaming: provider.streaming,
        available: true,
        tier: 'local',
        notes: 'detected locally',
      });
    }
  }

  // Registry entries grouped by their provider.
  for (const key of registry.listModelNames()) {
    const cfg = registry.getModel(key);
    if (!cfg) continue;
    const provider = providerForConfig(cfg.provider, cfg.model ?? key);
    if (!provider) continue;
    const local = provider.local;
    const model = (cfg.model ?? key).trim();
    // Skip registry rows shadowed by a live detection of the same server.
    const liveModels =
      provider.id === 'ollama'
        ? detected.ollama
        : provider.id === 'lmstudio'
          ? detected.lmstudio
          : undefined;
    if (local && (liveModels ?? []).length > 0) {
      continue;
    }
    ensureGroup(provider).models.push({
      key,
      model,
      vision: modelSupportsVision(provider, model),
      streaming: provider.streaming,
      available: local ? false : isProviderAvailable(provider, env),
      tier: cfg.tier ? String(cfg.tier) : undefined,
      notes: cfg.notes ? String(cfg.notes) : undefined,
    });
  }

  // Stable output: provider declaration order, models sorted by key.
  const ordered: PickerGroup[] = [];
  for (const provider of PROVIDERS) {
    const group = groups.get(provider.id);
    if (!group || group.models.length === 0) continue;
    group.models.sort((a, b) => a.key.localeCompare(b.key));
    ordered.push(group);
  }
  return ordered;
}

/** Renders picker groups as terminal text (✓ marks + capability flags). */
export function formatPickerGroups(groups: readonly PickerGroup[]): string {
  if (groups.length === 0) {
    return 'No models found. Check configs/models.toml or start Ollama / LM Studio.';
  }
  const lines: string[] = [];
  for (const group of groups) {
    lines.push(`${group.provider.displayName}`);
    for (const model of group.models) {
      const ready = model.available ? '✓' : '✗';
      const vision = model.vision ? 'vision' : '     -';
      const streaming = model.streaming ? 'stream' : '     -';
      const tier = model.tier ? ` [${model.tier}]` : '';
      lines.push(
        `  ${ready} ${model.key.padEnd(36)} ${vision}  ${streaming}${tier}`,
      );
    }
    lines.push('');
  }
  lines.push('Use /model set <name> (or /pick <name>) to switch models.');
  lines.push('✓ = usable now (API key set or local server detected).');
  return lines.join('\n');
}

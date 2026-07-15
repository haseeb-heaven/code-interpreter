/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * /model dialog for the multi-provider fork: lists every model from
 * configs/models.toml grouped by provider (plus detected Ollama /
 * LM Studio models), and lets the user switch to any of them. Selecting
 * a paid model whose provider key is missing opens an inline API-key
 * step that saves the key to .env for that provider.
 */

import type React from 'react';
import * as path from 'node:path';
import { useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { Box, Text } from 'ink';
import {
  ModelSlashCommandEvent,
  isLMStudioRunning,
  isOllamaRunning,
  listLMStudioModels,
  listOllamaModels,
  logModelSlashCommand,
  writeEnvKey,
  getModelRegistry,
  groupModelsByProvider,
  type PickerGroup,
  type PickerModel,
  type ProviderDefinition,
} from '@open-agent/core';
import { useKeypress } from '../hooks/useKeypress.js';
import { theme } from '../semantic-colors.js';
import { DescriptiveRadioButtonSelect } from './shared/DescriptiveRadioButtonSelect.js';
import { TextInput } from './shared/TextInput.js';
import { useTextBuffer } from './shared/text-buffer.js';
import { ConfigContext } from '../contexts/ConfigContext.js';

interface ProviderModelDialogProps {
  onClose: () => void;
}

interface DialogEntry {
  model: PickerModel;
  provider: ProviderDefinition;
}

function tierLabel(model: PickerModel): string {
  switch (model.tier) {
    case 'free':
      return 'free';
    case 'free_tier':
      return 'free tier';
    case 'local':
      return 'local';
    default:
      return 'paid';
  }
}

export function ProviderModelDialog({
  onClose,
}: ProviderModelDialogProps): React.JSX.Element {
  const config = useContext(ConfigContext);
  // Registry models render immediately; detected local models are added
  // asynchronously when an Ollama / LM Studio server responds.
  const [groups, setGroups] = useState<PickerGroup[]>(() =>
    groupModelsByProvider({ registry: getModelRegistry() }),
  );
  const [pendingKeyEntry, setPendingKeyEntry] = useState<DialogEntry | null>(
    null,
  );
  const [notice, setNotice] = useState('');

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const detected: Partial<Record<'ollama' | 'lmstudio', string[]>> = {};
      const [ollamaUp, lmStudioUp] = await Promise.all([
        isOllamaRunning(),
        isLMStudioRunning(),
      ]);
      if (!ollamaUp && !lmStudioUp) return;
      if (ollamaUp) detected.ollama = await listOllamaModels();
      if (lmStudioUp) detected.lmstudio = await listLMStudioModels();
      if (cancelled) return;
      setGroups(
        groupModelsByProvider({
          registry: getModelRegistry(),
          detectedLocalModels: detected,
        }),
      );
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const entries = useMemo(() => {
    const map = new Map<string, DialogEntry>();
    for (const group of groups) {
      for (const model of group.models) {
        map.set(model.key, { model, provider: group.provider });
      }
    }
    return map;
  }, [groups]);

  const items = useMemo(
    () =>
      [...entries.values()].map(({ model, provider }) => ({
        value: model.key,
        key: model.key,
        title: `${model.available ? '✓' : '✗'} ${model.key}`,
        description: `${provider.displayName} · ${tierLabel(model)}${
          model.notes ? ` · ${model.notes}` : ''
        }${
          !model.available && provider.envKey
            ? ` · needs ${String(provider.envKey)}`
            : ''
        }`,
      })),
    [entries],
  );

  const initialIndex = useMemo(() => {
    const current = config?.getModel();
    if (!current) return 0;
    const idx = items.findIndex((item) => item.value === current);
    return idx === -1 ? 0 : idx;
  }, [config, items]);

  const applyModel = useCallback(
    (entry: DialogEntry) => {
      if (config) {
        // Registry keys are unique (LiteLLM ids can be shared by aliases),
        // so pass the key and let the provider factory resolve it.
        config.setModel(entry.model.key, true);
        logModelSlashCommand(
          config,
          new ModelSlashCommandEvent(entry.model.key),
        );
      }
      onClose();
    },
    [config, onClose],
  );

  const handleSelect = useCallback(
    (key: string) => {
      const entry = entries.get(key);
      if (!entry) return;
      if (entry.model.available) {
        applyModel(entry);
        return;
      }
      if (entry.provider.envKey) {
        setNotice('');
        setPendingKeyEntry(entry);
        return;
      }
      setNotice(
        `${entry.provider.displayName} is a local provider - start its server ` +
          '(Ollama: localhost:11434, LM Studio: localhost:1234) and reopen /model.',
      );
    },
    [entries, applyModel],
  );

  const keyBuffer = useTextBuffer({
    initialText: '',
    viewport: { width: 60, height: 1 },
    singleLine: true,
  });

  const handleKeySubmit = useCallback(
    (value: string) => {
      const entry = pendingKeyEntry;
      const apiKey = value.trim();
      if (!entry || !entry.provider.envKey) return;
      if (!apiKey) {
        setPendingKeyEntry(null);
        return;
      }
      const envKey = String(entry.provider.envKey);
      // .env is gitignored; same store the --byok walkthrough uses.
      writeEnvKey(path.join(process.cwd(), '.env'), envKey, apiKey);
      process.env[envKey] = apiKey;
      setPendingKeyEntry(null);
      applyModel(entry);
    },
    [pendingKeyEntry, applyModel],
  );

  useKeypress(
    (key) => {
      if (key.name === 'escape') {
        if (pendingKeyEntry) {
          setPendingKeyEntry(null);
        } else {
          onClose();
        }
        return true;
      }
      return false;
    },
    { isActive: true },
  );

  return (
    <Box
      borderStyle="round"
      borderColor={theme.border.default}
      flexDirection="column"
      padding={1}
      width="100%"
    >
      <Text bold>Select Model (all providers)</Text>

      {pendingKeyEntry === null && (
        <>
          <Box marginTop={1}>
            <DescriptiveRadioButtonSelect
              items={items}
              onSelect={handleSelect}
              initialIndex={initialIndex}
              showNumbers={false}
              showScrollArrows={true}
              maxItemsToShow={12}
            />
          </Box>
          {notice !== '' && (
            <Box marginTop={1}>
              <Text color={theme.status.warning}>{notice}</Text>
            </Box>
          )}
          <Box marginTop={1}>
            <Text color={theme.text.secondary}>
              ✓ usable now · ✗ needs an API key (selecting one prompts for it) ·
              Esc to close
            </Text>
          </Box>
        </>
      )}

      {pendingKeyEntry !== null && (
        <Box marginTop={1} flexDirection="column">
          <Text>
            Enter your {pendingKeyEntry.provider.displayName} API key (
            {String(pendingKeyEntry.provider.envKey)}) to use{' '}
            <Text bold>{pendingKeyEntry.model.key}</Text>:
          </Text>
          <Box marginTop={1}>
            <TextInput
              buffer={keyBuffer}
              placeholder="paste key and press Enter (Esc to go back)"
              onSubmit={handleKeySubmit}
              onCancel={() => setPendingKeyEntry(null)}
            />
          </Box>
          <Box marginTop={1}>
            <Text color={theme.text.secondary}>
              The key is saved to .env (gitignored) in this project.
            </Text>
          </Box>
        </Box>
      )}
    </Box>
  );
}

/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * /free-models dialog: an interactive picker scoped to the free-tier
 * catalog only (FreeLLMCatalog), rather than every model in the registry.
 * Mirrors ProviderModelDialog's local-provider / cloud-provider / API-key
 * flow so free entries that still require a key (OpenRouter free tier,
 * Groq free tier, etc.) get the same paste-and-save experience.
 */

import type React from 'react';
import { useCallback, useContext, useMemo, useState } from 'react';
import { Box, Text } from 'ink';
import {
  FreeLLMCatalog,
  ModelSlashCommandEvent,
  getDefaultEnvFilePath,
  getModelRegistry,
  getProvider,
  isEntryAvailable,
  logModelSlashCommand,
  providerApiKey,
  writeEnvKey,
  type FreeModelEntry,
  type ProviderDefinition,
} from '@open-agent/core';
import { useKeypress } from '../hooks/useKeypress.js';
import { theme } from '../semantic-colors.js';
import { DescriptiveRadioButtonSelect } from './shared/DescriptiveRadioButtonSelect.js';
import { TextInput } from './shared/TextInput.js';
import { useTextBuffer } from './shared/text-buffer.js';
import { ConfigContext } from '../contexts/ConfigContext.js';

interface FreeModelDialogProps {
  onClose: () => void;
}

interface DialogEntry {
  entry: FreeModelEntry;
  provider?: ProviderDefinition;
}

function tierLabel(tier: string): string {
  switch (tier) {
    case 'free':
      return 'free';
    case 'free_tier':
      return 'free tier';
    case 'local':
      return 'local';
    default:
      return tier || 'free';
  }
}

function maskKey(key: string): string {
  const t = key.trim();
  if (t.length <= 8) return '••••••••';
  return `${t.slice(0, 4)}…${t.slice(-4)}`;
}

export function FreeModelDialog({
  onClose,
}: FreeModelDialogProps): React.JSX.Element {
  const config = useContext(ConfigContext);
  const registry = useMemo(() => getModelRegistry(), []);
  const catalog = useMemo(() => FreeLLMCatalog.load(registry), [registry]);

  const entries = useMemo(() => {
    const map = new Map<string, DialogEntry>();
    for (const entry of catalog.entries) {
      map.set(entry.config, { entry, provider: getProvider(entry.provider) });
    }
    return map;
  }, [catalog]);

  const [pendingKeyEntry, setPendingKeyEntry] = useState<DialogEntry | null>(
    null,
  );
  const [existingKey, setExistingKey] = useState<string | undefined>();
  const [notice, setNotice] = useState('');

  const items = useMemo(
    () =>
      [...entries.values()].map(({ entry, provider }) => {
        const available = isEntryAvailable(entry, process.env);
        return {
          value: entry.config,
          key: entry.config,
          title: `${available ? '✓' : '✗'} ${entry.id}`,
          description: `${provider?.displayName ?? entry.provider} · ${tierLabel(
            entry.tier,
          )}${entry.notes ? ` · ${entry.notes}` : ''}${
            !available && provider?.envKey
              ? ` · needs ${String(provider.envKey)}`
              : available && provider?.envKey
                ? ` · ${String(provider.envKey)} set`
                : ''
          }`,
        };
      }),
    [entries],
  );

  const initialIndex = useMemo(() => {
    const current = config?.getModel();
    if (!current) return 0;
    const idx = items.findIndex((item) => item.value === current);
    return idx === -1 ? 0 : idx;
  }, [config, items]);

  const applyModel = useCallback(
    (dialogEntry: DialogEntry) => {
      if (config) {
        config.setModel(dialogEntry.entry.config, false);
        logModelSlashCommand(
          config,
          new ModelSlashCommandEvent(dialogEntry.entry.config),
        );
      }
      onClose();
    },
    [config, onClose],
  );

  const promptForKey = useCallback((dialogEntry: DialogEntry) => {
    const key = dialogEntry.provider?.envKey
      ? providerApiKey(dialogEntry.provider, process.env)
      : undefined;
    setExistingKey(key);
    setNotice('');
    setPendingKeyEntry(dialogEntry);
  }, []);

  const handleSelect = useCallback(
    (key: string) => {
      const dialogEntry = entries.get(key);
      if (!dialogEntry) return;
      const { entry, provider } = dialogEntry;

      if (provider?.local || entry.tier === 'local') {
        if (isEntryAvailable(entry, process.env)) {
          applyModel(dialogEntry);
          return;
        }
        setNotice(
          `${provider?.displayName ?? entry.provider} is a local provider — start its server ` +
            '(Ollama: localhost:11434, LM Studio: localhost:1234) and reopen /free-models.',
        );
        return;
      }

      if (provider?.envKey || entry.envKey) {
        promptForKey(dialogEntry);
        return;
      }

      applyModel(dialogEntry);
    },
    [entries, applyModel, promptForKey],
  );

  const keyBuffer = useTextBuffer({
    initialText: '',
    viewport: { width: 60, height: 1 },
    singleLine: true,
  });

  const handleKeySubmit = useCallback(
    (value: string) => {
      const dialogEntry = pendingKeyEntry;
      const envKeyName =
        dialogEntry?.provider?.envKey ?? dialogEntry?.entry.envKey;
      if (!dialogEntry || !envKeyName) return;

      const typed = value.replace(/\s+/g, '').trim();
      const envKey = String(envKeyName);

      const apiKey = typed || existingKey || '';
      if (!apiKey) {
        setNotice(
          `${dialogEntry.provider?.displayName ?? dialogEntry.entry.provider} requires ${envKey}. Paste your API key and press Enter.`,
        );
        return;
      }

      try {
        if (typed) {
          const envFile = getDefaultEnvFilePath();
          writeEnvKey(envFile, envKey, typed);
          process.env[envKey] = typed;
          setNotice(`Saved ${envKey} to ${envFile}`);
        }

        setPendingKeyEntry(null);
        setExistingKey(undefined);
        applyModel(dialogEntry);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setNotice(`Could not save key: ${msg}. Fix and press Enter again.`);
      }
    },
    [pendingKeyEntry, existingKey, applyModel],
  );

  useKeypress(
    (key) => {
      if (
        (key.ctrl && (key.name === 'c' || key.name === 'd')) ||
        key.name === 'escape'
      ) {
        if (key.name === 'escape' || (key.ctrl && key.name === 'c')) {
          if (pendingKeyEntry) {
            setPendingKeyEntry(null);
            setExistingKey(undefined);
            setNotice(
              'Cancelled key entry. Select a model again or Esc to close.',
            );
            return true;
          }
          if (key.name === 'escape') {
            onClose();
            return true;
          }
        }
        return true;
      }
      return false;
    },
    { isActive: true, priority: true },
  );

  const currentModel = config?.getModel() ?? '';

  return (
    <Box
      borderStyle="round"
      borderColor={theme.ui.focus}
      flexDirection="column"
      padding={1}
      width="100%"
    >
      <Box>
        <Text color={theme.text.accent}>? </Text>
        <Text bold color={theme.text.primary}>
          Free models
        </Text>
      </Box>
      <Box marginTop={1}>
        <Text color={theme.text.primary}>
          Pick a free-tier / local model to activate
        </Text>
      </Box>
      {currentModel ? (
        <Box marginTop={1}>
          <Text color={theme.text.secondary}>Current: {currentModel}</Text>
        </Box>
      ) : null}

      {items.length === 0 && (
        <Box marginTop={1}>
          <Text color={theme.status.warning}>
            No free models are configured in the catalog.
          </Text>
        </Box>
      )}

      {items.length > 0 && pendingKeyEntry === null && (
        <>
          <Box marginTop={1}>
            <DescriptiveRadioButtonSelect
              items={items}
              onSelect={handleSelect}
              initialIndex={initialIndex}
              showNumbers={true}
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
              (Use Enter to select · Esc to close)
            </Text>
          </Box>
          <Box marginTop={1}>
            <Text color={theme.text.secondary}>
              ✓ key ready · ✗ needs API key · after pick, paste key if asked
            </Text>
          </Box>
        </>
      )}

      {pendingKeyEntry !== null && (
        <Box marginTop={1} flexDirection="column">
          <Text>
            {pendingKeyEntry.provider?.displayName ??
              pendingKeyEntry.entry.provider}{' '}
            API key (
            {String(
              pendingKeyEntry.provider?.envKey ?? pendingKeyEntry.entry.envKey,
            )}
            ){' for '}
            <Text bold>{pendingKeyEntry.entry.id}</Text>
            {pendingKeyEntry.entry.tier === 'free' ||
            pendingKeyEntry.entry.tier === 'free_tier'
              ? ' (free models still require a provider API key)'
              : ''}
            :
          </Text>
          {existingKey ? (
            <Box marginTop={1}>
              <Text color={theme.status.success}>
                Found existing key: {maskKey(existingKey)} — press Enter to use
                it, or paste a new key to replace.
              </Text>
            </Box>
          ) : (
            <Box marginTop={1}>
              <Text color={theme.status.warning}>
                No{' '}
                {String(
                  pendingKeyEntry.provider?.envKey ??
                    pendingKeyEntry.entry.envKey,
                )}{' '}
                in .env — paste your API key below.
              </Text>
            </Box>
          )}
          <Box marginTop={1}>
            <TextInput
              buffer={keyBuffer}
              placeholder={
                existingKey
                  ? 'Enter to keep existing key, or paste a new one'
                  : 'paste key and press Enter (Esc to go back)'
              }
              onSubmit={handleKeySubmit}
              onCancel={() => {
                setPendingKeyEntry(null);
                setExistingKey(undefined);
                setNotice('');
              }}
            />
          </Box>
          {notice !== '' && (
            <Box marginTop={1}>
              <Text color={theme.status.warning}>{notice}</Text>
            </Box>
          )}
          <Box marginTop={1}>
            <Text color={theme.text.secondary}>
              Paste key then Enter · Esc back · keys saved to ~/.openagent/.env
            </Text>
          </Box>
        </Box>
      )}
    </Box>
  );
}

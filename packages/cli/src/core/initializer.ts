/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import {
  AuthType,
  IdeClient,
  IdeConnectionEvent,
  IdeConnectionType,
  isMultiProviderModel,
  logIdeConnection,
  type Config,
  StartSessionEvent,
  logCliConfiguration,
  startupProfiler,
  debugLogger,
} from '@open-agent/core';
import { type LoadedSettings } from '../config/settings.js';
import { SettingScope } from '../config/settings.js';
import { performInitialAuth } from './auth.js';
import { validateTheme } from './theme.js';
import { resolveOpenAgentDefaultAuth } from '../config/openAgentAuth.js';
import type { AccountSuspensionInfo } from '../ui/contexts/UIStateContext.js';

export interface InitializationResult {
  authError: string | null;
  accountSuspensionInfo: AccountSuspensionInfo | null;
  themeError: string | null;
  shouldOpenAuthDialog: boolean;
  geminiMdFileCount: number;
}

/**
 * Orchestrates the application's startup initialization.
 * This runs BEFORE the React UI is rendered.
 * @param config The application config.
 * @param settings The loaded application settings.
 * @returns The results of the initialization.
 */
export async function initializeApp(
  config: Config,
  settings: LoadedSettings,
): Promise<InitializationResult> {
  const authHandle = startupProfiler.start('authenticate');

  // OpenAgent: never strand the user on the Gemini CLI "Sign in with Google /
  // Gemini API Key / Vertex" dialog. Auto-select multi-provider (or Gemini
  // only when that is the sole available path).
  let authType = settings.merged.security.auth.selectedType;
  if (
    authType === undefined ||
    // Stale Gemini-only selection while the active model is itself a
    // multi-provider id (e.g. nvidia-nemotron) — re-resolve so auth matches
    // the model. Checked against the model directly (not
    // resolveOpenAgentDefaultAuth's ambient-env heuristic), so an explicit
    // `--provider gemini` pin isn't clobbered just because unrelated BYOK
    // keys (OPENAI_API_KEY, etc.) also happen to be set in the environment.
    (authType === AuthType.USE_GEMINI &&
      isMultiProviderModel(config.getModel()))
  ) {
    authType = resolveOpenAgentDefaultAuth(config.getModel());
    settings.setValue(
      SettingScope.User,
      'security.auth.selectedType',
      authType,
    );
  }

  const { authError, accountSuspensionInfo } = await performInitialAuth(
    config,
    authType,
  );
  authHandle?.end();
  const themeError = validateTheme(settings);

  // Only open /auth UI when login actually failed — not merely because
  // selectedType was empty (we already filled it above).
  const shouldOpenAuthDialog = !!authError;

  logCliConfiguration(
    config,
    new StartSessionEvent(config, config.getToolRegistry()),
  );

  if (config.getIdeMode()) {
    IdeClient.getInstance()
      .then(async (ideClient) => {
        await ideClient.connect();
        logIdeConnection(
          config,
          new IdeConnectionEvent(IdeConnectionType.START),
        );
      })
      .catch((e) => {
        // We log locally if IDE connection setup fails in the background.
        debugLogger.error('Failed to initialize IDE client:', e);
      });
  }

  return {
    authError,
    accountSuspensionInfo,
    themeError,
    shouldOpenAuthDialog,
    geminiMdFileCount: config.getGeminiMdFileCount(),
  };
}

/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import type React from 'react';
import { useMemo, useState, useEffect } from 'react';
import { Box, Text } from 'ink';
import { theme } from '../semantic-colors.js';
import {
  type Config,
  UserAccountManager,
  AuthType,
  resolveActiveProvider,
} from '@open-agent/core';
import { isUltraTier } from '../../utils/tierUtils.js';

interface UserIdentityProps {
  config: Config;
}

/**
 * Human-readable names for Gemini-family / Google auth methods.
 * Multi-provider sessions resolve the live provider via the active model.
 */
const AUTH_TYPE_DISPLAY_NAMES: Readonly<Partial<Record<AuthType, string>>> = {
  [AuthType.LOGIN_WITH_GOOGLE]: 'Google',
  [AuthType.USE_GEMINI]: 'Gemini',
  [AuthType.USE_VERTEX_AI]: 'Vertex AI',
  [AuthType.LEGACY_CLOUD_SHELL]: 'Cloud Shell',
  [AuthType.COMPUTE_ADC]: 'Compute ADC',
  [AuthType.GATEWAY]: 'Gateway',
};

/**
 * Returns a user-facing provider/auth label for the header, e.g.
 * "OpenRouter", "Gemini", "OpenAI".
 */
export function resolveProviderDisplayName(config: Config): string | undefined {
  const authType = config.getContentGeneratorConfig()?.authType;
  if (!authType) {
    return undefined;
  }

  if (authType === AuthType.LOGIN_WITH_GOOGLE) {
    return AUTH_TYPE_DISPLAY_NAMES[AuthType.LOGIN_WITH_GOOGLE];
  }

  // Prefer the provider that actually backs the active model (OpenRouter,
  // OpenAI, Groq, Ollama, …) over the raw auth-type id.
  const currentModel = config.getModel();
  if (currentModel) {
    try {
      const provider = resolveActiveProvider(currentModel);
      if (provider?.displayName) {
        return provider.displayName;
      }
    } catch {
      // Registry may be unavailable in unit tests; fall through.
    }
  }

  if (authType === AuthType.MULTI_PROVIDER) {
    return 'Multi-provider';
  }

  return AUTH_TYPE_DISPLAY_NAMES[authType] ?? authType;
}

/**
 * Builds the "Authenticated with …" line shown under the OA logo.
 *
 * Examples:
 * - Authenticated with Gemini API key.
 * - Authenticated with OpenRouter API key.
 * - Authenticated with Ollama (local).
 */
export function formatAuthStatusLine(
  providerDisplayName: string,
  authType: AuthType,
): string {
  if (authType === AuthType.LOGIN_WITH_GOOGLE) {
    return 'Signed in with Google';
  }

  // Local providers already include "(local)" in their display name.
  if (/\(local\)/i.test(providerDisplayName)) {
    return `Authenticated with ${providerDisplayName}.`;
  }

  // API-key backed providers.
  if (
    authType === AuthType.USE_GEMINI ||
    authType === AuthType.MULTI_PROVIDER ||
    authType === AuthType.USE_VERTEX_AI ||
    authType === AuthType.GATEWAY
  ) {
    return `Authenticated with ${providerDisplayName} API key.`;
  }

  return `Authenticated with ${providerDisplayName}.`;
}

export const UserIdentity: React.FC<UserIdentityProps> = ({ config }) => {
  const authType = config.getContentGeneratorConfig()?.authType;
  const [email, setEmail] = useState<string | undefined>();

  useEffect(() => {
    if (authType) {
      const userAccountManager = new UserAccountManager();
      setEmail(userAccountManager.getCachedGoogleAccount() ?? undefined);
    } else {
      setEmail(undefined);
    }
  }, [authType]);

  const tierName = useMemo(
    () => (authType ? config.getUserTierName() : undefined),
    [config, authType],
  );

  const isUltra = useMemo(() => isUltraTier(tierName), [tierName]);

  const providerDisplayName = useMemo(
    () => resolveProviderDisplayName(config),
    [config],
  );

  if (!authType || !providerDisplayName) {
    return null;
  }

  return (
    <Box flexDirection="column">
      {/* User Email /auth */}
      <Box>
        <Text color={theme.text.primary} wrap="truncate-end">
          {authType === AuthType.LOGIN_WITH_GOOGLE ? (
            <Text>
              <Text bold>
                Signed in with Google{email ? ':' : ''}
              </Text>
              {email ? ` ${email}` : ''}
            </Text>
          ) : (
            formatAuthStatusLine(providerDisplayName, authType)
          )}
        </Text>
        <Text color={theme.text.secondary}> /auth</Text>
      </Box>

      {/* Tier Name /upgrade */}
      {tierName && (
        <Box>
          <Text color={theme.text.primary} wrap="truncate-end">
            <Text bold>Plan:</Text> {tierName}
          </Text>
          {!isUltra && <Text color={theme.text.secondary}> /upgrade</Text>}
        </Box>
      )}
    </Box>
  );
};

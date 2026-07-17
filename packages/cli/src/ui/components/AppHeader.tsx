/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { Box, Text } from 'ink';
import { UserIdentity } from './UserIdentity.js';
import { Tips } from './Tips.js';
import { useSettings } from '../contexts/SettingsContext.js';
import { useConfig } from '../contexts/ConfigContext.js';
import { useUIState } from '../contexts/UIStateContext.js';
import { Banner } from './Banner.js';
import { useBanner } from '../hooks/useBanner.js';
import { useTips } from '../hooks/useTips.js';
import { theme } from '../semantic-colors.js';
import { ThemedGradient } from './ThemedGradient.js';
import { CliSpinner } from './CliSpinner.js';

import {
  longAsciiLogoCompactText,
  tinyAsciiLogoCompactText,
} from './AsciiArt.js';
import { getAsciiArtWidth } from '../utils/textUtils.js';

interface AppHeaderProps {
  version: string;
  showDetails?: boolean;
}

/**
 * The horizontal padding (in columns) required for metadata (version, identity, etc.)
 * when rendered alongside the ASCII logo.
 */
const LOGO_METADATA_PADDING = 28;

/**
 * The terminal width below which we switch to a narrow/column layout to prevent
 * UI elements from wrapping or overlapping.
 */
const NARROW_TERMINAL_BREAKPOINT = 48;

export const AppHeader = ({ version, showDetails = true }: AppHeaderProps) => {
  const settings = useSettings();
  const config = useConfig();
  const {
    terminalWidth,
    bannerData,
    bannerVisible,
    updateInfo,
    isConfigInitialized,
    isAuthenticating,
  } = useUIState();

  const { bannerText } = useBanner(bannerData);
  const { showTips } = useTips();

  const authType = config.getContentGeneratorConfig()?.authType;
  const loggedOut = isConfigInitialized && !isAuthenticating && !authType;

  const showHeader = !(
    settings.merged.ui.hideBanner || config.getScreenReader()
  );

  const widthOfOaLogo =
    getAsciiArtWidth(longAsciiLogoCompactText) + LOGO_METADATA_PADDING;
  const canFitOaLogo = terminalWidth >= widthOfOaLogo;
  const isNarrow = terminalWidth < NARROW_TERMINAL_BREAKPOINT;

  // Always prefer the full OA block logo; fall back to the tiny glyph art on
  // very narrow terminals so the banner stays readable.
  const logoArt = canFitOaLogo
    ? longAsciiLogoCompactText.trim()
    : tinyAsciiLogoCompactText.trim();

  const renderLogo = () => (
    <Box flexShrink={0}>
      <ThemedGradient>{logoArt}</ThemedGradient>
    </Box>
  );

  /**
   * Metadata sits to the right of the OA logo. Blank rows align "OpenAgent vX"
   * with logo line 2 and the auth line with logo line 5 (when using the full OA).
   */
  const renderMetadata = (isBelow = false) => (
    <Box marginLeft={isBelow ? 0 : 2} flexDirection="column">
      {!isBelow && canFitOaLogo && <Box height={1} />}

      {/* Line: OpenAgent vVersion [Updating] */}
      <Box>
        <Text bold color={theme.text.primary}>
          OpenAgent
        </Text>
        <Text color={theme.text.secondary}> v{version}</Text>
        {updateInfo?.isUpdating && (
          <Box marginLeft={2}>
            <Text color={theme.text.secondary}>
              <CliSpinner /> Updating
            </Text>
          </Box>
        )}
      </Box>

      {showDetails && (
        <>
          {!isBelow && canFitOaLogo && (
            <>
              <Box height={1} />
              <Box height={1} />
            </>
          )}
          {isBelow && <Box height={1} />}

          {/* User Identity: provider / Google sign-in */}
          {settings.merged.ui.showUserIdentity !== false && (
            <UserIdentity config={config} />
          )}
          {loggedOut && (
            <Text color={theme.text.secondary}>Not authenticated · /auth</Text>
          )}
        </>
      )}
    </Box>
  );

  const useColumnLayout = isNarrow || !canFitOaLogo;

  return (
    <Box flexDirection="column">
      {showHeader && (
        <Box
          flexDirection={useColumnLayout ? 'column' : 'row'}
          marginTop={1}
          marginBottom={1}
          paddingLeft={1}
        >
          {renderLogo()}
          {useColumnLayout ? (
            <Box marginTop={1}>{renderMetadata(true)}</Box>
          ) : (
            renderMetadata(false)
          )}
        </Box>
      )}

      {bannerVisible && bannerText && (
        <Banner
          width={terminalWidth}
          bannerText={bannerText}
          isWarning={bannerData.warningText !== ''}
        />
      )}

      {!(settings.merged.ui.hideTips || config.getScreenReader()) &&
        showTips && <Tips config={config} />}
    </Box>
  );
};

/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import type {
  MCPServerConfig,
  ExtensionInstallMetadata,
  CustomTheme,
} from '@open-agent/core';
import * as fs from 'node:fs';
import {
  INSTALL_METADATA_FILENAMES,
  resolveExistingOrDefaultPath,
} from './extensions/variables.js';
import type { ExtensionSetting } from './extensions/extensionSettings.js';

/**
 * Extension definition as written to disk in extension manifest files.
 * This should *not* be referenced outside of the logic for reading files.
 * If information is required for manipulating extensions (load, unload, update)
 * outside of the loading process that data needs to be stored on the
 * GeminiCLIExtension class defined in Core.
 */
export interface ExtensionConfig {
  name: string;
  version: string;
  mcpServers?: Record<string, MCPServerConfig>;
  contextFileName?: string | string[];
  excludeTools?: string[];
  settings?: ExtensionSetting[];
  /**
   * Custom themes contributed by this extension.
   * These themes will be registered when the extension is activated.
   */
  themes?: CustomTheme[];
  /**
   * Planning features configuration contributed by this extension.
   */
  plan?: {
    /**
     * The directory where planning artifacts are stored.
     */
    directory?: string;
  };
  /**
   * Used to migrate an extension to a new repository source.
   */
  migratedTo?: string;
}

export interface ExtensionUpdateInfo {
  name: string;
  originalVersion: string;
  updatedVersion: string;
}

export function loadInstallMetadata(
  extensionDir: string,
): ExtensionInstallMetadata | undefined {
  const metadataFilePath = resolveExistingOrDefaultPath(
    extensionDir,
    INSTALL_METADATA_FILENAMES,
  );
  try {
    const configContent = fs.readFileSync(metadataFilePath, 'utf-8');
    // eslint-disable-next-line @typescript-eslint/no-unsafe-type-assertion
    const metadata = JSON.parse(configContent) as ExtensionInstallMetadata;
    return metadata;
  } catch {
    return undefined;
  }
}

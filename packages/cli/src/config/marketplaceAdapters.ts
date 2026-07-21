/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import type { RegistryExtension } from './extensionRegistryClient.js';

const CLAUDE_CODE_MARKETPLACE_REPO_URL =
  'https://github.com/anthropics/claude-plugins-official.git';

type AdaptedExtension = Omit<RegistryExtension, 'registryName'>;

interface ClaudeCodeSourceUrl {
  source: 'url';
  url: string;
  sha?: string;
}

interface ClaudeCodeSourceGithub {
  source: 'github';
  repo: string;
  commit?: string;
  sha?: string;
}

interface ClaudeCodeSourceGitSubdir {
  source: 'git-subdir';
  url: string;
  path: string;
  ref?: string;
  sha?: string;
}

type ClaudeCodeSource =
  | ClaudeCodeSourceUrl
  | ClaudeCodeSourceGithub
  | ClaudeCodeSourceGitSubdir
  | string;

interface ClaudeCodeMarketplacePlugin {
  name: string;
  description?: string;
  author?: { name?: string };
  category?: string;
  source: ClaudeCodeSource;
  homepage?: string;
}

export interface ClaudeCodeMarketplaceJson {
  name?: string;
  owner?: { name?: string };
  plugins: ClaudeCodeMarketplacePlugin[];
}

/**
 * Adapts the Claude Code plugin marketplace.json format
 * (github.com/anthropics/claude-plugins-official) into `RegistryExtension`s.
 *
 * `source` is one of four shapes:
 * - `{source:'url', url}` — directly clonable, repo root is the extension.
 * - `{source:'github', repo}` — build the clone URL from `owner/repo`.
 * - `{source:'git-subdir', url, path, ref}` — extension lives in a subdir.
 * - a plain string, e.g. `"./plugins/agent-sdk-dev"` — a path inside the
 *   marketplace repo itself, also a subdir install.
 */
export function adaptClaudeCodeMarketplace(
  json: ClaudeCodeMarketplaceJson,
): AdaptedExtension[] {
  const plugins = Array.isArray(json.plugins) ? json.plugins : [];
  return plugins.map((plugin) => {
    const { url, installRef, installSubdir } = resolveClaudeCodeSource(
      plugin.source,
    );
    return {
      id: `claude-code:${plugin.name}`,
      rank: 0,
      url,
      installRef,
      installSubdir,
      fullName: plugin.name,
      repoDescription: plugin.description ?? '',
      stars: 0,
      lastUpdated: '',
      extensionName: plugin.name,
      extensionVersion: '',
      extensionDescription: plugin.description ?? '',
      avatarUrl: '',
      hasMCP: false,
      hasContext: false,
      hasHooks: false,
      hasSkills: false,
      hasCustomCommands: false,
      isGoogleOwned: false,
      licenseKey: '',
    };
  });
}

function resolveClaudeCodeSource(source: ClaudeCodeSource): {
  url: string;
  installRef?: string;
  installSubdir?: string;
} {
  if (typeof source === 'string') {
    return {
      url: CLAUDE_CODE_MARKETPLACE_REPO_URL,
      installSubdir: source,
    };
  }
  switch (source.source) {
    case 'url':
      return { url: source.url };
    case 'github':
      return { url: `https://github.com/${source.repo}.git` };
    case 'git-subdir':
      return {
        url: source.url,
        installRef: source.ref,
        installSubdir: source.path,
      };
    default: {
      const _exhaustiveCheck: never = source;
      throw new Error(
        `Unhandled Claude Code marketplace source: ${JSON.stringify(_exhaustiveCheck)}`,
      );
    }
  }
}

interface CodexMarketplacePlugin {
  slug: string;
  name: string;
  displayName?: string;
  version?: string;
  description?: string;
  pluginPath?: string;
  author?: string;
  license?: string;
  repository?: string;
  homepage?: string;
  githubStars?: number;
  lastUpdated?: string;
  logo?: string;
  hasSkills?: boolean;
  hasMcpServers?: boolean;
  hasHooks?: boolean;
  hasApps?: boolean;
}

export interface CodexMarketplaceJson {
  plugins: CodexMarketplacePlugin[];
}

/**
 * Adapts the Codex plugin marketplace API
 * (www.codex-marketplace.com/api/plugins) into `RegistryExtension`s. Every
 * entry has both `repository` (clonable URL) and `pluginPath` (subdir)
 * populated.
 */
export function adaptCodexMarketplace(
  json: CodexMarketplaceJson,
): AdaptedExtension[] {
  const plugins = Array.isArray(json.plugins) ? json.plugins : [];
  return plugins.map((plugin) => ({
    id: `codex:${plugin.slug}`,
    rank: 0,
    url: plugin.repository ?? '',
    installSubdir: plugin.pluginPath,
    fullName: plugin.displayName ?? plugin.name,
    repoDescription: plugin.description ?? '',
    stars: plugin.githubStars ?? 0,
    lastUpdated: plugin.lastUpdated ?? '',
    extensionName: plugin.displayName ?? plugin.name,
    extensionVersion: plugin.version ?? '',
    extensionDescription: plugin.description ?? '',
    avatarUrl: plugin.logo ?? '',
    hasMCP: plugin.hasMcpServers ?? false,
    hasContext: false,
    hasHooks: plugin.hasHooks ?? false,
    hasSkills: plugin.hasSkills ?? false,
    hasCustomCommands: plugin.hasApps ?? false,
    isGoogleOwned: false,
    licenseKey: plugin.license ?? '',
  }));
}

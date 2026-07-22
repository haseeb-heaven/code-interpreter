/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect } from 'vitest';
import {
  adaptClaudeCodeMarketplace,
  adaptCodexMarketplace,
  type ClaudeCodeMarketplaceJson,
  type CodexMarketplaceJson,
} from './marketplaceAdapters.js';

describe('adaptClaudeCodeMarketplace', () => {
  it('adapts a {source: "url"} plugin to a registry extension', () => {
    const json: ClaudeCodeMarketplaceJson = {
      name: 'Test marketplace',
      owner: { name: 'Anthropic' },
      plugins: [
        {
          name: 'slack',
          description: 'Slack integration',
          author: { name: 'Acme' },
          source: { source: 'url', url: 'https://github.com/acme/slack.git' },
          homepage: 'https://acme.com/slack',
        },
      ],
    };

    const [ext] = adaptClaudeCodeMarketplace(json);
    expect(ext.id).toBe('claude-code:slack');
    expect(ext.url).toBe('https://github.com/acme/slack.git');
    expect(ext.installRef).toBeUndefined();
    expect(ext.installSubdir).toBeUndefined();
    expect(ext.extensionName).toBe('slack');
    expect(ext.extensionDescription).toBe('Slack integration');
    expect(ext.hasMCP).toBe(false);
    expect(ext.isGoogleOwned).toBe(false);
  });

  it('adapts a {source: "github"} plugin by building the clone URL from owner/repo', () => {
    const json: ClaudeCodeMarketplaceJson = {
      plugins: [
        {
          name: 'my-tool',
          source: { source: 'github', repo: 'acme/my-tool' },
        },
      ],
    };

    const [ext] = adaptClaudeCodeMarketplace(json);
    expect(ext.url).toBe('https://github.com/acme/my-tool.git');
    expect(ext.installRef).toBeUndefined();
    expect(ext.installSubdir).toBeUndefined();
  });

  it('adapts a {source: "git-subdir"} plugin, threading ref and subdir', () => {
    const json: ClaudeCodeMarketplaceJson = {
      plugins: [
        {
          name: 'agent-sdk',
          description: 'SDK skills',
          source: {
            source: 'git-subdir',
            url: 'https://github.com/acme/sdk.git',
            path: 'packages/agent-skills',
            ref: 'main',
          },
        },
      ],
    };

    const [ext] = adaptClaudeCodeMarketplace(json);
    expect(ext.url).toBe('https://github.com/acme/sdk.git');
    expect(ext.installRef).toBe('main');
    expect(ext.installSubdir).toBe('packages/agent-skills');
  });

  it('adapts a plain-string source as an installSubdir against the marketplace repo', () => {
    const json: ClaudeCodeMarketplaceJson = {
      plugins: [
        {
          name: 'bundled-plugin',
          source: './plugins/bundled-plugin',
        },
      ],
    };

    const [ext] = adaptClaudeCodeMarketplace(json);
    expect(ext.url).toBe(
      'https://github.com/anthropics/claude-plugins-official.git',
    );
    expect(ext.installSubdir).toBe('./plugins/bundled-plugin');
  });

  it('returns an empty array when plugins is missing or not an array', () => {
    expect(adaptClaudeCodeMarketplace({} as ClaudeCodeMarketplaceJson)).toEqual(
      [],
    );
    expect(
      adaptClaudeCodeMarketplace({
        plugins: 'nope',
      } as unknown as ClaudeCodeMarketplaceJson),
    ).toEqual([]);
  });
});

describe('adaptCodexMarketplace', () => {
  it('adapts a codex plugin, mapping repository + pluginPath', () => {
    const json: CodexMarketplaceJson = {
      plugins: [
        {
          slug: 'codex-slack',
          name: 'slack',
          displayName: 'Slack',
          version: '1.2.0',
          description: 'Codex Slack plugin',
          pluginPath: 'plugins/slack',
          repository: 'https://github.com/acme/codex-slack.git',
          author: 'Acme',
          license: 'mit',
          githubStars: 42,
          lastUpdated: '2026-01-01',
          logo: 'https://acme.com/logo.png',
          hasSkills: true,
          hasMcpServers: true,
          hasHooks: false,
          hasApps: true,
        },
      ],
    };

    const [ext] = adaptCodexMarketplace(json);
    expect(ext.id).toBe('codex:codex-slack');
    expect(ext.url).toBe('https://github.com/acme/codex-slack.git');
    expect(ext.installSubdir).toBe('plugins/slack');
    expect(ext.extensionName).toBe('Slack');
    expect(ext.extensionVersion).toBe('1.2.0');
    expect(ext.stars).toBe(42);
    expect(ext.hasMCP).toBe(true);
    expect(ext.hasSkills).toBe(true);
    expect(ext.hasHooks).toBe(false);
    expect(ext.hasCustomCommands).toBe(true);
    expect(ext.licenseKey).toBe('mit');
  });

  it('falls back to the plugin name when displayName is absent', () => {
    const json: CodexMarketplaceJson = {
      plugins: [
        {
          slug: 's',
          name: 'plain-name',
          repository: 'https://example.com/r.git',
        },
      ],
    };

    const [ext] = adaptCodexMarketplace(json);
    expect(ext.extensionName).toBe('plain-name');
    expect(ext.installSubdir).toBeUndefined();
    expect(ext.hasMCP).toBe(false);
  });

  it('returns an empty array for a missing plugins list', () => {
    expect(adaptCodexMarketplace({} as CodexMarketplaceJson)).toEqual([]);
  });
});

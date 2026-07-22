/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';
import {
  ApprovalMode,
  loadAgentsFromDirectory,
  loadSkillsFromDir,
} from '@open-agent/core';
import { ExtensionManager } from './extension-manager.js';
import { createTestMergedSettings } from './settings.js';
import { cleanupTmpDir } from '@open-agent/test-utils';
import {
  isWorkspaceTrusted,
  resetTrustedFoldersForTesting,
} from './trustedFolders.js';
import { ExtensionStorage } from './extensions/storage.js';

let currentTempHome = '';

vi.mock('@open-agent/core', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@open-agent/core')>();
  return {
    ...actual,
    homedir: () => currentTempHome,
    debugLogger: {
      log: vi.fn(),
      error: vi.fn(),
      warn: vi.fn(),
      debug: vi.fn(),
    },
    loadAgentsFromDirectory: vi.fn().mockImplementation(async () => ({
      agents: [],
      errors: [],
    })),
    loadSkillsFromDir: vi.fn().mockImplementation(async () => []),
  };
});

vi.mock('./trustedFolders.js', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./trustedFolders.js')>();
  return { ...actual, isWorkspaceTrusted: vi.fn() };
});

/**
 * Creates a Claude Code plugin-structured directory:
 *   dir/.claude-plugin/plugin.json
 *   dir/.mcp.json (optional)
 */
function createClaudePlugin(
  dir: string,
  opts: {
    name: string;
    version?: string;
    mcpJson?: Record<string, unknown>;
  },
): string {
  fs.mkdirSync(path.join(dir, '.claude-plugin'), { recursive: true });
  fs.writeFileSync(
    path.join(dir, '.claude-plugin', 'plugin.json'),
    JSON.stringify({
      name: opts.name,
      version: opts.version,
      description: `${opts.name} plugin`,
      author: { name: 'Test' },
    }),
  );
  if (opts.mcpJson) {
    fs.writeFileSync(path.join(dir, '.mcp.json'), JSON.stringify(opts.mcpJson));
  }
  return dir;
}

describe('ExtensionManager Claude plugin.json support', () => {
  let tempWorkspace: string;
  let sourceDir: string;
  let requestConsent: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.mocked(loadAgentsFromDirectory).mockResolvedValue({
      agents: [],
      errors: [],
    });
    vi.mocked(loadSkillsFromDir).mockResolvedValue([]);
    currentTempHome = fs.mkdtempSync(
      path.join(os.tmpdir(), 'openagent-plugin-home-'),
    );
    vi.stubEnv('OPENAGENT_HOME', currentTempHome);
    vi.stubEnv('GEMINI_CLI_HOME', currentTempHome);
    tempWorkspace = fs.mkdtempSync(
      path.join(os.tmpdir(), 'openagent-plugin-workspace-'),
    );
    sourceDir = fs.mkdtempSync(
      path.join(os.tmpdir(), 'openagent-plugin-source-'),
    );
    requestConsent = vi.fn().mockResolvedValue(true);
    vi.mocked(isWorkspaceTrusted).mockReturnValue({
      isTrusted: true,
      source: 'file',
    });
    resetTrustedFoldersForTesting();
  });

  afterEach(async () => {
    await cleanupTmpDir(currentTempHome);
    await cleanupTmpDir(tempWorkspace);
    await cleanupTmpDir(sourceDir);
    vi.clearAllMocks();
    vi.unstubAllEnvs();
  });

  it('loads an ExtensionConfig from a Claude .claude-plugin/plugin.json manifest', async () => {
    const pluginDir = createClaudePlugin(sourceDir, {
      name: 'slack-plugin',
      version: '1.4.0',
      mcpJson: {
        'slack-server': { type: 'http', url: 'https://mcp.slack.example/mcp' },
      },
    });

    const manager = new ExtensionManager({
      workspaceDir: tempWorkspace,
      requestConsent,
      requestSetting: null,
      settings: createTestMergedSettings({
        telemetry: { enabled: false },
        security: { folderTrust: { enabled: false } },
      }),
    });

    const config = await manager.loadExtensionConfig(pluginDir);
    expect(config.name).toBe('slack-plugin');
    expect(config.version).toBe('1.4.0');
    expect(config.mcpServers).toBeDefined();
    expect(config.mcpServers!['slack-server']).toMatchObject({
      type: 'http',
      url: 'https://mcp.slack.example/mcp',
    });
  });

  it('defaults version to 0.0.0 when the plugin manifest omits it', async () => {
    const pluginDir = createClaudePlugin(sourceDir, { name: 'no-version' });

    const manager = new ExtensionManager({
      workspaceDir: tempWorkspace,
      requestConsent,
      requestSetting: null,
      settings: createTestMergedSettings({
        telemetry: { enabled: false },
        security: { folderTrust: { enabled: false } },
      }),
    });

    const config = await manager.loadExtensionConfig(pluginDir);
    expect(config.version).toBe('0.0.0');
  });

  it('throws when the plugin manifest is missing a name', async () => {
    const pluginDir = path.join(sourceDir, 'bad-plugin');
    fs.mkdirSync(path.join(pluginDir, '.claude-plugin'), { recursive: true });
    fs.writeFileSync(
      path.join(pluginDir, '.claude-plugin', 'plugin.json'),
      JSON.stringify({ description: 'no name here' }),
    );

    const manager = new ExtensionManager({
      workspaceDir: tempWorkspace,
      requestConsent,
      requestSetting: null,
      settings: createTestMergedSettings({
        telemetry: { enabled: false },
        security: { folderTrust: { enabled: false } },
      }),
    });

    await expect(manager.loadExtensionConfig(pluginDir)).rejects.toThrow(
      /missing "name"/,
    );
  });

  it('installs a Claude plugin-structured source and surfaces its MCP server', async () => {
    const pluginDir = createClaudePlugin(sourceDir, {
      name: 'slack-install',
      version: '2.0.0',
      mcpJson: {
        'slack-mcp': { type: 'http', url: 'https://mcp.slack.example/mcp' },
      },
    });

    const manager = new ExtensionManager({
      workspaceDir: tempWorkspace,
      requestConsent,
      requestSetting: null,
      settings: createTestMergedSettings({
        telemetry: { enabled: false },
        security: { folderTrust: { enabled: false } },
      }),
    });

    await manager.loadExtensions();
    const ext = await manager.installOrUpdateExtension({
      source: pluginDir,
      type: 'local',
    });

    expect(ext.name).toBe('slack-install');
    expect(ext.version).toBe('2.0.0');
    expect(ext.mcpServers?.['slack-mcp']).toMatchObject({
      type: 'http',
      url: 'https://mcp.slack.example/mcp',
    });

    const installedDir = new ExtensionStorage(
      'slack-install',
    ).getExtensionDir();
    expect(fs.existsSync(path.join(installedDir, '.mcp.json'))).toBe(true);
    await manager.uninstallExtension('slack-install', false);
  });
});

describe('ExtensionManager Auto-mode workspace trust', () => {
  let tempWorkspace: string;
  let sourceDir: string;
  let requestConsent: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.mocked(loadAgentsFromDirectory).mockResolvedValue({
      agents: [],
      errors: [],
    });
    vi.mocked(loadSkillsFromDir).mockResolvedValue([]);
    currentTempHome = fs.mkdtempSync(
      path.join(os.tmpdir(), 'openagent-auto-home-'),
    );
    vi.stubEnv('OPENAGENT_HOME', currentTempHome);
    vi.stubEnv('GEMINI_CLI_HOME', currentTempHome);
    tempWorkspace = fs.mkdtempSync(
      path.join(os.tmpdir(), 'openagent-auto-workspace-'),
    );
    sourceDir = fs.mkdtempSync(
      path.join(os.tmpdir(), 'openagent-auto-source-'),
    );
    requestConsent = vi.fn().mockResolvedValue(true);
    // Workspace is NOT trusted — the trust branch must run.
    vi.mocked(isWorkspaceTrusted).mockReturnValue({
      isTrusted: false,
      source: undefined,
    });
    resetTrustedFoldersForTesting();
  });

  afterEach(async () => {
    await cleanupTmpDir(currentTempHome);
    await cleanupTmpDir(tempWorkspace);
    await cleanupTmpDir(sourceDir);
    vi.clearAllMocks();
    vi.unstubAllEnvs();
  });

  function makeManager(mode: ApprovalMode) {
    return new ExtensionManager({
      workspaceDir: tempWorkspace,
      requestConsent,
      requestSetting: null,
      approvalMode: mode,
      settings: createTestMergedSettings({
        telemetry: { enabled: false },
        security: { folderTrust: { enabled: true } },
      }),
    });
  }

  it('does NOT prompt for workspace trust when approvalMode is AUTO', async () => {
    fs.writeFileSync(
      path.join(sourceDir, 'open-agent-extension.json'),
      JSON.stringify({ name: 'auto-trust-ext', version: '1.0.0' }),
    );

    const manager = makeManager(ApprovalMode.AUTO);
    await manager.loadExtensions();
    const ext = await manager.installOrUpdateExtension({
      source: sourceDir,
      type: 'local',
    });

    expect(ext.name).toBe('auto-trust-ext');
    // The workspace-trust consent prompt must be skipped in Auto mode.
    expect(requestConsent).not.toHaveBeenCalledWith(
      expect.stringContaining('is not trusted'),
    );
    await manager.uninstallExtension('auto-trust-ext', false);
  });

  it('does NOT prompt for workspace trust when approvalMode is YOLO', async () => {
    fs.writeFileSync(
      path.join(sourceDir, 'open-agent-extension.json'),
      JSON.stringify({ name: 'yolo-trust-ext', version: '1.0.0' }),
    );

    const manager = makeManager(ApprovalMode.YOLO);
    await manager.loadExtensions();
    const ext = await manager.installOrUpdateExtension({
      source: sourceDir,
      type: 'local',
    });

    expect(ext.name).toBe('yolo-trust-ext');
    expect(requestConsent).not.toHaveBeenCalledWith(
      expect.stringContaining('is not trusted'),
    );
    await manager.uninstallExtension('yolo-trust-ext', false);
  });

  it('still prompts for workspace trust in DEFAULT mode', async () => {
    fs.writeFileSync(
      path.join(sourceDir, 'open-agent-extension.json'),
      JSON.stringify({ name: 'default-trust-ext', version: '1.0.0' }),
    );

    const manager = makeManager(ApprovalMode.DEFAULT);
    await manager.loadExtensions();
    const ext = await manager.installOrUpdateExtension({
      source: sourceDir,
      type: 'local',
    });

    expect(ext.name).toBe('default-trust-ext');
    expect(requestConsent).toHaveBeenCalledWith(
      expect.stringContaining('is not trusted'),
    );
    await manager.uninstallExtension('default-trust-ext', false);
  });

  it('respects a live setApprovalMode update from DEFAULT to AUTO', async () => {
    fs.writeFileSync(
      path.join(sourceDir, 'open-agent-extension.json'),
      JSON.stringify({ name: 'live-mode-ext', version: '1.0.0' }),
    );

    const manager = makeManager(ApprovalMode.DEFAULT);
    manager.setApprovalMode(ApprovalMode.AUTO);
    await manager.loadExtensions();
    await manager.installOrUpdateExtension({
      source: sourceDir,
      type: 'local',
    });

    expect(requestConsent).not.toHaveBeenCalledWith(
      expect.stringContaining('is not trusted'),
    );
    await manager.uninstallExtension('live-mode-ext', false);
  });
});

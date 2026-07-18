/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { format } from 'node:util';
import {
  handleRegistryAdd,
  handleRegistryRemove,
  handleRegistryList,
  registryCommand,
} from './registry.js';
import {
  loadSettings,
  SettingScope,
  type LoadedSettings,
} from '../../config/settings.js';

const emitConsoleLog = vi.hoisted(() => vi.fn());
const debugLogger = vi.hoisted(() => ({
  log: vi.fn((message, ...args) => {
    emitConsoleLog('log', format(message, ...args));
  }),
  error: vi.fn((message, ...args) => {
    emitConsoleLog('error', format(message, ...args));
  }),
}));

vi.mock('@open-agent/core', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@open-agent/core')>();
  return {
    ...actual,
    debugLogger,
  };
});

vi.mock('../../config/settings.js');

describe('extensions registry command', () => {
  const mockLoadSettings = vi.mocked(loadSettings);
  let setValue: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
    setValue = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  function mockSources(sources: Array<{ name: string; uri: string }>) {
    mockLoadSettings.mockReturnValue({
      merged: {
        experimental: {
          extensionRegistries: sources,
        },
      },
      setValue,
    } as unknown as LoadedSettings);
  }

  describe('handleRegistryAdd', () => {
    it('should append a new registry source to the settings array', () => {
      mockSources([{ name: 'OpenAgent', uri: 'https://a.example.com' }]);

      handleRegistryAdd('Local', './local.json');

      expect(setValue).toHaveBeenCalledWith(
        SettingScope.User,
        'experimental.extensionRegistries',
        [
          { name: 'OpenAgent', uri: 'https://a.example.com' },
          { name: 'Local', uri: './local.json' },
        ],
      );
      expect(emitConsoleLog).toHaveBeenCalledWith(
        'log',
        'Registry "Local" added.',
      );
    });

    it('should reject a duplicate registry name', () => {
      mockSources([{ name: 'Local', uri: './local.json' }]);

      expect(() => handleRegistryAdd('Local', './other.json')).toThrow(
        'A registry named "Local" already exists. Remove it first or choose a different name.',
      );
      expect(setValue).not.toHaveBeenCalled();
    });

    it('should start from an empty list when no registries are configured', () => {
      mockSources([]);

      handleRegistryAdd('Local', './local.json');

      expect(setValue).toHaveBeenCalledWith(
        SettingScope.User,
        'experimental.extensionRegistries',
        [{ name: 'Local', uri: './local.json' }],
      );
    });
  });

  describe('handleRegistryRemove', () => {
    it('should remove a registry source by name', () => {
      mockSources([
        { name: 'OpenAgent', uri: 'https://a.example.com' },
        { name: 'Local', uri: './local.json' },
      ]);

      handleRegistryRemove('Local');

      expect(setValue).toHaveBeenCalledWith(
        SettingScope.User,
        'experimental.extensionRegistries',
        [{ name: 'OpenAgent', uri: 'https://a.example.com' }],
      );
      expect(emitConsoleLog).toHaveBeenCalledWith(
        'log',
        'Registry "Local" removed.',
      );
    });

    it('should throw when the named registry does not exist', () => {
      mockSources([{ name: 'OpenAgent', uri: 'https://a.example.com' }]);

      expect(() => handleRegistryRemove('Missing')).toThrow(
        'No registry named "Missing" is configured.',
      );
      expect(setValue).not.toHaveBeenCalled();
    });
  });

  describe('handleRegistryList', () => {
    it('should log each configured registry', () => {
      mockSources([
        { name: 'OpenAgent', uri: 'https://a.example.com' },
        { name: 'Local', uri: './local.json' },
      ]);

      handleRegistryList();

      expect(emitConsoleLog).toHaveBeenCalledWith(
        'log',
        'OpenAgent: https://a.example.com\nLocal: ./local.json',
      );
    });

    it('should log a message when no registries are configured', () => {
      mockSources([]);

      handleRegistryList();

      expect(emitConsoleLog).toHaveBeenCalledWith(
        'log',
        'No extension registries configured.',
      );
    });
  });

  describe('registryCommand', () => {
    it('should have the expected command and describe', () => {
      expect(registryCommand.command).toBe('registry <command>');
      expect(registryCommand.describe).toBe(
        'Manage extension marketplace/registry sources.',
      );
    });
  });
});

/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  loadApiKey,
  saveApiKey,
  clearApiKey,
  resetApiKeyCacheForTesting,
} from './apiKeyCredentialStorage.js';

const getCredentialsMock = vi.hoisted(() => vi.fn());
const setCredentialsMock = vi.hoisted(() => vi.fn());
const deleteCredentialsMock = vi.hoisted(() => vi.fn());
const legacyGetCredentialsMock = vi.hoisted(() => vi.fn());
const legacyDeleteCredentialsMock = vi.hoisted(() => vi.fn());

vi.mock('../mcp/token-storage/hybrid-token-storage.js', () => ({
  HybridTokenStorage: vi.fn().mockImplementation((serviceName: string) => {
    if (serviceName === 'gemini-cli-api-key') {
      return {
        getCredentials: legacyGetCredentialsMock,
        setCredentials: vi.fn(),
        deleteCredentials: legacyDeleteCredentialsMock,
      };
    }
    return {
      getCredentials: getCredentialsMock,
      setCredentials: setCredentialsMock,
      deleteCredentials: deleteCredentialsMock,
    };
  }),
}));

describe('ApiKeyCredentialStorage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetApiKeyCacheForTesting();
    legacyGetCredentialsMock.mockResolvedValue(null);
  });

  it('should load an API key and cache it', async () => {
    getCredentialsMock.mockResolvedValue({
      serverName: 'default-api-key',
      token: {
        accessToken: 'test-key',
        tokenType: 'ApiKey',
      },
      updatedAt: Date.now(),
    });

    const apiKey1 = await loadApiKey();
    expect(apiKey1).toBe('test-key');
    expect(getCredentialsMock).toHaveBeenCalledTimes(1);

    const apiKey2 = await loadApiKey();
    expect(apiKey2).toBe('test-key');
    expect(getCredentialsMock).toHaveBeenCalledTimes(1); // Should be cached
  });

  it('should return null if no API key is stored and cache it', async () => {
    getCredentialsMock.mockResolvedValue(null);
    const apiKey1 = await loadApiKey();
    expect(apiKey1).toBeNull();
    expect(getCredentialsMock).toHaveBeenCalledTimes(1);
    expect(legacyGetCredentialsMock).toHaveBeenCalledTimes(1);

    const apiKey2 = await loadApiKey();
    expect(apiKey2).toBeNull();
    expect(getCredentialsMock).toHaveBeenCalledTimes(1); // Should be cached
    expect(legacyGetCredentialsMock).toHaveBeenCalledTimes(1);
  });

  it('should save an API key and clear cache', async () => {
    getCredentialsMock.mockResolvedValue({
      serverName: 'default-api-key',
      token: {
        accessToken: 'old-key',
        tokenType: 'ApiKey',
      },
      updatedAt: Date.now(),
    });

    await loadApiKey();
    expect(getCredentialsMock).toHaveBeenCalledTimes(1);

    await saveApiKey('new-key');
    expect(setCredentialsMock).toHaveBeenCalledWith(
      expect.objectContaining({
        serverName: 'default-api-key',
        token: expect.objectContaining({
          accessToken: 'new-key',
          tokenType: 'ApiKey',
        }),
      }),
    );

    getCredentialsMock.mockResolvedValue({
      serverName: 'default-api-key',
      token: {
        accessToken: 'new-key',
        tokenType: 'ApiKey',
      },
      updatedAt: Date.now(),
    });

    await loadApiKey();
    expect(getCredentialsMock).toHaveBeenCalledTimes(2); // Should have fetched again
  });

  it('should clear an API key and clear cache', async () => {
    getCredentialsMock.mockResolvedValue({
      serverName: 'default-api-key',
      token: {
        accessToken: 'old-key',
        tokenType: 'ApiKey',
      },
      updatedAt: Date.now(),
    });

    await loadApiKey();
    expect(getCredentialsMock).toHaveBeenCalledTimes(1);

    await clearApiKey();
    expect(deleteCredentialsMock).toHaveBeenCalledWith('default-api-key');

    getCredentialsMock.mockResolvedValue(null);
    await loadApiKey();
    expect(getCredentialsMock).toHaveBeenCalledTimes(2); // Should have fetched again
  });

  it('should fall back to the legacy keychain entry and migrate it forward', async () => {
    getCredentialsMock.mockResolvedValue(null);
    legacyGetCredentialsMock.mockResolvedValue({
      serverName: 'default-api-key',
      token: {
        accessToken: 'legacy-key',
        tokenType: 'ApiKey',
      },
      updatedAt: Date.now(),
    });

    const apiKey = await loadApiKey();
    expect(apiKey).toBe('legacy-key');

    // Migrated forward into the new keychain service...
    expect(setCredentialsMock).toHaveBeenCalledWith(
      expect.objectContaining({
        serverName: 'default-api-key',
        token: expect.objectContaining({ accessToken: 'legacy-key' }),
      }),
    );
    // ...and removed from the legacy service.
    expect(legacyDeleteCredentialsMock).toHaveBeenCalledWith('default-api-key');
  });

  it('should still return the legacy key if removing it from legacy storage fails', async () => {
    getCredentialsMock.mockResolvedValue(null);
    legacyGetCredentialsMock.mockResolvedValue({
      serverName: 'default-api-key',
      token: {
        accessToken: 'legacy-key',
        tokenType: 'ApiKey',
      },
      updatedAt: Date.now(),
    });
    legacyDeleteCredentialsMock.mockRejectedValueOnce(
      new Error('Failed to delete'),
    );

    await expect(loadApiKey()).resolves.toBe('legacy-key');
  });

  it('should clear an API key and cache when saving empty key', async () => {
    await saveApiKey('');
    expect(deleteCredentialsMock).toHaveBeenCalledWith('default-api-key');
    expect(setCredentialsMock).not.toHaveBeenCalled();
  });

  it('should clear an API key and cache when saving null key', async () => {
    await saveApiKey(null);
    expect(deleteCredentialsMock).toHaveBeenCalledWith('default-api-key');
    expect(setCredentialsMock).not.toHaveBeenCalled();
  });

  it('should not throw when clearing an API key fails during saveApiKey', async () => {
    deleteCredentialsMock.mockRejectedValueOnce(new Error('Failed to delete'));
    await expect(saveApiKey('')).resolves.not.toThrow();
    expect(deleteCredentialsMock).toHaveBeenCalledWith('default-api-key');
  });

  it('should not throw when clearing an API key fails during clearApiKey', async () => {
    deleteCredentialsMock.mockRejectedValueOnce(new Error('Failed to delete'));
    await expect(clearApiKey()).resolves.not.toThrow();
    expect(deleteCredentialsMock).toHaveBeenCalledWith('default-api-key');
  });
});

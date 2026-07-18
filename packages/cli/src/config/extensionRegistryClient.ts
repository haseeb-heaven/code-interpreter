/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import * as fs from 'node:fs/promises';
import {
  fetchWithTimeout,
  resolveToRealPath,
  isPrivateIp,
} from '@open-agent/core';
import { AsyncFzf } from 'fzf';

export interface RegistryExtension {
  id: string;
  rank: number;
  url: string;
  fullName: string;
  repoDescription: string;
  stars: number;
  lastUpdated: string;
  extensionName: string;
  extensionVersion: string;
  extensionDescription: string;
  avatarUrl: string;
  hasMCP: boolean;
  hasContext: boolean;
  hasHooks: boolean;
  hasSkills: boolean;
  hasCustomCommands: boolean;
  isGoogleOwned: boolean;
  licenseKey: string;
  /** Name of the registry source this extension was fetched from. */
  registryName: string;
}

export class ExtensionRegistryClient {
  static readonly DEFAULT_REGISTRY_URL =
    'https://geminicli.com/extensions.json';
  static readonly DEFAULT_REGISTRY_NAME = 'OpenAgent';
  private static readonly FETCH_TIMEOUT_MS = 10000; // 10 seconds

  private fetchPromise: Promise<RegistryExtension[]> | null = null;

  private readonly registryURI: string;
  private readonly registryName: string;

  constructor(registryURI?: string, registryName?: string) {
    this.registryURI =
      registryURI || ExtensionRegistryClient.DEFAULT_REGISTRY_URL;
    this.registryName =
      registryName || ExtensionRegistryClient.DEFAULT_REGISTRY_NAME;
  }

  async getExtensions(
    page: number = 1,
    limit: number = 10,
    orderBy: 'ranking' | 'alphabetical' = 'ranking',
  ): Promise<{ extensions: RegistryExtension[]; total: number }> {
    const allExtensions = await this.fetchAllExtensions();
    return sortAndPaginate(allExtensions, page, limit, orderBy);
  }

  async searchExtensions(query: string): Promise<RegistryExtension[]> {
    const allExtensions = await this.fetchAllExtensions();
    if (!query.trim()) {
      return allExtensions;
    }

    const fzf = new AsyncFzf(allExtensions, {
      selector: (ext: RegistryExtension) =>
        `${ext.extensionName} ${ext.extensionDescription} ${ext.fullName}`,
      fuzzy: true,
    });
    // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment
    const results: Array<{ item: RegistryExtension }> = await fzf.find(query);
    return results.map((r) => r.item);
  }

  async getExtension(id: string): Promise<RegistryExtension | undefined> {
    const allExtensions = await this.fetchAllExtensions();
    return allExtensions.find((ext) => ext.id === id);
  }

  private async fetchAllExtensions(): Promise<RegistryExtension[]> {
    if (this.fetchPromise) {
      return this.fetchPromise;
    }

    const uri = this.registryURI;
    this.fetchPromise = (async () => {
      try {
        let extensions: Array<Omit<RegistryExtension, 'registryName'>>;
        if (uri.startsWith('http')) {
          if (isPrivateIp(uri)) {
            throw new Error(
              'Private IP addresses are not allowed for the extension registry.',
            );
          }
          const response = await fetchWithTimeout(
            uri,
            ExtensionRegistryClient.FETCH_TIMEOUT_MS,
          );
          if (!response.ok) {
            throw new Error(
              `Failed to fetch extensions: ${response.statusText}`,
            );
          }

          // eslint-disable-next-line @typescript-eslint/no-unsafe-type-assertion
          extensions = (await response.json()) as Array<
            Omit<RegistryExtension, 'registryName'>
          >;
        } else {
          // Handle local file path
          const filePath = resolveToRealPath(uri);
          const content = await fs.readFile(filePath, 'utf-8');
          // eslint-disable-next-line @typescript-eslint/no-unsafe-type-assertion
          extensions = JSON.parse(content) as Array<
            Omit<RegistryExtension, 'registryName'>
          >;
        }
        return extensions.map((ext) => ({
          ...ext,
          registryName: this.registryName,
        }));
      } catch (error) {
        this.fetchPromise = null;
        throw error;
      }
    })();

    return this.fetchPromise;
  }
}

interface RegistrySourceLike {
  name: string;
  uri: string;
}

function sortAndPaginate(
  extensions: RegistryExtension[],
  page: number,
  limit: number,
  orderBy: 'ranking' | 'alphabetical',
): { extensions: RegistryExtension[]; total: number } {
  const sorted = [...extensions];
  switch (orderBy) {
    case 'ranking':
      sorted.sort((a, b) => a.rank - b.rank);
      break;
    case 'alphabetical':
      sorted.sort((a, b) => a.extensionName.localeCompare(b.extensionName));
      break;
    default: {
      const _exhaustiveCheck: never = orderBy;
      throw new Error(`Unhandled orderBy: ${_exhaustiveCheck}`);
    }
  }

  const startIndex = (page - 1) * limit;
  const endIndex = startIndex + limit;
  return {
    extensions: sorted.slice(startIndex, endIndex),
    total: sorted.length,
  };
}

/**
 * Aggregates extensions across multiple named registry sources. Tolerates
 * individual source failures (a down/misconfigured registry doesn't break
 * the others) and dedupes by extension `id`, first-seen source wins.
 */
export class MultiRegistryClient {
  private readonly clients: ExtensionRegistryClient[];

  constructor(sources: RegistrySourceLike[]) {
    this.clients = sources.map(
      (source) => new ExtensionRegistryClient(source.uri, source.name),
    );
  }

  async getExtensions(
    page: number = 1,
    limit: number = 10,
    orderBy: 'ranking' | 'alphabetical' = 'ranking',
  ): Promise<{ extensions: RegistryExtension[]; total: number }> {
    const allExtensions = this.dedupe(await this.fetchAll());
    return sortAndPaginate(allExtensions, page, limit, orderBy);
  }

  async searchExtensions(query: string): Promise<RegistryExtension[]> {
    const allExtensions = this.dedupe(await this.fetchAll());
    if (!query.trim()) {
      return allExtensions;
    }

    const fzf = new AsyncFzf(allExtensions, {
      selector: (ext: RegistryExtension) =>
        `${ext.extensionName} ${ext.extensionDescription} ${ext.fullName}`,
      fuzzy: true,
    });
    // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment
    const results: Array<{ item: RegistryExtension }> = await fzf.find(query);
    return results.map((r) => r.item);
  }

  async getExtension(id: string): Promise<RegistryExtension | undefined> {
    const allExtensions = this.dedupe(await this.fetchAll());
    return allExtensions.find((ext) => ext.id === id);
  }

  private async fetchAll(): Promise<RegistryExtension[]> {
    const results = await Promise.all(
      this.clients.map(async (client) => {
        try {
          return (await client.getExtensions(1, Number.MAX_SAFE_INTEGER))
            .extensions;
        } catch {
          // Tolerate a single misbehaving/unreachable registry source; the
          // others should still be usable.
          return [];
        }
      }),
    );
    return results.flat();
  }

  private dedupe(extensions: RegistryExtension[]): RegistryExtension[] {
    const seen = new Set<string>();
    const deduped: RegistryExtension[] = [];
    for (const ext of extensions) {
      if (seen.has(ext.id)) {
        continue;
      }
      seen.add(ext.id);
      deduped.push(ext);
    }
    return deduped;
  }
}

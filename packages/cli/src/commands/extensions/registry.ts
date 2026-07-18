/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import type { CommandModule } from 'yargs';
import type { RegistrySource } from '@open-agent/core';
import { debugLogger, FatalConfigError } from '@open-agent/core';
import { loadSettings, SettingScope } from '../../config/settings.js';
import { exitCli } from '../utils.js';
import { defer } from '../../deferred.js';

function getRegistrySources(cwd: string): RegistrySource[] {
  return loadSettings(cwd).merged.experimental?.extensionRegistries ?? [];
}

function saveRegistrySources(cwd: string, sources: RegistrySource[]): void {
  const loadedSettings = loadSettings(cwd);
  loadedSettings.setValue(
    SettingScope.User,
    'experimental.extensionRegistries',
    sources,
  );
}

export function handleRegistryAdd(name: string, uri: string) {
  const cwd = process.cwd();
  const sources = getRegistrySources(cwd);
  if (sources.some((source) => source.name === name)) {
    throw new FatalConfigError(
      `A registry named "${name}" already exists. Remove it first or choose a different name.`,
    );
  }
  saveRegistrySources(cwd, [...sources, { name, uri }]);
  debugLogger.log(`Registry "${name}" added.`);
}

export function handleRegistryRemove(name: string) {
  const cwd = process.cwd();
  const sources = getRegistrySources(cwd);
  if (!sources.some((source) => source.name === name)) {
    throw new FatalConfigError(`No registry named "${name}" is configured.`);
  }
  saveRegistrySources(
    cwd,
    sources.filter((source) => source.name !== name),
  );
  debugLogger.log(`Registry "${name}" removed.`);
}

export function handleRegistryList() {
  const sources = getRegistrySources(process.cwd());
  if (sources.length === 0) {
    debugLogger.log('No extension registries configured.');
    return;
  }
  debugLogger.log(
    sources.map((source) => `${source.name}: ${source.uri}`).join('\n'),
  );
}

interface RegistryAddArgs {
  name: string;
  uri: string;
}

const addCommand: CommandModule<object, RegistryAddArgs> = {
  command: 'add <name> <uri>',
  describe: 'Adds a named extension registry source.',
  builder: (yargs) =>
    yargs
      .positional('name', {
        describe: 'A unique name for the registry.',
        type: 'string',
        demandOption: true,
      })
      .positional('uri', {
        describe: 'The registry URI (web URL or local file path).',
        type: 'string',
        demandOption: true,
      }),
  handler: async (argv) => {
    handleRegistryAdd(argv.name, argv.uri);
    await exitCli();
  },
};

interface RegistryRemoveArgs {
  name: string;
}

const removeCommand: CommandModule<object, RegistryRemoveArgs> = {
  command: 'remove <name>',
  aliases: ['rm'],
  describe: 'Removes a named extension registry source.',
  builder: (yargs) =>
    yargs.positional('name', {
      describe: 'The name of the registry to remove.',
      type: 'string',
      demandOption: true,
    }),
  handler: async (argv) => {
    handleRegistryRemove(argv.name);
    await exitCli();
  },
};

const listCommand: CommandModule = {
  command: 'list',
  describe: 'Lists configured extension registry sources.',
  handler: async () => {
    handleRegistryList();
    await exitCli();
  },
};

export const registryCommand: CommandModule = {
  command: 'registry <command>',
  describe: 'Manage extension marketplace/registry sources.',
  builder: (yargs) =>
    yargs
      .command(defer(addCommand, 'extensions'))
      .command(defer(removeCommand, 'extensions'))
      .command(defer(listCommand, 'extensions'))
      .demandCommand(1, 'You need at least one command before continuing.')
      .version(false),
  handler: () => {
    // This handler is not called when a subcommand is provided.
    // Yargs will show the help menu.
  },
};

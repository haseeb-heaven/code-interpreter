/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import {
  getPackageJson,
  type SandboxConfig,
  FatalSandboxError,
} from '@open-agent/core';
import commandExists from 'command-exists';
import * as os from 'node:os';
import type { Settings } from './settings.js';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// This is a stripped-down version of the CliArgs interface from config.ts
// to avoid circular dependencies.
interface SandboxCliArgs {
  sandbox?: boolean | string | null;
}
// Placeholder OpenAgent sandbox image; not published to a registry yet.
const DEFAULT_UNPUBLISHED_SANDBOX_IMAGE =
  'ghcr.io/haseeb-heaven/open-agent-sandbox:4.0.0';

const VALID_SANDBOX_COMMANDS = [
  'docker',
  'podman',
  'sandbox-exec',
  'runsc',
  'lxc',
  'windows-native',
];

function isSandboxCommand(
  value: string,
): value is Exclude<SandboxConfig['command'], undefined> {
  return (VALID_SANDBOX_COMMANDS as ReadonlyArray<string | undefined>).includes(
    value,
  );
}

function getSandboxCommand(
  sandbox?: boolean | string | null,
): SandboxConfig['command'] | '' {
  // If the SANDBOX env var is set, we're already inside the sandbox.
  if (process.env['SANDBOX']) {
    return '';
  }

  // note environment variable takes precedence over argument (from command line or settings)
  const environmentConfiguredSandbox =
    process.env['OPENAGENT_SANDBOX']?.toLowerCase().trim() ??
    process.env['GEMINI_SANDBOX']?.toLowerCase().trim() ??
    '';
  sandbox =
    environmentConfiguredSandbox?.length > 0
      ? environmentConfiguredSandbox
      : sandbox;
  if (sandbox === '1' || sandbox === 'true') sandbox = true;
  else if (sandbox === '0' || sandbox === 'false' || !sandbox) sandbox = false;

  if (sandbox === false) {
    return '';
  }

  if (typeof sandbox === 'string' && sandbox) {
    if (!isSandboxCommand(sandbox)) {
      throw new FatalSandboxError(
        `Invalid sandbox command '${sandbox}'. Must be one of ${VALID_SANDBOX_COMMANDS.join(
          ', ',
        )}`,
      );
    }
    // runsc (gVisor) is only supported on Linux
    if (sandbox === 'runsc' && os.platform() !== 'linux') {
      throw new FatalSandboxError(
        'gVisor (runsc) sandboxing is only supported on Linux',
      );
    }
    // windows-native is only supported on Windows
    if (sandbox === 'windows-native' && os.platform() !== 'win32') {
      throw new FatalSandboxError(
        'Windows native sandboxing is only supported on Windows',
      );
    }

    // confirm that specified command exists (unless it's built-in)
    if (sandbox !== 'windows-native' && !commandExists.sync(sandbox)) {
      throw new FatalSandboxError(
        `Missing sandbox command '${sandbox}' (from OPENAGENT_SANDBOX)`,
      );
    }
    // runsc uses Docker with --runtime=runsc; both must be available (prioritize runsc when explicitly chosen)
    if (sandbox === 'runsc' && !commandExists.sync('docker')) {
      throw new FatalSandboxError(
        "runsc (gVisor) requires Docker. Install Docker, or use sandbox: 'docker'.",
      );
    }
    return sandbox;
  }

  // look for seatbelt, docker, or podman, in that order
  // for container-based sandboxing, require sandbox to be enabled explicitly
  // note: runsc is NOT auto-detected, it must be explicitly specified
  if (os.platform() === 'darwin' && commandExists.sync('sandbox-exec')) {
    return 'sandbox-exec';
  } else if (commandExists.sync('docker') && sandbox === true) {
    return 'docker';
  } else if (commandExists.sync('podman') && sandbox === true) {
    return 'podman';
  }

  // throw an error if user requested sandbox but no command was found
  if (sandbox === true) {
    throw new FatalSandboxError(
      'OPENAGENT_SANDBOX is true but failed to determine command for sandbox; ' +
        'install docker or podman or specify command in OPENAGENT_SANDBOX',
    );
  }

  return '';
  // Note: 'lxc' is intentionally not auto-detected because it requires a
  // pre-existing, running container managed by the user. Use
  // GEMINI_SANDBOX=lxc or sandbox: "lxc" in settings to enable it.
}

export async function loadSandboxConfig(
  settings: Settings,
  argv: SandboxCliArgs,
): Promise<SandboxConfig | undefined> {
  const sandboxOption = argv.sandbox ?? settings.tools?.sandbox;

  let sandboxValue: boolean | string | null | undefined;
  let allowedPaths: string[] = [];
  let networkAccess = true;
  let customImage: string | undefined;

  if (
    typeof sandboxOption === 'object' &&
    sandboxOption !== null &&
    !Array.isArray(sandboxOption)
  ) {
    const config = sandboxOption;
    sandboxValue = config.enabled ? (config.command ?? true) : false;
    allowedPaths = config.allowedPaths ?? [];
    networkAccess = config.networkAccess ?? true;
    customImage = config.image;
  } else if (typeof sandboxOption !== 'object' || sandboxOption === null) {
    sandboxValue = sandboxOption;
  }

  const command = getSandboxCommand(sandboxValue);

  const packageJson = await getPackageJson(__dirname);
  const image =
    process.env['OPENAGENT_SANDBOX_IMAGE'] ??
    process.env['GEMINI_SANDBOX_IMAGE'] ??
    process.env['OPENAGENT_SANDBOX_IMAGE_DEFAULT'] ??
    process.env['GEMINI_SANDBOX_IMAGE_DEFAULT'] ??
    customImage ??
    packageJson?.config?.sandboxImageUri;

  const isNative =
    command === 'windows-native' ||
    command === 'sandbox-exec' ||
    command === 'lxc';

  const isContainerCommand = command === 'docker' || command === 'podman';
  if (isContainerCommand && image === DEFAULT_UNPUBLISHED_SANDBOX_IMAGE) {
    throw new FatalSandboxError(
      `The default OpenAgent sandbox image ('${DEFAULT_UNPUBLISHED_SANDBOX_IMAGE}') ` +
        'has not been published yet. Build it locally with `npm run build:sandbox` ' +
        'and set OPENAGENT_SANDBOX_IMAGE to the local tag, or point OPENAGENT_SANDBOX_IMAGE ' +
        'at another image.',
    );
  }

  return command && (image || isNative)
    ? { enabled: true, allowedPaths, networkAccess, command, image }
    : undefined;
}

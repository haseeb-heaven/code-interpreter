/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * This project's own internal signaling env vars were originally named
 * GEMINI_CLI_*. They are now OPENAGENT_CLI_*, with the old name still read
 * as a fallback for one deprecation window so existing saved environments
 * (.env files, CI configs) don't silently break. The new name always wins
 * when both are set.
 */
export function readCliEnvAlias(
  suffix: string,
  env: NodeJS.ProcessEnv = process.env,
): string | undefined {
  return env[`OPENAGENT_CLI_${suffix}`] ?? env[`GEMINI_CLI_${suffix}`];
}

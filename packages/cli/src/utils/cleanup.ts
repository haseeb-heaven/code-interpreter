/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { promises as fs } from 'node:fs';
import { join } from 'node:path';
import {
  Storage,
  shutdownTelemetry,
  isTelemetrySdkInitialized,
  ExitCodes,
  resetBrowserSession,
} from '@open-agent/core';
import type { Config } from '@open-agent/core';

const cleanupFunctions: Array<(() => void) | (() => Promise<void>)> = [];
const syncCleanupFunctions: Array<() => void> = [];
let configForTelemetry: Config | null = null;
let isShuttingDown = false;
let pendingForceExitTimer: ReturnType<typeof setTimeout> | null = null;

export function registerCleanup(fn: (() => void) | (() => Promise<void>)) {
  cleanupFunctions.push(fn);
}

export function removeCleanup(fn: (() => void) | (() => Promise<void>)) {
  const index = cleanupFunctions.indexOf(fn);
  if (index !== -1) {
    cleanupFunctions.splice(index, 1);
  }
}

export function registerSyncCleanup(fn: () => void) {
  syncCleanupFunctions.push(fn);
}

export function removeSyncCleanup(fn: () => void) {
  const index = syncCleanupFunctions.indexOf(fn);
  if (index !== -1) {
    syncCleanupFunctions.splice(index, 1);
  }
}

/**
 * Resets the internal cleanup state for testing purposes.
 * This allows tests to run in isolation without vi.resetModules().
 */
export function resetCleanupForTesting() {
  cleanupFunctions.length = 0;
  syncCleanupFunctions.length = 0;
  configForTelemetry = null;
  isShuttingDown = false;
  if (pendingForceExitTimer) {
    clearTimeout(pendingForceExitTimer);
    pendingForceExitTimer = null;
  }
}

export function runSyncCleanup() {
  for (const fn of syncCleanupFunctions) {
    try {
      fn();
    } catch {
      // Ignore errors during cleanup.
    }
  }
  syncCleanupFunctions.length = 0;
}

/**
 * Forcing process.exit() while another async handle (e.g. an in-flight
 * network socket, MCP child process pipe, or fetch AbortController) is
 * mid-teardown races libuv's own handle-close bookkeeping on Windows,
 * observed as a native "Assertion failed: !(handle->flags &
 * UV_HANDLE_CLOSING), file src\win\async.c, line 76" that aborts the
 * process instead of exiting cleanly. Setting exitCode and letting the
 * event loop drain naturally gives libuv time to close handles in the
 * normal order; process.exit() is only used as a last resort if the loop
 * doesn't drain on its own within the grace period.
 */
export function exitProcess(code: number): void {
  process.exitCode = code;
  if (pendingForceExitTimer) {
    clearTimeout(pendingForceExitTimer);
  }
  pendingForceExitTimer = setTimeout(() => process.exit(code), 2000);
  pendingForceExitTimer.unref();
}

/**
 * Thrown by terminateProcess() to unwind synchronously out of whatever
 * loop/handler is currently running, after the deferred exit has already
 * been scheduled via exitProcess(). Callers that catch generic errors
 * (e.g. to route them through handleError) must check for this signal and
 * rethrow it rather than treating it as an application error.
 */
export class ProcessExitSignal extends Error {
  constructor(readonly code: number) {
    super('__process_exit_signal__');
    this.name = 'ProcessExitSignal';
  }
}

/**
 * Schedules a safe deferred exit (see exitProcess) and then throws to halt
 * synchronous execution, matching the previous behavior of a raw
 * process.exit() call without the Windows libuv crash risk. Callers
 * upstream (nonInteractiveCli's error catch, index.ts's top-level catch)
 * must recognize ProcessExitSignal and let it propagate rather than
 * re-handling it as an application error.
 */
export function terminateProcess(code: number): never {
  exitProcess(code);
  throw new ProcessExitSignal(code);
}

/**
 * Register the config instance for telemetry shutdown.
 * This must be called early in the application lifecycle.
 */
export function registerTelemetryConfig(config: Config) {
  configForTelemetry = config;
}

export async function runExitCleanup() {
  // drain stdin to prevent printing garbage on exit
  // https://github.com/haseeb-heaven/open-agent/issues/16801
  await drainStdin();

  runSyncCleanup();
  for (const fn of cleanupFunctions) {
    try {
      await fn();
    } catch {
      // Ignore errors during cleanup.
    }
  }
  cleanupFunctions.length = 0; // Clear the array

  // Close persistent browser sessions before disposing config
  try {
    await resetBrowserSession();
  } catch {
    // Ignore errors during browser cleanup
  }

  if (configForTelemetry) {
    try {
      await configForTelemetry.dispose();
    } catch {
      // Ignore errors during disposal
    }
  }

  // IMPORTANT: Shutdown telemetry AFTER all other cleanup functions have run
  // This ensures SessionEnd hooks and other telemetry are properly flushed
  if (configForTelemetry && isTelemetrySdkInitialized()) {
    try {
      await shutdownTelemetry(configForTelemetry);
    } catch {
      // Ignore errors during telemetry shutdown
    }
  }
}

async function drainStdin() {
  if (!process.stdin?.isTTY) return;
  // Resume stdin and attach a no-op listener to drain the buffer.
  // We use removeAllListeners to ensure we don't trigger other handlers.
  process.stdin
    .resume()
    .removeAllListeners('data')
    .on('data', () => {});
  // Give it a moment to flush the OS buffer.
  await new Promise((resolve) => setTimeout(resolve, 50));
}

/**
 * Gracefully shuts down the process, ensuring cleanup runs exactly once.
 * Guards against concurrent shutdown from signals (SIGHUP, SIGTERM, SIGINT)
 * and TTY loss detection racing each other.
 *
 * @see https://github.com/haseeb-heaven/open-agent/issues/15874
 */
async function gracefulShutdown(_reason: string) {
  if (isShuttingDown) {
    return;
  }
  isShuttingDown = true;

  await runExitCleanup();
  process.exit(ExitCodes.SUCCESS);
}

export function setupSignalHandlers() {
  process.on('SIGHUP', () => gracefulShutdown('SIGHUP'));
  process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
  process.on('SIGINT', () => gracefulShutdown('SIGINT'));
}

export function setupTtyCheck(): () => void {
  let intervalId: ReturnType<typeof setInterval> | null = null;
  let isCheckingTty = false;

  intervalId = setInterval(async () => {
    if (isCheckingTty || isShuttingDown) {
      return;
    }

    if (process.env['SANDBOX']) {
      return;
    }

    if (!process.stdin.isTTY && !process.stdout.isTTY) {
      isCheckingTty = true;

      if (intervalId) {
        clearInterval(intervalId);
        intervalId = null;
      }

      await gracefulShutdown('TTY loss');
    }
  }, 5000);

  // Don't keep the process alive just for this interval
  intervalId.unref();

  return () => {
    if (intervalId) {
      clearInterval(intervalId);
      intervalId = null;
    }
  };
}

export async function cleanupCheckpoints() {
  const storage = new Storage(process.cwd());
  await storage.initialize();
  const tempDir = storage.getProjectTempDir();
  const checkpointsDir = join(tempDir, 'checkpoints');
  try {
    await fs.rm(checkpointsDir, { recursive: true, force: true });
  } catch {
    // Ignore errors if the directory doesn't exist or fails to delete.
  }
}

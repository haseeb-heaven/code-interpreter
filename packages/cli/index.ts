#!/usr/bin/env node

/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { spawn } from 'node:child_process';
import os from 'node:os';
import v8 from 'node:v8';
import {
  RELAUNCH_EXIT_CODE,
  getSpawnConfig,
  getScriptArgs,
} from './src/utils/processUtils.js';

// --- Global Entry Point ---

// Forcing process.exit() while another async handle (e.g. an in-flight
// network socket, MCP child process pipe, or fetch AbortController) is
// mid-teardown races libuv's own handle-close bookkeeping on Windows,
// observed as a native "Assertion failed: !(handle->flags &
// UV_HANDLE_CLOSING), file src\win\async.c, line 76" that aborts the
// process instead of exiting cleanly. Setting exitCode and letting the
// event loop drain naturally gives libuv time to close handles in the
// normal order; process.exit() is only used as a last resort if the loop
// doesn't drain on its own within the grace period.
function exitProcess(code: number): void {
  process.exitCode = code;
  const forceExitTimer = setTimeout(() => process.exit(code), 2000);
  forceExitTimer.unref();
}

// Suppress known race condition error in node-pty on Windows and Linux
// Tracking bug: https://github.com/microsoft/node-pty/issues/827
process.on('uncaughtException', (error) => {
  if (error instanceof Error) {
    const message = error.message || '';
    const isPtyResizeError =
      message === 'Cannot resize a pty that has already exited';
    const isEbadfError =
      message.includes('EBADF') ||
      (error as { code?: string }).code === 'EBADF';
    const isFromNodePty =
      error.stack?.includes('node-pty') || error.stack?.includes('PtyResize');

    if ((isPtyResizeError || isEbadfError) && isFromNodePty) {
      // This error happens with node-pty when resizing a pty that has just exited.
      // It is a race condition in node-pty that we cannot prevent, so we silence it.
      return;
    }
  }

  // For other errors, we rely on the default behavior, but since we attached a listener,
  // we must manually replicate it.
  if (error instanceof Error) {
    process.stderr.write(error.stack + '\n');
  } else {
    process.stderr.write(String(error) + '\n');
  }
  exitProcess(1);
});

async function getMemoryNodeArgs(): Promise<string[]> {
  let autoConfigureMemory = true;
  try {
    const { readFileSync } = await import('node:fs');
    const { join } = await import('node:path');
    // Respect OPENAGENT_HOME (or legacy GEMINI_CLI_HOME) env var, falling
    // back to ~/.openagent.
    const baseDir =
      process.env['OPENAGENT_HOME'] ||
      process.env['GEMINI_CLI_HOME'] ||
      join(os.homedir(), '.openagent');
    const settingsPath = join(baseDir, 'settings.json');
    const rawSettings = readFileSync(settingsPath, 'utf8');
    const settings = JSON.parse(rawSettings);
    if (settings?.advanced?.autoConfigureMemory === false) {
      autoConfigureMemory = false;
    }
  } catch {
    // ignore
  }

  if (autoConfigureMemory) {
    const totalMemoryMB = os.totalmem() / (1024 * 1024);
    const heapStats = v8.getHeapStatistics();
    const currentMaxOldSpaceSizeMb = Math.floor(
      heapStats.heap_size_limit / 1024 / 1024,
    );
    const targetMaxOldSpaceSizeInMB = Math.floor(totalMemoryMB * 0.5);

    if (targetMaxOldSpaceSizeInMB > currentMaxOldSpaceSizeMb) {
      return [`--max-old-space-size=${targetMaxOldSpaceSizeInMB}`];
    }
  }

  return [];
}

async function run() {
  if (
    !process.env['OPENAGENT_NO_RELAUNCH'] &&
    !process.env['GEMINI_CLI_NO_RELAUNCH'] &&
    !process.env['SANDBOX']
  ) {
    // --- Lightweight Parent Process / Daemon ---
    // We avoid importing heavy dependencies here to save ~1.5s of startup time.

    const scriptArgs = getScriptArgs();
    const memoryArgs = await getMemoryNodeArgs();
    const { spawnArgs, env: newEnv } = getSpawnConfig(memoryArgs, scriptArgs);

    let latestAdminSettings: unknown = undefined;

    // Prevent the parent process from exiting prematurely on signals.
    // The child process will receive the same signals and handle its own cleanup.
    for (const sig of ['SIGINT', 'SIGTERM', 'SIGHUP']) {
      process.on(sig as NodeJS.Signals, () => {});
    }

    const runner = () => {
      process.stdin.pause();

      const child = spawn(process.execPath, spawnArgs, {
        stdio: ['inherit', 'inherit', 'inherit', 'ipc'],
        env: newEnv,
      });

      if (latestAdminSettings) {
        child.send({ type: 'admin-settings', settings: latestAdminSettings });
      }

      child.on('message', (msg: { type?: string; settings?: unknown }) => {
        if (msg.type === 'admin-settings-update' && msg.settings) {
          latestAdminSettings = msg.settings;
        }
      });

      return new Promise<number>((resolve) => {
        child.on('error', (err) => {
          process.stderr.write(
            'Error: Failed to start child process: ' + err.message + '\n',
          );
          resolve(1);
        });
        child.on('close', (code) => {
          process.stdin.resume();
          resolve(code ?? 1);
        });
      });
    };

    while (true) {
      try {
        const exitCode = await runner();
        if (process.platform === 'android' || exitCode !== RELAUNCH_EXIT_CODE) {
          process.exit(exitCode);
        }
      } catch (error: unknown) {
        process.stdin.resume();
        process.stderr.write(
          `Fatal error: Failed to relaunch the CLI process.\n${error instanceof Error ? (error.stack ?? error.message) : String(error)}\n`,
        );
        process.exit(1);
      }
    }
  } else {
    // --- Heavy Child Process ---
    // Now we can safely import everything.
    const { main } = await import('./src/gemini.js');
    const { FatalError, writeToStderr, parseAndFormatApiError } = await import(
      '@open-agent/core'
    );
    const { runExitCleanup, ProcessExitSignal } = await import(
      './src/utils/cleanup.js'
    );

    main().catch(async (error: unknown) => {
      // terminateProcess() (used by handleError/handleCancellationError/etc.
      // for JSON/stream-json output) throws this after already scheduling a
      // safe deferred exit via exitProcess() - the exit code and any output
      // formatting were already handled there, so just let the process exit
      // as scheduled instead of re-running cleanup or reformatting it as a
      // generic uncaught error.
      if (error instanceof ProcessExitSignal) {
        return;
      }

      // Set a timeout to force exit if cleanup hangs
      const cleanupTimeout = setTimeout(() => {
        writeToStderr('Cleanup timed out, forcing exit...\n');
        exitProcess(1);
      }, 5000);

      try {
        await runExitCleanup();
      } catch (cleanupError: unknown) {
        writeToStderr(
          `Error during final cleanup: ${cleanupError instanceof Error ? cleanupError.message : String(cleanupError)}\n`,
        );
      } finally {
        clearTimeout(cleanupTimeout);
      }

      if (error instanceof FatalError) {
        let errorMessage = error.message;
        if (!process.env['NO_COLOR']) {
          errorMessage = `\x1b[31m${errorMessage}\x1b[0m`;
        }
        writeToStderr(errorMessage + '\n');
        exitProcess(error.exitCode);
        return;
      }

      // Most uncaught rejections reaching here are unwrapped API errors
      // (nonInteractiveCli's handleError re-throws in TEXT mode so callers
      // can format/exit themselves). Use the same formatter errors.ts uses
      // so the user sees a readable message instead of a raw stack dump
      // (or "[object Object]" when the rejection isn't even an Error).
      writeToStderr(parseAndFormatApiError(error) + '\n');
      exitProcess(1);
    });
  }
}

run();

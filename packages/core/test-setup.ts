/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import path from 'node:path';
import { fileURLToPath } from 'node:url';
import dotenv from 'dotenv';

// Load repo-root .env for live websearch / provider probes (does not override
// vars already set in the shell). Unit tests still mock or stub as needed.
const _repoRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../..',
);
dotenv.config({ path: path.join(_repoRoot, '.env') });
dotenv.config({ path: path.join(process.cwd(), '.env') });

// Unset NO_COLOR environment variable to ensure consistent theme behavior between local and CI test runs
if (process.env.NO_COLOR !== undefined) {
  delete process.env.NO_COLOR;
}

// oauth2.ts reads GOOGLE_OAUTH_CLIENT_ID once at module load to validate
// LOGIN_WITH_GOOGLE requests (see code_assist/oauth2.ts). Provide a fake
// fallback so tests that exercise that flow don't need to stub it
// individually; this runs before any test file's imports resolve.
if (!process.env['GOOGLE_OAUTH_CLIENT_ID']) {
  process.env['GOOGLE_OAUTH_CLIENT_ID'] =
    'test-client-id.apps.googleusercontent.com';
}

import { setSimulate429 } from './src/utils/testUtils.js';
import { vi, afterEach } from 'vitest';
import { coreEvents } from './src/utils/events.js';

// Increase max listeners to avoid warnings in large test suites
coreEvents.setMaxListeners(100);

// Disable 429 simulation globally for all tests
setSimulate429(false);

afterEach(() => {
  vi.unstubAllEnvs();
});

// Default mocks for Storage and ProjectRegistry to prevent disk access in most tests.
// These can be overridden in specific tests using vi.unmock().

vi.mock('./src/config/projectRegistry.js', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('./src/config/projectRegistry.js')>();
  actual.ProjectRegistry.prototype.initialize = vi.fn(() =>
    Promise.resolve(undefined),
  );
  actual.ProjectRegistry.prototype.getShortId = vi.fn(() =>
    Promise.resolve('project-slug'),
  );
  return actual;
});

vi.mock('./src/config/storageMigration.js', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('./src/config/storageMigration.js')>();
  actual.StorageMigration.migrateDirectory = vi.fn(() =>
    Promise.resolve(undefined),
  );
  return actual;
});

vi.mock('./src/config/storage.js', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('./src/config/storage.js')>();
  actual.Storage.prototype.initialize = vi.fn(() => Promise.resolve(undefined));
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (actual.Storage.prototype as any).getProjectIdentifier = vi.fn(
    () => 'project-slug',
  );
  return actual;
});

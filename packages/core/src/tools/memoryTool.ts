/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import * as path from 'node:path';
import { Storage } from '../config/storage.js';
import { resolveToRealPath } from '../utils/paths.js';

export const DEFAULT_CONTEXT_FILENAME = 'OPENAGENT.md';
// Ordered discovery fallbacks: OPENAGENT.md is written for new files; AGENTS.md
// and GEMINI.md are recognized so existing projects (or ones authored for other
// agent CLIs) keep working without a migration step.
export const DEFAULT_CONTEXT_FILENAMES: string[] = [
  DEFAULT_CONTEXT_FILENAME,
  'AGENTS.md',
  'GEMINI.md',
];
export const PROJECT_MEMORY_INDEX_FILENAME = 'MEMORY.md';

// This variable will hold the currently configured context filenames.
// It defaults to DEFAULT_CONTEXT_FILENAMES but can be extended by setContextFilename.
let currentGeminiMdFilename: string | string[] = DEFAULT_CONTEXT_FILENAMES;

/**
 * Adds one or more filenames to the current context filenames.
 * Ensures uniqueness and maintains order.
 */
export function setContextFilename(newFilename: string | string[]): void {
  const filenames = Array.isArray(newFilename) ? newFilename : [newFilename];
  const current = getAllContextFilenames();
  const next = new Set<string>();

  for (const filename of filenames) {
    const trimmed = filename.trim();
    if (trimmed !== '') {
      const normalized = path.normalize(trimmed);
      // Sanitize to prevent path traversal while allowing subdirectories
      const validatedPath = resolveToRealPath(normalized);
      if (validatedPath) {
        next.add(normalized);
      }
    }
  }

  for (const filename of current) {
    next.add(filename);
  }

  const result = Array.from(next);
  if (result.length > 1) {
    currentGeminiMdFilename = result;
  } else if (result.length === 1) {
    currentGeminiMdFilename = result[0];
  }
}

/**
 * Resets the context filenames to the provided value, or the default if none provided.
 * This replaces all current filenames.
 */
export function resetContextFilename(
  filename: string | string[] = DEFAULT_CONTEXT_FILENAMES,
): void {
  const filenames = Array.isArray(filename) ? filename : [filename];
  const cleaned = Array.from(
    new Set(
      filenames
        .map((f) => path.normalize(f.trim()))
        .filter((f) => !!resolveToRealPath(f)),
    ),
  );

  if (cleaned.length === 0) {
    currentGeminiMdFilename = DEFAULT_CONTEXT_FILENAMES;
  } else if (cleaned.length === 1) {
    currentGeminiMdFilename = cleaned[0];
  } else {
    currentGeminiMdFilename = cleaned;
  }
}

export function getCurrentContextFilename(): string {
  if (Array.isArray(currentGeminiMdFilename)) {
    return currentGeminiMdFilename[0];
  }
  return currentGeminiMdFilename;
}

export function getAllContextFilenames(): string[] {
  if (Array.isArray(currentGeminiMdFilename)) {
    return currentGeminiMdFilename;
  }
  return [currentGeminiMdFilename];
}

/** @deprecated Use {@link setContextFilename} instead. */
export const setGeminiMdFilename = setContextFilename;
/** @deprecated Use {@link resetContextFilename} instead. */
export const resetGeminiMdFilename = resetContextFilename;
/** @deprecated Use {@link getCurrentContextFilename} instead. */
export const getCurrentGeminiMdFilename = getCurrentContextFilename;
/** @deprecated Use {@link getAllContextFilenames} instead. */
export const getAllGeminiMdFilenames = getAllContextFilenames;

export function getGlobalMemoryFilePath(): string {
  return path.join(Storage.getGlobalGeminiDir(), getCurrentGeminiMdFilename());
}

export function getProjectMemoryIndexFilePath(storage: Storage): string {
  return path.join(
    storage.getProjectMemoryDir(),
    PROJECT_MEMORY_INDEX_FILENAME,
  );
}

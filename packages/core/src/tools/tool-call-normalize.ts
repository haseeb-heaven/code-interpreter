/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Normalizes model tool calls before registry lookup / validation.
 *
 * Recovers common failures from weaker multi-provider models:
 * - display / class / placeholder names
 * - calling grep (SearchText) with file-glob args (FindFiles shape)
 * - using `*.*` / `**\/*.txt` as a regex content pattern
 * - parameter aliases (`path` vs `dir_path` / `file_path`, `cmd` vs `command`)
 */

import {
  GLOB_TOOL_NAME,
  GREP_TOOL_NAME,
  LS_TOOL_NAME,
  READ_FILE_TOOL_NAME,
  READ_MANY_FILES_TOOL_NAME,
  SHELL_TOOL_NAME,
  WRITE_FILE_TOOL_NAME,
  resolveCanonicalToolName,
  TOOL_LEGACY_ALIASES,
} from './tool-names.js';

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function isBooleanValue(value: unknown): value is boolean {
  return typeof value === 'boolean';
}

function isNumberValue(value: unknown): value is number {
  return typeof value === 'number' && !Number.isNaN(value);
}

/**
 * True when `pattern` looks like a filename glob rather than a content regex.
 * Examples: `*.*`, `*.txt`, `**\/*.md`, `src/**\/*.ts`
 */
export function looksLikeFileGlobPattern(pattern: string): boolean {
  const p = pattern.trim();
  if (!p) return false;

  // Pure extension / multi-ext globs (invalid or nonsense as regex)
  if (/^\*\.[\w.*?{},-]+$/.test(p)) return true;
  if (/^\*\*\/.+/.test(p)) return true;
  if (/^[\w./-]*\*[\w.*?{},./-]*$/.test(p) && /[*?]/.test(p)) {
    // Path-ish globs with * or ?
    // Reject pure content regexes like `foo.*bar` without path separators / ext form
    if (
      p.includes('/') ||
      p.includes('\\') ||
      /^\*\./.test(p) ||
      p.endsWith('.*')
    ) {
      // `*.*` ends with .* — treat as glob when it also starts with *
      if (/^\*+\./.test(p) || p.includes('/') || p.includes('**')) {
        return true;
      }
    }
  }

  // If it is not a valid JS regex, and uses glob metacharacters, treat as glob.
  if (/[*?[{]/.test(p)) {
    try {
       
      new RegExp(p);
    } catch {
      return true;
    }
  }

  return false;
}

/**
 * Grep/SearchText was called with FindFiles/glob-shaped arguments.
 */
export function isGlobShapedSearchArgs(args: Record<string, unknown>): boolean {
  if (!isNonEmptyString(args['pattern'])) {
    return false;
  }

  const hasGlobOnlyFlags =
    isBooleanValue(args['case_sensitive']) ||
    isBooleanValue(args['respect_git_ignore']) ||
    isBooleanValue(args['respect_gemini_ignore']);

  const hasGrepOnlyFlags =
    isNonEmptyString(args['include_pattern']) ||
    isNonEmptyString(args['exclude_pattern']) ||
    isBooleanValue(args['names_only']) ||
    isBooleanValue(args['fixed_strings']) ||
    isNumberValue(args['max_matches_per_file']) ||
    isNumberValue(args['total_max_matches']) ||
    isNumberValue(args['context']) ||
    isNumberValue(args['after']) ||
    isNumberValue(args['before']);

  if (hasGlobOnlyFlags && !hasGrepOnlyFlags) {
    return true;
  }

  if (!hasGrepOnlyFlags && looksLikeFileGlobPattern(String(args['pattern']))) {
    return true;
  }

  return false;
}

function pickGlobArgs(args: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {
    pattern: args['pattern'],
  };
  if (isNonEmptyString(args['dir_path'])) {
    out['dir_path'] = args['dir_path'];
  }
  if (isBooleanValue(args['case_sensitive'])) {
    out['case_sensitive'] = args['case_sensitive'];
  }
  if (isBooleanValue(args['respect_git_ignore'])) {
    out['respect_git_ignore'] = args['respect_git_ignore'];
  }
  if (isBooleanValue(args['respect_gemini_ignore'])) {
    out['respect_gemini_ignore'] = args['respect_gemini_ignore'];
  }
  return out;
}

function isGrepToolName(name: string): boolean {
  const canonical = TOOL_LEGACY_ALIASES[name] ?? name;
  return (
    canonical === GREP_TOOL_NAME ||
    name.toLowerCase() === GREP_TOOL_NAME ||
    name.toLowerCase() === 'searchtext' ||
    name.toLowerCase() === 'grep' ||
    name.toLowerCase() === 'greptool'
  );
}

export interface NormalizedToolCall {
  /** Canonical tool name after recovery. */
  name: string;
  /** Possibly rewritten args. */
  args: unknown;
  /** Present when the call was remapped from another tool. */
  remappedFrom?: string;
}

/**
 * First non-empty string among candidate keys on `args`.
 */
function firstString(
  args: Record<string, unknown>,
  keys: string[],
): string | undefined {
  for (const key of keys) {
    const value = args[key];
    if (isNonEmptyString(value)) {
      return value;
    }
  }
  return undefined;
}

/**
 * Recover common parameter aliases weaker models emit
 * (e.g. `path` instead of `dir_path` / `file_path`).
 */
export function normalizeToolArgs(toolName: string, args: unknown): unknown {
  if (!isRecord(args)) {
    return args;
  }
  const out: Record<string, unknown> = { ...args };
  const canonical = TOOL_LEGACY_ALIASES[toolName] ?? toolName;

  if (canonical === LS_TOOL_NAME || toolName === 'list_directory') {
    if (!isNonEmptyString(out['dir_path'])) {
      const alt = firstString(out, [
        'path',
        'directory',
        'directory_path',
        'dir',
        'folder',
        'target_directory',
        'target_dir',
      ]);
      // Default to workspace root when the model omits the path entirely
      // (common on free/weak models that still intend "list here").
      out['dir_path'] = alt ?? '.';
    }
  }

  if (
    canonical === READ_FILE_TOOL_NAME ||
    canonical === WRITE_FILE_TOOL_NAME ||
    toolName === 'read_file' ||
    toolName === 'write_file'
  ) {
    if (!isNonEmptyString(out['file_path'])) {
      const alt = firstString(out, [
        'path',
        'file',
        'filename',
        'filepath',
        'target_file',
      ]);
      if (alt) out['file_path'] = alt;
    }
  }

  if (canonical === SHELL_TOOL_NAME || toolName === 'run_shell_command') {
    if (!isNonEmptyString(out['command'])) {
      const alt = firstString(out, ['cmd', 'shell', 'script', 'code']);
      if (alt) out['command'] = alt;
    }
  }

  if (canonical === GLOB_TOOL_NAME) {
    if (!isNonEmptyString(out['pattern'])) {
      const alt = firstString(out, ['glob', 'glob_pattern', 'file_pattern']);
      if (alt) out['pattern'] = alt;
    }
    // Glob's schema uses `path` (search root). Accept common aliases without
    // also forcing a duplicate when `dir_path` was only used for grep remap.
    if (!isNonEmptyString(out['path'])) {
      const alt = firstString(out, ['directory', 'cwd', 'root', 'dir']);
      if (alt) {
        out['path'] = alt;
      } else if (isNonEmptyString(out['dir_path'])) {
        out['path'] = out['dir_path'];
        delete out['dir_path'];
      }
    } else if ('dir_path' in out && out['dir_path'] === out['path']) {
      delete out['dir_path'];
    }
  }

  if (canonical === READ_MANY_FILES_TOOL_NAME) {
    if (!Array.isArray(out['include'])) {
      const single = firstString(out, [
        'path',
        'file_path',
        'file',
        'include_path',
      ]);
      if (single) out['include'] = [single];
    }
  }

  return out;
}

/**
 * Normalize a model-emitted tool call name + args for OpenAgent execution.
 */
export function normalizeToolCallRequest(
  name: string,
  args: unknown,
  options: { knownNames?: readonly string[] } = {},
): NormalizedToolCall {
  const resolvedName = resolveCanonicalToolName(name, {
    knownNames: options.knownNames,
    args,
  });

  // Empty placeholder tool names cannot be recovered — leave as-is so the
  // scheduler returns a clear "not found" + available tools list.
  if (
    (resolvedName === 'generic_tool' || name === 'generic_tool') &&
    (!isRecord(args) || Object.keys(args).length === 0)
  ) {
    return { name: 'generic_tool', args: args ?? {} };
  }

  if (
    isRecord(args) &&
    isGrepToolName(resolvedName) &&
    isGlobShapedSearchArgs(args)
  ) {
    return {
      name: GLOB_TOOL_NAME,
      args: normalizeToolArgs(GLOB_TOOL_NAME, pickGlobArgs(args)),
      remappedFrom: resolvedName,
    };
  }

  // Also when the model used the display name SearchText but args are glob-shaped
  // before alias resolution (already handled by isGrepToolName on original).
  if (
    isRecord(args) &&
    isGrepToolName(name) &&
    resolvedName !== GLOB_TOOL_NAME &&
    isGlobShapedSearchArgs(args)
  ) {
    return {
      name: GLOB_TOOL_NAME,
      args: normalizeToolArgs(GLOB_TOOL_NAME, pickGlobArgs(args)),
      remappedFrom: name,
    };
  }

  return {
    name: resolvedName,
    args: normalizeToolArgs(resolvedName, args),
  };
}

/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect } from 'vitest';
import {
  looksLikeFileGlobPattern,
  isGlobShapedSearchArgs,
  normalizeToolCallRequest,
} from './tool-call-normalize.js';
import {
  GLOB_TOOL_NAME,
  GREP_TOOL_NAME,
  SHELL_TOOL_NAME,
} from './tool-names.js';

describe('looksLikeFileGlobPattern', () => {
  it('detects extension globs', () => {
    expect(looksLikeFileGlobPattern('*.*')).toBe(true);
    expect(looksLikeFileGlobPattern('*.txt')).toBe(true);
    expect(looksLikeFileGlobPattern('**/*.md')).toBe(true);
    expect(looksLikeFileGlobPattern('src/**/*.ts')).toBe(true);
  });

  it('rejects normal content regexes', () => {
    expect(looksLikeFileGlobPattern('TODO|FIXME')).toBe(false);
    expect(looksLikeFileGlobPattern('model id')).toBe(false);
    expect(looksLikeFileGlobPattern('function\\s+foo')).toBe(false);
  });
});

describe('isGlobShapedSearchArgs', () => {
  it('detects FindFiles-style args misrouted to SearchText', () => {
    expect(
      isGlobShapedSearchArgs({
        pattern: '*.*',
        dir_path: 'D:/Code/open-agent',
        case_sensitive: false,
        respect_git_ignore: true,
        respect_gemini_ignore: true,
      }),
    ).toBe(true);
  });

  it('does not treat real grep args as glob-shaped', () => {
    expect(
      isGlobShapedSearchArgs({
        pattern: 'TODO',
        include_pattern: '*.ts',
      }),
    ).toBe(false);
  });
});

describe('normalizeToolCallRequest', () => {
  it('remaps SearchText + glob pattern to glob', () => {
    const result = normalizeToolCallRequest('SearchText', {
      pattern: '*.*',
      dir_path: '.',
      case_sensitive: false,
      respect_git_ignore: true,
      respect_gemini_ignore: true,
    });
    expect(result.name).toBe(GLOB_TOOL_NAME);
    expect(result.remappedFrom).toBe(GREP_TOOL_NAME);
    // dir_path from grep-shaped calls is remapped to glob's `path` param
    expect(result.args).toEqual({
      pattern: '*.*',
      path: '.',
      case_sensitive: false,
      respect_git_ignore: true,
      respect_gemini_ignore: true,
    });
  });

  it('remaps grep_search with bare extension glob to glob', () => {
    const result = normalizeToolCallRequest('grep_search', {
      pattern: '**/*.txt',
    });
    expect(result.name).toBe(GLOB_TOOL_NAME);
    expect((result.args as { pattern: string }).pattern).toBe('**/*.txt');
  });

  it('keeps real content search on grep', () => {
    const result = normalizeToolCallRequest('SearchText', {
      pattern: 'model id',
      include_pattern: '*.md',
    });
    expect(result.name).toBe(GREP_TOOL_NAME);
  });

  it('still recovers generic_tool shell calls', () => {
    const result = normalizeToolCallRequest('generic_tool', {
      command: 'Get-Date',
      description: 'date',
    });
    expect(result.name).toBe(SHELL_TOOL_NAME);
  });

  it('resolves FindFiles display name to glob', () => {
    const result = normalizeToolCallRequest('FindFiles', {
      pattern: '**/*.{txt,md}',
    });
    expect(result.name).toBe(GLOB_TOOL_NAME);
  });

  it('maps path → dir_path for list_directory', () => {
    const result = normalizeToolCallRequest('list_directory', {
      path: 'scratch/live_user',
    });
    expect(result.name).toBe('list_directory');
    expect((result.args as { dir_path: string }).dir_path).toBe(
      'scratch/live_user',
    );
  });

  it('defaults list_directory dir_path to . when empty', () => {
    const result = normalizeToolCallRequest('list_directory', {});
    expect((result.args as { dir_path: string }).dir_path).toBe('.');
  });

  it('maps path → file_path for read_file', () => {
    const result = normalizeToolCallRequest('read_file', {
      path: 'README.md',
    });
    expect((result.args as { file_path: string }).file_path).toBe('README.md');
  });

  it('maps cmd → command for shell', () => {
    const result = normalizeToolCallRequest('run_shell_command', {
      cmd: 'Get-Date',
    });
    expect((result.args as { command: string }).command).toBe('Get-Date');
  });
});

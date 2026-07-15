/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import type { vi } from 'vitest';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fs from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import { byokCommand } from './byokCommand.js';
import { type CommandContext } from './types.js';
import { MessageType } from '../types.js';
import { createMockCommandContext } from '../../test-utils/mockCommandContext.js';

describe('byokCommand', () => {
  let mockContext: CommandContext;
  let dir: string;
  let previousCwd: string;

  beforeEach(() => {
    dir = fs.mkdtempSync(path.join(os.tmpdir(), 'byok-cmd-test-'));
    previousCwd = process.cwd();
    process.chdir(dir);
    delete process.env['GROQ_API_KEY'];
    mockContext = createMockCommandContext();
  });

  afterEach(() => {
    process.chdir(previousCwd);
    fs.rmSync(dir, { recursive: true, force: true });
    delete process.env['GROQ_API_KEY'];
  });

  it('lists providers and key status when called without args', async () => {
    await byokCommand.action!(mockContext, '');
    expect(mockContext.ui.addItem).toHaveBeenCalledWith(
      expect.objectContaining({
        type: MessageType.INFO,
        text: expect.stringContaining('/byok <provider> <api-key>'),
      }),
      expect.any(Number),
    );
    const text = (mockContext.ui.addItem as ReturnType<typeof vi.fn>).mock
      .calls[0][0].text as string;
    expect(text).toContain('groq');
    expect(text).toContain('GROQ_API_KEY');
    expect(text).not.toContain('ollama ');
  });

  it('writes the key to .env and reports newly available models', async () => {
    await byokCommand.action!(mockContext, 'groq gsk-test-123');

    const envFile = fs.readFileSync(path.join(dir, '.env'), 'utf8');
    expect(envFile).toContain('GROQ_API_KEY=gsk-test-123');
    expect(process.env['GROQ_API_KEY']).toBe('gsk-test-123');

    expect(mockContext.ui.addItem).toHaveBeenCalledWith(
      expect.objectContaining({
        type: MessageType.INFO,
        text: expect.stringContaining('Saved GROQ_API_KEY'),
      }),
      expect.any(Number),
    );
  });

  it('rejects unknown providers', async () => {
    await byokCommand.action!(mockContext, 'nope key');
    expect(mockContext.ui.addItem).toHaveBeenCalledWith(
      expect.objectContaining({
        type: MessageType.ERROR,
        text: expect.stringContaining('Unknown provider'),
      }),
      expect.any(Number),
    );
  });

  it('shows usage for malformed invocations', async () => {
    await byokCommand.action!(mockContext, 'only-one-arg');
    expect(mockContext.ui.addItem).toHaveBeenCalledWith(
      expect.objectContaining({
        type: MessageType.ERROR,
        text: expect.stringContaining('Usage: /byok'),
      }),
      expect.any(Number),
    );
  });
});

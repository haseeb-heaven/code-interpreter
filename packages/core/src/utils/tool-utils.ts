/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import {
  isTool,
  type AnyDeclarativeTool,
  type AnyToolInvocation,
} from '../index.js';
import { SHELL_TOOL_NAMES } from './shell-utils.js';
import { inferToolNameFromArgs } from '../tools/tool-names.js';
import levenshtein from 'fast-levenshtein';
import type { ToolCallResponseInfo } from '../scheduler/types.js';

/**
 * Validates if an object is a ToolCallResponseInfo.
 */
export function isToolCallResponseInfo(
  data: unknown,
): data is ToolCallResponseInfo {
  return (
    typeof data === 'object' &&
    data !== null &&
    'callId' in data &&
    'responseParts' in data
  );
}

/**
 * Generates a suggestion string for a tool name that was not found in the registry.
 * Prefers arg-shape hints (e.g. `{command}` → run_shell_command), then closest
 * Levenshtein matches within a reasonable distance threshold.
 * @param unknownToolName The tool name that was not found.
 * @param allToolNames The list of all available tool names.
 * @param topN The number of suggestions to return. Defaults to 3.
 * @param args Optional tool-call args for shape-based suggestions.
 * @returns A suggestion string like " Did you mean 'tool'?" or " Did you mean one of: 'tool1', 'tool2'?", or an empty string if no suggestions are found.
 */
export function getToolSuggestion(
  unknownToolName: string,
  allToolNames: string[],
  topN = 3,
  args?: unknown,
): string {
  const available = new Set(allToolNames);
  const ranked: Array<{ name: string; distance: number }> = [];

  // Shape-based hint first (recover from hallucinated names like generic_tool)
  const inferred = inferToolNameFromArgs(args);
  if (inferred && available.has(inferred)) {
    ranked.push({ name: inferred, distance: 0 });
  }

  const maxDistance = Math.max(4, Math.floor(unknownToolName.length / 2));
  for (const toolName of allToolNames) {
    if (ranked.some((r) => r.name === toolName)) continue;
    const distance = levenshtein.get(unknownToolName, toolName);
    if (distance <= maxDistance) {
      ranked.push({ name: toolName, distance });
    }
  }

  ranked.sort((a, b) => a.distance - b.distance);
  const topNResults = ranked.slice(0, topN);

  if (topNResults.length === 0) {
    return '';
  }

  const suggestedNames = topNResults
    .map((match) => `"${match.name}"`)
    .join(', ');

  if (topNResults.length > 1) {
    return ` Did you mean one of: ${suggestedNames}?`;
  } else {
    return ` Did you mean ${suggestedNames}?`;
  }
}

/**
 * Checks if a tool invocation matches any of a list of patterns.
 *
 * @param toolOrToolName The tool object or the name of the tool being invoked.
 * @param invocation The invocation object for the tool or the command invoked.
 * @param patterns A list of patterns to match against.
 *   Patterns can be:
 *   - A tool name (e.g., "ReadFileTool") to match any invocation of that tool.
 *   - A tool name with a prefix (e.g., "ShellTool(git status)") to match
 *     invocations where the arguments start with that prefix.
 * @returns True if the invocation matches any pattern, false otherwise.
 */
export function doesToolInvocationMatch(
  toolOrToolName: AnyDeclarativeTool | string,
  invocation: AnyToolInvocation | string,
  patterns: string[],
): boolean {
  let toolNames: string[];
  if (isTool(toolOrToolName)) {
    toolNames = [toolOrToolName.name, toolOrToolName.constructor.name];
  } else {
    toolNames = [toolOrToolName];
  }

  if (toolNames.some((name) => SHELL_TOOL_NAMES.includes(name))) {
    toolNames = [...new Set([...toolNames, ...SHELL_TOOL_NAMES])];
  }

  for (const pattern of patterns) {
    const openParen = pattern.indexOf('(');

    if (openParen === -1) {
      // No arguments, just a tool name
      if (toolNames.includes(pattern)) {
        return true;
      }
      continue;
    }

    const patternToolName = pattern.substring(0, openParen);
    if (!toolNames.includes(patternToolName)) {
      continue;
    }

    if (!pattern.endsWith(')')) {
      continue;
    }

    const argPattern = pattern.substring(openParen + 1, pattern.length - 1);

    let command: string;
    if (typeof invocation === 'string') {
      command = invocation;
    } else {
      if (!('command' in invocation.params)) {
        // This invocation has no command - nothing to check.
        continue;
      }
      // eslint-disable-next-line @typescript-eslint/no-unsafe-type-assertion
      command = String((invocation.params as { command: string }).command);
    }

    if (toolNames.some((name) => SHELL_TOOL_NAMES.includes(name))) {
      if (command === argPattern || command.startsWith(argPattern + ' ')) {
        return true;
      }
    }
  }

  return false;
}

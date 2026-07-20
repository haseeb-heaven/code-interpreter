/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import type React from 'react';
import { Box, Text } from 'ink';
import { theme } from '../semantic-colors.js';
import { Table, type Column } from './Table.js';
import type { UsageProviderRow, OpenRouterCreditsInfo } from '../types.js';

interface UsageStatsDisplayProps {
  providers: UsageProviderRow[];
  openRouterCredits?: OpenRouterCreditsInfo;
  openRouterKeyMissing?: boolean;
}

function formatLastUsed(iso: string): string {
  if (!iso) return 'unknown';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date
    .toISOString()
    .replace('T', ' ')
    .replace(/\.\d+Z$/, 'Z');
}

interface UsageRow {
  metric: string;
  requests: string;
  promptTokens: string;
  completionTokens: string;
  totalTokens: string;
  lastUsedAt: string;
  isTotal?: boolean;
}

export const UsageStatsDisplay: React.FC<UsageStatsDisplayProps> = ({
  providers,
  openRouterCredits,
  openRouterKeyMissing,
}) => {
  if (providers.length === 0) {
    return (
      <Box
        borderStyle="round"
        borderColor={theme.border.default}
        paddingTop={1}
        paddingX={2}
      >
        <Text color={theme.text.primary}>
          No provider usage recorded yet. Usage accumulates as you use the CLI.
        </Text>
      </Box>
    );
  }

  const sorted = [...providers].sort((a, b) =>
    a.displayName.localeCompare(b.displayName),
  );

  const totals = sorted.reduce(
    (acc, p) => ({
      requestCount: acc.requestCount + p.requestCount,
      promptTokens: acc.promptTokens + p.promptTokens,
      completionTokens: acc.completionTokens + p.completionTokens,
      totalTokens: acc.totalTokens + p.totalTokens,
    }),
    { requestCount: 0, promptTokens: 0, completionTokens: 0, totalTokens: 0 },
  );

  const rows: UsageRow[] = sorted.map((p) => ({
    metric: p.displayName,
    requests: p.requestCount.toLocaleString(),
    promptTokens: p.promptTokens.toLocaleString(),
    completionTokens: p.completionTokens.toLocaleString(),
    totalTokens: p.totalTokens.toLocaleString(),
    lastUsedAt: formatLastUsed(p.lastUsedAt),
  }));

  rows.push({
    metric: 'Total',
    requests: totals.requestCount.toLocaleString(),
    promptTokens: totals.promptTokens.toLocaleString(),
    completionTokens: totals.completionTokens.toLocaleString(),
    totalTokens: totals.totalTokens.toLocaleString(),
    lastUsedAt: '',
    isTotal: true,
  });

  const columns: Array<Column<UsageRow>> = [
    {
      key: 'metric',
      header: 'Provider',
      width: 16,
      renderCell: (row) => (
        <Text bold={row.isTotal} color={theme.text.link}>
          {row.metric}
        </Text>
      ),
    },
    {
      key: 'requests',
      header: 'Reqs',
      width: 8,
      renderCell: (row) => (
        <Text bold={row.isTotal} color={theme.text.primary}>
          {row.requests}
        </Text>
      ),
    },
    {
      key: 'promptTokens',
      header: 'Prompt',
      width: 12,
      renderCell: (row) => (
        <Text bold={row.isTotal} color={theme.text.primary}>
          {row.promptTokens}
        </Text>
      ),
    },
    {
      key: 'completionTokens',
      header: 'Completion',
      width: 12,
      renderCell: (row) => (
        <Text bold={row.isTotal} color={theme.text.primary}>
          {row.completionTokens}
        </Text>
      ),
    },
    {
      key: 'totalTokens',
      header: 'Total',
      width: 12,
      renderCell: (row) => (
        <Text bold={row.isTotal} color={theme.text.secondary}>
          {row.totalTokens}
        </Text>
      ),
    },
    {
      key: 'lastUsedAt',
      header: 'Last Used',
      flexGrow: 1,
      renderCell: (row) => (
        <Text color={theme.text.secondary}>{row.lastUsedAt}</Text>
      ),
    },
  ];

  return (
    <Box
      borderStyle="round"
      borderColor={theme.border.default}
      flexDirection="column"
      paddingTop={1}
      paddingX={2}
    >
      <Text bold color={theme.text.accent}>
        Cross-Provider Usage
      </Text>
      <Text color={theme.text.secondary}>
        Accumulated token usage across sessions, per provider
      </Text>
      <Box height={1} />

      <Table data={rows} columns={columns} />

      {(openRouterCredits || openRouterKeyMissing) && (
        <>
          <Box height={1} />
          <Box>
            <Box width={20}>
              <Text color={theme.text.link}>OpenRouter Balance:</Text>
            </Box>
            {openRouterCredits ? (
              <Text color={theme.text.primary}>
                {(openRouterCredits.remainingFraction * 100).toFixed(1)}%
                remaining ({' '}
                {(
                  openRouterCredits.totalCredits - openRouterCredits.totalUsage
                ).toFixed(2)}{' '}
                of {openRouterCredits.totalCredits.toFixed(2)} credits )
              </Text>
            ) : (
              <Text color={theme.text.secondary}>
                unavailable (set OPENROUTER_API_KEY, or the credits API is
                unreachable)
              </Text>
            )}
          </Box>
        </>
      )}
    </Box>
  );
};

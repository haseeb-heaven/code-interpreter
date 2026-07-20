/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import type React from 'react';
import { Box, Text } from 'ink';
import { theme } from '../semantic-colors.js';
import { Table, type Column } from './Table.js';
import type { FreeModelsListRow } from '../types.js';

interface FreeModelsDisplayProps {
  entries: FreeModelsListRow[];
}

export const FreeModelsDisplay: React.FC<FreeModelsDisplayProps> = ({
  entries,
}) => {
  if (entries.length === 0) {
    return (
      <Box
        borderStyle="round"
        borderColor={theme.border.default}
        paddingTop={1}
        paddingX={2}
      >
        <Text color={theme.text.primary}>
          No free models found in the catalog.
        </Text>
      </Box>
    );
  }

  const sorted = [...entries].sort((a, b) => a.id.localeCompare(b.id));

  const columns: Array<Column<FreeModelsListRow>> = [
    {
      key: 'id',
      header: 'Model',
      width: 24,
      renderCell: (row) => <Text color={theme.text.link}>{row.id}</Text>,
    },
    {
      key: 'provider',
      header: 'Provider',
      width: 14,
      renderCell: (row) => (
        <Text color={theme.text.primary}>{row.provider}</Text>
      ),
    },
    {
      key: 'tier',
      header: 'Tier',
      width: 10,
      renderCell: (row) => <Text color={theme.text.secondary}>{row.tier}</Text>,
    },
    {
      key: 'available',
      header: 'Available',
      width: 10,
      renderCell: (row) => (
        <Text color={row.available ? theme.status.success : theme.status.error}>
          {row.available ? 'yes' : 'no'}
        </Text>
      ),
    },
    {
      key: 'notes',
      header: 'Notes',
      flexGrow: 1,
      renderCell: (row) => (
        <Text color={theme.text.secondary}>{row.notes}</Text>
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
        Free Models
      </Text>
      <Text color={theme.text.secondary}>
        Models available at no cost, per configs/models.toml
      </Text>
      <Box height={1} />

      <Table data={sorted} columns={columns} />
    </Box>
  );
};

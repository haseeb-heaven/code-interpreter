/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState, useCallback } from 'react';

interface UseWebSearchCommandReturn {
  isWebSearchDialogOpen: boolean;
  openWebSearchDialog: () => void;
  closeWebSearchDialog: () => void;
}

export const useWebSearchCommand = (): UseWebSearchCommandReturn => {
  const [isWebSearchDialogOpen, setIsWebSearchDialogOpen] = useState(false);

  const openWebSearchDialog = useCallback(() => {
    setIsWebSearchDialogOpen(true);
  }, []);

  const closeWebSearchDialog = useCallback(() => {
    setIsWebSearchDialogOpen(false);
  }, []);

  return {
    isWebSearchDialogOpen,
    openWebSearchDialog,
    closeWebSearchDialog,
  };
};

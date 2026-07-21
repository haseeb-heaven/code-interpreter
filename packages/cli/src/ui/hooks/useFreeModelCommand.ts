/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState, useCallback } from 'react';

interface UseFreeModelCommandReturn {
  isFreeModelDialogOpen: boolean;
  openFreeModelDialog: () => void;
  closeFreeModelDialog: () => void;
}

export const useFreeModelCommand = (): UseFreeModelCommandReturn => {
  const [isFreeModelDialogOpen, setIsFreeModelDialogOpen] = useState(false);

  const openFreeModelDialog = useCallback(() => {
    setIsFreeModelDialogOpen(true);
  }, []);

  const closeFreeModelDialog = useCallback(() => {
    setIsFreeModelDialogOpen(false);
  }, []);

  return {
    isFreeModelDialogOpen,
    openFreeModelDialog,
    closeFreeModelDialog,
  };
};

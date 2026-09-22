'use client';

import { useEffect } from 'react';
import { usePlatformStatusStore } from '@/stores/platform-status';

export interface SheetsStatusBarProps {
  onRefresh?: () => void;
  refreshing?: boolean;
}

/**
 * Registers Sheets-specific Refresh on the shell PlatformStatusFooter.
 * Does not render UI: the workspace shell owns the footer chrome.
 */
export function SheetsStatusBar({ onRefresh, refreshing }: SheetsStatusBarProps) {
  useEffect(() => {
    const store = usePlatformStatusStore.getState();
    if (onRefresh) {
      store.setRefresh({
        onRefresh,
        title: 'Refresh workbook from workspace (⌘R)',
      });
    }
    store.setRefreshing(Boolean(refreshing));
    return () => {
      usePlatformStatusStore.getState().clearRefresh();
    };
  }, [onRefresh, refreshing]);

  useEffect(() => {
    usePlatformStatusStore.getState().setRefreshing(Boolean(refreshing));
  }, [refreshing]);

  return null;
}

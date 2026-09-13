'use client';

import { useEffect } from 'react';
import { usePlatformStatusStore } from '@/stores/platform-status';

export interface DocumentsStatusBarProps {
  onRefresh?: () => void;
  refreshing?: boolean;
}

/**
 * Registers Sections-specific Refresh on the shell PlatformStatusFooter.
 * Does not render UI: the workspace shell owns the footer chrome.
 */
export function DocumentsStatusBar({ onRefresh, refreshing }: DocumentsStatusBarProps) {
  useEffect(() => {
    const store = usePlatformStatusStore.getState();
    if (onRefresh) {
      store.setRefresh({
        onRefresh,
        title: 'Refresh document from workspace (⌘R)',
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

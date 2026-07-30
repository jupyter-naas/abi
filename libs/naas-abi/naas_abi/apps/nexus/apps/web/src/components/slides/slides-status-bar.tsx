'use client';

import { useEffect } from 'react';
import { usePlatformStatusStore } from '@/stores/platform-status';

export interface SlidesStatusBarProps {
  onRefresh?: () => void;
  refreshing?: boolean;
}

/**
 * Registers Slides-specific Refresh on the shell PlatformStatusFooter.
 * Does not render UI: the workspace shell owns the footer chrome.
 */
export function SlidesStatusBar({ onRefresh, refreshing }: SlidesStatusBarProps) {
  useEffect(() => {
    const store = usePlatformStatusStore.getState();
    if (onRefresh) {
      store.setRefresh({
        onRefresh,
        title: 'Refresh deck from workspace (⌘R)',
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

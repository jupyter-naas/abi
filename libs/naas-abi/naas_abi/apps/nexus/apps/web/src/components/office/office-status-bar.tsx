'use client';

import { useEffect } from 'react';
import { usePlatformStatusStore } from '@/stores/platform-status';
import type { OfficeKind } from './office-kinds';

export interface OfficeStatusBarProps {
  onRefresh?: () => void;
  refreshing?: boolean;
}

/**
 * Registers the item's Refresh on the shell PlatformStatusFooter.
 * Does not render UI: the workspace shell owns the footer chrome.
 */
export function OfficeStatusBar({
  noun,
  onRefresh,
  refreshing,
}: OfficeStatusBarProps & Pick<OfficeKind, 'noun'>) {
  useEffect(() => {
    const store = usePlatformStatusStore.getState();
    if (onRefresh) {
      store.setRefresh({
        onRefresh,
        title: `Refresh ${noun} from workspace (⌘R)`,
      });
    }
    store.setRefreshing(Boolean(refreshing));
    return () => {
      usePlatformStatusStore.getState().clearRefresh();
    };
  }, [noun, onRefresh, refreshing]);

  useEffect(() => {
    usePlatformStatusStore.getState().setRefreshing(Boolean(refreshing));
  }, [refreshing]);

  return null;
}

// Bound per kind for the editor pages.
export const DocumentsStatusBar = (props: OfficeStatusBarProps) => <OfficeStatusBar noun="document" {...props} />;
export const SheetsStatusBar = (props: OfficeStatusBarProps) => <OfficeStatusBar noun="workbook" {...props} />;
export const SlidesStatusBar = (props: OfficeStatusBarProps) => <OfficeStatusBar noun="deck" {...props} />;

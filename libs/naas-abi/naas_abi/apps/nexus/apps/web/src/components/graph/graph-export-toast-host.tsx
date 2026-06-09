'use client';

import { useEffect } from 'react';
import { ToastStack } from '@/components/graph/toast-notification';
import { useGraphExportStore } from '@/stores/graph-export';

export function GraphExportToastHost({ workspaceId }: { workspaceId: string }) {
  const toasts = useGraphExportStore((state) => state.toasts);
  const dismissToast = useGraphExportStore((state) => state.dismissToast);
  const loadWorkspaceRecords = useGraphExportStore((state) => state.loadWorkspaceRecords);

  useEffect(() => {
    if (!workspaceId) return;
    loadWorkspaceRecords(workspaceId);
  }, [workspaceId, loadWorkspaceRecords]);

  return <ToastStack toasts={toasts} onDismiss={dismissToast} />;
}

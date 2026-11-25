'use client';

import { useEffect } from 'react';
import { useGraphExportStore } from '@/stores/graph-export';

/** Loads the workspace's export records, so exports still running resume (and toast when done). */
export function GraphExportResume({ workspaceId }: { workspaceId: string }) {
  const loadWorkspaceRecords = useGraphExportStore((state) => state.loadWorkspaceRecords);
  useEffect(() => {
    if (workspaceId) loadWorkspaceRecords(workspaceId);
  }, [workspaceId, loadWorkspaceRecords]);
  return null;
}

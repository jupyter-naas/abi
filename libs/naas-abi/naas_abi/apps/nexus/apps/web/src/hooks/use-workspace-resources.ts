'use client';

import { useEffect } from 'react';
import { create } from 'zustand';
import { fetchWorkspaceResources, type WorkspaceResources } from '@/lib/workspace-resources';

type Entry = { status: 'loading' | 'ready'; resources: WorkspaceResources | null };

interface WorkspaceResourcesState {
  byWorkspace: Record<string, Entry>;
  load: (workspaceId: string) => Promise<void>;
}

/** One read per workspace and session: the nav and the pages share it. */
export const useWorkspaceResourcesStore = create<WorkspaceResourcesState>((set, get) => ({
  byWorkspace: {},
  load: async (workspaceId) => {
    if (get().byWorkspace[workspaceId]) return;
    set({ byWorkspace: { ...get().byWorkspace, [workspaceId]: { status: 'loading', resources: null } } });
    const resources = await fetchWorkspaceResources(workspaceId);
    set({ byWorkspace: { ...get().byWorkspace, [workspaceId]: { status: 'ready', resources } } });
  },
}));

/** The workspace's resources (null while loading, or for a caller who may not read them). */
export function useWorkspaceResources(workspaceId: string | null | undefined): Entry {
  const entry = useWorkspaceResourcesStore((state) =>
    workspaceId ? state.byWorkspace[workspaceId] : undefined
  );
  const load = useWorkspaceResourcesStore((state) => state.load);
  useEffect(() => {
    if (workspaceId) void load(workspaceId);
  }, [workspaceId, load]);
  return entry ?? { status: 'loading', resources: null };
}

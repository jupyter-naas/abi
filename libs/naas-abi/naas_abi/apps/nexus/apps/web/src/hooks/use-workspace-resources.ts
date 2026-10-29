'use client';

import { useEffect } from 'react';
import { create } from 'zustand';
import {
  fetchWorkspaceResources,
  type ResourcesAnswer,
  type WorkspaceResources,
} from '@/lib/workspace-resources';

type Entry = { status: 'loading' | 'ready'; resources: WorkspaceResources | null };

export interface WorkspaceResourcesState {
  byWorkspace: Record<string, Entry>;
  /** The call in flight per workspace: a second caller waits for it. */
  pending: Record<string, Promise<void>>;
  /**
   * Read the workspace's resources. A known answer is kept unless `force` (the settings
   * opened again, Reload); one that is not known (denied, failed, none yet) is read again.
   * A failed read keeps the last known answer, and is never kept itself.
   */
  load: (workspaceId: string, force?: boolean) => Promise<void>;
}

export function createWorkspaceResourcesStore(
  fetcher: (workspaceId: string) => Promise<ResourcesAnswer> = fetchWorkspaceResources
) {
  return create<WorkspaceResourcesState>((set, get) => ({
    byWorkspace: {},
    pending: {},
    load: (workspaceId, force = false) => {
      const inFlight = get().pending[workspaceId];
      if (inFlight) return inFlight;
      const known = get().byWorkspace[workspaceId]?.resources ?? null;
      if (known && !force) return Promise.resolve();
      if (!known) {
        set({ byWorkspace: { ...get().byWorkspace, [workspaceId]: { status: 'loading', resources: null } } });
      }
      const promise = (async () => {
        try {
          const answer = await fetcher(workspaceId);
          const resources =
            answer.kind === 'ok' ? answer.resources : answer.kind === 'denied' ? null : known;
          set({ byWorkspace: { ...get().byWorkspace, [workspaceId]: { status: 'ready', resources } } });
        } finally {
          const { [workspaceId]: _done, ...rest } = get().pending;
          set({ pending: rest });
        }
      })();
      set({ pending: { ...get().pending, [workspaceId]: promise } });
      return promise;
    },
  }));
}

/** One store for the nav and the pages. */
export const useWorkspaceResourcesStore = createWorkspaceResourcesStore();

/** Read the caller's usable resources again (the settings Reload, a policy changed). */
export function reloadWorkspaceResources(workspaceId: string | null | undefined): Promise<void> {
  return workspaceId ? useWorkspaceResourcesStore.getState().load(workspaceId, true) : Promise.resolve();
}

/**
 * The workspace's resources (null while loading, or for a caller who may not read them).
 * `refresh`: read them again when the caller mounts (the settings layout, so a module or a
 * policy changed since shows when the settings are opened again).
 */
export function useWorkspaceResources(
  workspaceId: string | null | undefined,
  { refresh = false }: { refresh?: boolean } = {}
): Entry {
  const entry = useWorkspaceResourcesStore((state) =>
    workspaceId ? state.byWorkspace[workspaceId] : undefined
  );
  const load = useWorkspaceResourcesStore((state) => state.load);
  useEffect(() => {
    if (workspaceId) void load(workspaceId, refresh);
  }, [workspaceId, load, refresh]);
  return entry ?? { status: 'loading', resources: null };
}

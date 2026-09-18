'use client';

import { create } from 'zustand';
import { useEffect } from 'react';
import { useAuthStore } from './auth';
import { readGraph } from '@/hooks/use-graph-request';
import type { ExplorerCatalog } from '@/lib/graph-explorer';

interface State {
  key: string;
  data: ExplorerCatalog | null;
  loading: boolean;
  error: string | null;
  revision: number;
  fetchedAt: number;
  load: (workspaceId: string, graphs: string[], force?: boolean) => Promise<void>;
}
let pending: AbortController | undefined;
export const useGraphExplorerStore = create<State>((set, get) => ({
  key: '',
  data: null,
  loading: false,
  error: null,
  revision: 0,
  fetchedAt: 0,
  load: async (workspaceId, graphs, force = false) => {
    const key = JSON.stringify([workspaceId, graphs]);
    const current = get();
    if (
      !workspaceId ||
      (!force && current.key === key && (current.loading || Date.now() - current.fetchedAt < 30000))
    )
      return;
    pending?.abort();
    const controller = new AbortController();
    pending = controller;
    set({
      key,
      data: null,
      loading: true,
      error: null,
      fetchedAt: 0,
      revision: current.revision + 1,
    });
    try {
      const data = await readGraph<ExplorerCatalog>('explorer/catalog',
        JSON.stringify({ workspace_id: workspaceId, graph_uris: graphs }), controller.signal, force);
      if (!controller.signal.aborted && get().key === key)
        set({ data, loading: false, fetchedAt: Date.now() });
    } catch (error) {
      if (!controller.signal.aborted && get().key === key)
        set({
          data: null,
          loading: false,
          error: error instanceof Error ? error.message : 'Could not load Explorer.',
        });
    }
  },
}));

export function invalidateGraphExplorer() {
  pending?.abort();
  useGraphExplorerStore.setState({ key: '', data: null, loading: false, error: null, fetchedAt: 0 });
}

useAuthStore.subscribe((state, previous) => {
  if (state.user?.id !== previous.user?.id || Boolean(state.token) !== Boolean(previous.token)) {
    invalidateGraphExplorer();
  }
});

/** Sidebar and canvas share one request; prior workspace/filter results never flash. */
export function useGraphExplorer(workspaceId: string, graphs: string[]) {
  const key = JSON.stringify([workspaceId, graphs]);
  const userId = useAuthStore(state => state.user?.id);
  const state = useGraphExplorerStore();
  const { load } = state;
  const graphKey = JSON.stringify(graphs);
  useEffect(() => {
    void load(workspaceId, JSON.parse(graphKey) as string[]);
  }, [load, workspaceId, graphKey, userId]);
  return {
    data: state.key === key ? state.data : null,
    error: state.key === key ? state.error : null,
    loading: state.key !== key || state.loading,
    revision: state.revision,
    retry: () => void load(workspaceId, graphs, true),
  };
}

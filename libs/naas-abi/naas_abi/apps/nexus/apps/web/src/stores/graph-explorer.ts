'use client';

import { create } from 'zustand';
import { useEffect } from 'react';
import { authFetch, useAuthStore } from './auth';
import { getApiUrl } from '@/lib/config';
import { readGraph } from '@/hooks/use-graph-request';
import type { ExplorerCatalog, ExplorerGraph } from '@/lib/graph-explorer';

interface State {
  key: string;
  data: ExplorerCatalog | null;
  loading: boolean;
  error: string | null;
  revision: number;
  fetchedAt: number;
  loadStartedAt: number;
  load: (workspaceId: string, graphs: string[], force?: boolean) => Promise<void>;
}
const CATALOG_CACHE_MS = 30_000;
/** In-flight catalog can take minutes on large graphs; allow retry after this. */
const CATALOG_STALE_LOAD_MS = 90_000;
let pending: AbortController | undefined;
export const useGraphExplorerStore = create<State>((set, get) => ({
  key: '',
  data: null,
  loading: false,
  error: null,
  revision: 0,
  fetchedAt: 0,
  loadStartedAt: 0,
  load: async (workspaceId, graphs, force = false) => {
    const key = JSON.stringify([workspaceId, graphs]);
    const current = get();
    if (!workspaceId) return;
    if (!force && current.key === key && !current.loading && Date.now() - current.fetchedAt < CATALOG_CACHE_MS) {
      return;
    }
    if (
      !force &&
      current.loading &&
      current.key === key &&
      Date.now() - current.loadStartedAt < CATALOG_STALE_LOAD_MS
    ) {
      return;
    }
    pending?.abort();
    const controller = new AbortController();
    pending = controller;
    const startedAt = Date.now();
    set({
      key,
      data: force ? null : current.key === key ? current.data : null,
      loading: true,
      error: null,
      fetchedAt: 0,
      loadStartedAt: startedAt,
      revision: current.revision + 1,
    });
    try {
      const data = await readGraph<ExplorerCatalog>('explorer/catalog',
        JSON.stringify({ workspace_id: workspaceId, graph_uris: graphs }), controller.signal, force);
      if (!controller.signal.aborted && get().key === key)
        set({ data, loading: false, fetchedAt: Date.now(), loadStartedAt: 0 });
    } catch (error) {
      if (controller.signal.aborted) return;
      if (get().key === key)
        set({
          data: null,
          loading: false,
          loadStartedAt: 0,
          error: error instanceof Error ? error.message : 'Could not load Explorer.',
        });
    }
  },
}));

export function invalidateGraphExplorer() {
  pending?.abort();
  useGraphExplorerStore.setState({
    key: '',
    data: null,
    loading: false,
    error: null,
    fetchedAt: 0,
    loadStartedAt: 0,
  });
}

type GraphPack = { role_label: string; graphs: ExplorerGraph[] };

interface ListState {
  workspaceId: string;
  graphs: ExplorerGraph[];
  loading: boolean;
  error: string | null;
  fetchedAt: number;
  load: (workspaceId: string, force?: boolean) => Promise<void>;
}

let listPending: AbortController | undefined;
const LIST_TTL_MS = 60_000;

export const useWorkspaceGraphListStore = create<ListState>((set, get) => ({
  workspaceId: '',
  graphs: [],
  loading: false,
  error: null,
  fetchedAt: 0,
  load: async (workspaceId, force = false) => {
    const current = get();
    if (
      !workspaceId ||
      (!force &&
        current.workspaceId === workspaceId &&
        (current.loading || Date.now() - current.fetchedAt < LIST_TTL_MS))
    ) {
      return;
    }
    listPending?.abort();
    const controller = new AbortController();
    listPending = controller;
    set({
      workspaceId,
      graphs: current.workspaceId === workspaceId ? current.graphs : [],
      loading: current.workspaceId !== workspaceId || current.graphs.length === 0,
      error: null,
    });
    try {
      const response = await authFetch(
        `${getApiUrl()}/api/graph/list?workspace_id=${encodeURIComponent(workspaceId)}`,
        { signal: controller.signal },
      );
      if (!response.ok) throw new Error(`Failed to load graphs (${response.status})`);
      const packs = (await response.json()) as GraphPack[];
      const seen = new Set<string>();
      const graphs: ExplorerGraph[] = [];
      for (const pack of Array.isArray(packs) ? packs : []) {
        for (const graph of pack.graphs || []) {
          if (seen.has(graph.uri)) continue;
          seen.add(graph.uri);
          graphs.push(graph);
        }
      }
      if (!controller.signal.aborted && get().workspaceId === workspaceId) {
        set({ graphs, loading: false, fetchedAt: Date.now(), error: null });
      }
    } catch (error) {
      if (!controller.signal.aborted && get().workspaceId === workspaceId) {
        set({
          loading: false,
          error: error instanceof Error ? error.message : 'Could not load graphs.',
        });
      }
    }
  },
}));

useAuthStore.subscribe((state, previous) => {
  if (state.user?.id !== previous.user?.id || Boolean(state.token) !== Boolean(previous.token)) {
    invalidateGraphExplorer();
    listPending?.abort();
    useWorkspaceGraphListStore.setState({
      workspaceId: '',
      graphs: [],
      loading: false,
      error: null,
      fetchedAt: 0,
    });
  }
});

export function useWorkspaceGraphList(workspaceId: string) {
  const state = useWorkspaceGraphListStore();
  const { load } = state;
  useEffect(() => {
    void load(workspaceId);
  }, [load, workspaceId]);
  useEffect(() => {
    const refresh = () => void load(workspaceId, true);
    window.addEventListener('graph-list-update', refresh);
    window.addEventListener('graph-cache-refresh', refresh);
    return () => {
      window.removeEventListener('graph-list-update', refresh);
      window.removeEventListener('graph-cache-refresh', refresh);
    };
  }, [load, workspaceId]);
  const mine = state.workspaceId === workspaceId;
  return {
    graphs: mine ? state.graphs : [],
    loading: !mine || state.loading,
    error: mine ? state.error : null,
    retry: () => void load(workspaceId, true),
  };
}

/** Class-count catalog for the selected graphs. The graph picker uses /api/graph/list. */
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

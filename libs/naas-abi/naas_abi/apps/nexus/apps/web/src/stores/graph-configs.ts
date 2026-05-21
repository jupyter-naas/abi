'use client';

import { create } from 'zustand';
import { getApiUrl } from '@/lib/config';
import { authFetch } from './auth';

export interface GraphConfigItem {
  uri: string;
  label: string;
  role_label: string;
  enabled: boolean;
}

interface GraphConfigsState {
  graphs: GraphConfigItem[];
  loading: boolean;
  workspaceId: string | null;

  fetchGraphs: (workspaceId: string) => Promise<void>;
  toggleGraph: (uri: string) => Promise<void>;
}

const apiBase = () => getApiUrl();

export const useGraphConfigsStore = create<GraphConfigsState>()((set, get) => ({
  graphs: [],
  loading: false,
  workspaceId: null,

  fetchGraphs: async (workspaceId: string) => {
    set({ loading: true, workspaceId });
    try {
      const response = await authFetch(
        `${apiBase()}/api/graph/list?workspace_id=${encodeURIComponent(workspaceId)}`
      );
      if (!response.ok) {
        set({ loading: false });
        return;
      }
      const data = await response.json();
      const packs = Array.isArray(data) ? data : [];
      const items: GraphConfigItem[] = packs.flatMap((pack: {
        role_label?: string;
        graphs: Array<{ uri: string; label?: string; id?: string; enabled?: boolean }>;
      }) =>
        (Array.isArray(pack.graphs) ? pack.graphs : []).map((g) => ({
          uri: g.uri,
          label: g.label ?? g.id ?? g.uri,
          role_label: pack.role_label ?? 'unknown',
          enabled: g.enabled ?? true,
        }))
      );
      set({ graphs: items, loading: false });
    } catch (error) {
      console.error('Failed to fetch graph configs:', error);
      set({ loading: false });
    }
  },

  toggleGraph: async (uri: string) => {
    const { workspaceId, graphs } = get();
    if (!workspaceId) return;
    const target = graphs.find((g) => g.uri === uri);
    if (!target) return;

    const newEnabled = !target.enabled;

    set({
      graphs: graphs.map((g) =>
        g.uri === uri ? { ...g, enabled: newEnabled } : g
      ),
    });

    try {
      const response = await authFetch(
        `${apiBase()}/api/graph/configs/${encodeURIComponent(workspaceId)}/${encodeURI(uri)}`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled: newEnabled }),
        }
      );
      if (!response.ok) {
        set({
          graphs: get().graphs.map((g) =>
            g.uri === uri ? { ...g, enabled: !newEnabled } : g
          ),
        });
        console.error('Failed to toggle graph');
      }
    } catch (error) {
      set({
        graphs: get().graphs.map((g) =>
          g.uri === uri ? { ...g, enabled: !newEnabled } : g
        ),
      });
      console.error('Failed to toggle graph:', error);
    }
  },
}));

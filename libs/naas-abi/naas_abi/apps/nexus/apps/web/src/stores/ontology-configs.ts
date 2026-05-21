'use client';

import { create } from 'zustand';
import { getApiUrl } from '@/lib/config';
import { authFetch } from './auth';

export interface OntologyConfigItem {
  name: string;
  path: string;
  module_name: string;
  submodule_name?: string | null;
  description?: string | null;
  license?: string | null;
  date?: string | null;
  enabled: boolean;
}

interface OntologyConfigsState {
  ontologies: OntologyConfigItem[];
  loading: boolean;
  workspaceId: string | null;

  fetchOntologies: (workspaceId: string) => Promise<void>;
  toggleOntology: (path: string) => Promise<void>;
}

const apiBase = () => getApiUrl();

export const useOntologyConfigsStore = create<OntologyConfigsState>()((set, get) => ({
  ontologies: [],
  loading: false,
  workspaceId: null,

  fetchOntologies: async (workspaceId: string) => {
    set({ loading: true, workspaceId });
    try {
      const response = await authFetch(
        `${apiBase()}/api/ontology/ontologies?workspace_id=${encodeURIComponent(workspaceId)}`
      );
      if (!response.ok) {
        set({ loading: false });
        return;
      }
      const data = await response.json();
      const items: OntologyConfigItem[] = Array.isArray(data?.items) ? data.items : [];
      set({ ontologies: items, loading: false });
    } catch (error) {
      console.error('Failed to fetch ontology configs:', error);
      set({ loading: false });
    }
  },

  toggleOntology: async (path: string) => {
    const { workspaceId, ontologies } = get();
    if (!workspaceId) return;
    const target = ontologies.find((o) => o.path === path);
    if (!target) return;

    const newEnabled = !target.enabled;

    set({
      ontologies: ontologies.map((o) =>
        o.path === path ? { ...o, enabled: newEnabled } : o
      ),
    });

    try {
      const response = await authFetch(
        `${apiBase()}/api/ontology/configs/${encodeURIComponent(workspaceId)}/${encodeURI(path)}`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled: newEnabled }),
        }
      );
      if (!response.ok) {
        set({
          ontologies: get().ontologies.map((o) =>
            o.path === path ? { ...o, enabled: !newEnabled } : o
          ),
        });
        console.error('Failed to toggle ontology');
      }
    } catch (error) {
      set({
        ontologies: get().ontologies.map((o) =>
          o.path === path ? { ...o, enabled: !newEnabled } : o
        ),
      });
      console.error('Failed to toggle ontology:', error);
    }
  },
}));

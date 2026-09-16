import { create } from 'zustand';
import { getApiUrl } from '@/lib/config';
import { authFetch } from './auth';

/**
 * Per-workspace enable state for the reference (module TTL) ontology
 * catalog — the ontology counterpart of `stores/apps.ts`.
 *
 * Note this is the *reference* catalog shipped by engine modules, not the
 * workspace's own classes and relationships (`stores/ontology.ts`).
 */
export interface OntologyCatalogItem {
  /** Stable catalog key, "<module>:<filename.ttl>". */
  ontology_id: string;
  /** Absolute file path — what `?ontology=` and the sidebar use. */
  path: string;
  name: string;
  module_name: string;
  submodule_name?: string | null;
  description?: string | null;
  license?: string | null;
  contributors?: string[];
  date?: string | null;
  imports?: string[];
  enabled: boolean;
}

interface OntologyCatalogState {
  ontologies: OntologyCatalogItem[];
  loading: boolean;
  workspaceId: string | null;

  fetchOntologies: (workspaceId: string) => Promise<void>;
  toggleOntology: (ontologyId: string) => Promise<void>;
}

const apiBase = () => getApiUrl();

export const useOntologyCatalogStore = create<OntologyCatalogState>()((set, get) => ({
  ontologies: [],
  loading: false,
  workspaceId: null,

  fetchOntologies: async (workspaceId: string) => {
    const switched = get().workspaceId !== workspaceId;
    set({ loading: true, workspaceId, ...(switched ? { ontologies: [] } : {}) });
    try {
      const response = await authFetch(
        `${apiBase()}/api/ontology-configs/?workspace_id=${encodeURIComponent(workspaceId)}`
      );
      if (get().workspaceId !== workspaceId) return;
      if (!response.ok) {
        set({ ontologies: [], loading: false });
        return;
      }
      const data = await response.json();
      const ontologies: OntologyCatalogItem[] = Array.isArray(data?.ontologies)
        ? data.ontologies
        : [];
      if (get().workspaceId !== workspaceId) return;
      set({ ontologies, loading: false });
    } catch (error) {
      console.error('Failed to fetch ontologies:', error);
      if (get().workspaceId !== workspaceId) return;
      set({ ontologies: [], loading: false });
    }
  },

  toggleOntology: async (ontologyId: string) => {
    const { workspaceId, ontologies } = get();
    if (!workspaceId) return;
    const target = ontologies.find((o) => o.ontology_id === ontologyId);
    if (!target) return;

    const newEnabled = !target.enabled;

    // Optimistic update
    set({
      ontologies: ontologies.map((o) =>
        o.ontology_id === ontologyId ? { ...o, enabled: newEnabled } : o
      ),
    });

    try {
      const response = await authFetch(
        `${apiBase()}/api/ontology-configs/${encodeURIComponent(workspaceId)}/${encodeURIComponent(ontologyId)}`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled: newEnabled }),
        }
      );
      if (!response.ok) {
        // Rollback
        set({
          ontologies: get().ontologies.map((o) =>
            o.ontology_id === ontologyId ? { ...o, enabled: !newEnabled } : o
          ),
        });
        console.error('Failed to toggle ontology');
      }
    } catch (error) {
      set({
        ontologies: get().ontologies.map((o) =>
          o.ontology_id === ontologyId ? { ...o, enabled: !newEnabled } : o
        ),
      });
      console.error('Failed to toggle ontology:', error);
    }
  },
}));

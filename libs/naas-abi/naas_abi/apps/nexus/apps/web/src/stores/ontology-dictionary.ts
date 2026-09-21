'use client';

import { create } from 'zustand';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import type { DictionaryTerm } from '@/lib/ontology-dictionary-tree';
import type { OntologyDeclaration } from '@/lib/ontology-dashboard';

type DictionaryState = {
  workspaceId: string | null;
  terms: DictionaryTerm[];
  ontologies: OntologyDeclaration[];
  loading: boolean;
  error: string | null;
  fileCount: number;
  loadedFileCount: number;
  errors: Array<{ path: string; name: string; message: string }>;
  revision: number;
  load: (workspaceId: string, revision?: number, force?: boolean) => Promise<void>;
};

let generation = 0;
export const useOntologyDictionaryStore = create<DictionaryState>((set, get) => ({
  workspaceId: null, terms: [], ontologies: [], loading: false, error: null,
  fileCount: 0, loadedFileCount: 0, errors: [], revision: -1,
  load: async (workspaceId, revision = 0, force = false) => {
    const previous = get();
    // A hot update can retain a dictionary loaded before ledger metadata existed.
    const currentProjection = Array.isArray(previous.ontologies) && previous.terms.every(term => term.metadata && (term.type !== 'entity' || 'processLedger' in term));
    if (!force && currentProjection && previous.workspaceId === workspaceId && previous.revision === revision) return;
    const request = ++generation;
    set({ workspaceId, revision, terms: [], ontologies: [], loading: true, error: null, errors: [], fileCount: 0, loadedFileCount: 0 });
    try {
      const query = new URLSearchParams({ workspace_id: workspaceId });
      const response = await authFetch(`${getApiUrl()}/api/ontology/dictionary?${query}`);
      if (!response.ok) throw new Error(`Could not load the workspace dictionary (${response.status}).`);
      const data = await response.json();
      if (!Array.isArray(data.items)) throw new Error('The dictionary response is invalid.');
      if (!Array.isArray(data.ontologies) || data.items.some((term: DictionaryTerm) => !term.metadata)) throw new Error('Ontology metadata is unavailable. Refresh after the API has updated.');
      if (request === generation) set({ terms: data.items, ontologies: data.ontologies, fileCount: data.file_count,
        loadedFileCount: data.loaded_file_count, errors: data.errors || [], loading: false });
    } catch (err) {
      if (request === generation) set({ loading: false, error: err instanceof Error ? err.message : 'Could not load the workspace dictionary.' });
    }
  },
}));

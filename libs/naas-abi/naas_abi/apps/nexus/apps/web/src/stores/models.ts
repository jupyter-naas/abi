import { create } from 'zustand';
import { persist } from 'zustand/middleware';

/**
 * A single entry from the model catalog (`GET /api/providers/models`).
 * We only keep what's needed to map an id to a human-readable name.
 */
export interface CatalogModel {
  canonicalId: string;
  modelId: string;
  provider: string;
  name: string | null;
}

// Re-fetch the catalog at most once every 5 minutes.
const MODELS_CACHE_TTL_MS = 5 * 60 * 1000;

interface ModelsState {
  models: CatalogModel[];
  lastFetchedAt: number | null;
  fetchModels: (force?: boolean) => Promise<void>;
}

export const useModelsStore = create<ModelsState>()(
  persist(
    (set, get) => ({
      models: [],
      lastFetchedAt: null,

      fetchModels: async (force = false) => {
        if (!force) {
          const last = get().lastFetchedAt;
          if (last && Date.now() - last < MODELS_CACHE_TTL_MS) return;
        }
        try {
          const { authFetch } = await import('./auth');
          const { getApiUrl } = await import('@/lib/config');
          const res = await authFetch(`${getApiUrl()}/api/providers/models`);
          if (!res.ok) return;
          const data = await res.json();
          const models: CatalogModel[] = (Array.isArray(data) ? data : []).map(
            (m: {
              canonical_id?: string;
              model_id?: string;
              provider?: string;
              name?: string | null;
            }) => ({
              canonicalId: m.canonical_id ?? '',
              modelId: m.model_id ?? '',
              provider: m.provider ?? '',
              name: m.name ?? null,
            })
          );
          set({ models, lastFetchedAt: Date.now() });
        } catch (e) {
          console.warn('Failed to fetch models', e);
        }
      },
    }),
    { name: 'nexus-models' }
  )
);

/**
 * Resolve a human-readable model name (e.g. "Claude Sonnet 5") for a model id
 * or canonical id (e.g. "claude-sonnet-5"). Falls back to the id itself when the
 * catalog has no matching entry or no name, so callers always get something
 * printable. Returns null only when the id is empty.
 */
export function modelDisplayName(
  models: CatalogModel[],
  id: string | null | undefined
): string | null {
  if (!id) return null;
  const match = models.find((m) => m.modelId === id || m.canonicalId === id);
  return match?.name ?? id;
}

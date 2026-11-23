import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { defineResource, invalidateResource, pathUnder, readResource, type ReadOptions } from '@/lib/resource-cache';

/**
 * A single entry from the model catalog (`GET /api/providers/models`).
 * We only keep what's needed to map an id to a human-readable name.
 */
export interface CatalogModel {
  canonicalId: string;
  modelId: string;
  provider: string;
  name: string | null;
  contextWindow?: number | null;
}

// Re-fetch the catalog at most once every 5 minutes.
const MODELS_CACHE_TTL_MS = 5 * 60 * 1000;

const changesCatalog = (path: string) => pathUnder(path, '/api/providers') || pathUnder(path, '/api/secrets');

/**
 * The deployment's catalogs, read by the chat, Agents and Models settings: one request
 * for all of them, kept 5 minutes in memory, dropped by any provider or secret change.
 */
export const PROVIDER_MODELS = defineResource<Record<string, never>>({
  name: 'provider-models',
  ttlMs: MODELS_CACHE_TTL_MS,
  key: () => '',
  backendCache: false,
  invalidatedBy: changesCatalog,
});

export const AVAILABLE_PROVIDERS = defineResource<Record<string, never>>({
  name: 'available-providers',
  ttlMs: MODELS_CACHE_TTL_MS,
  key: () => '',
  backendCache: false,
  invalidatedBy: changesCatalog,
});

/** `GET /api/providers/models`, shared. */
export async function readProviderModels(options?: ReadOptions): Promise<Response> {
  const { authFetch } = await import('./auth');
  const { getApiUrl } = await import('@/lib/config');
  return readResource(
    PROVIDER_MODELS,
    {},
    () => authFetch(`${getApiUrl()}/api/providers/models`, {}, { settingsCache: PROVIDER_MODELS.backendCache }),
    options,
  );
}

/** `GET /api/providers/available`, shared. */
export async function readAvailableProviders(options?: ReadOptions): Promise<Response> {
  const { authFetch } = await import('./auth');
  const { getApiUrl } = await import('@/lib/config');
  return readResource(
    AVAILABLE_PROVIDERS,
    {},
    () => authFetch(`${getApiUrl()}/api/providers/available`, {}, { settingsCache: AVAILABLE_PROVIDERS.backendCache }),
    options,
  );
}

/** After a catalog edit: every consumer reads the catalog again. */
export function invalidateModelCatalog(): void {
  invalidateResource(PROVIDER_MODELS);
  invalidateResource(AVAILABLE_PROVIDERS);
  useModelsStore.setState({ lastFetchedAt: null });
}

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
          const res = await readProviderModels({ force });
          if (!res.ok) return;
          const data = await res.json();
          const models: CatalogModel[] = (Array.isArray(data) ? data : []).map(
            (m: {
              canonical_id?: string;
              model_id?: string;
              provider?: string;
              name?: string | null;
              context_window?: number | null;
            }) => ({
              canonicalId: m.canonical_id ?? '',
              modelId: m.model_id ?? '',
              provider: m.provider ?? '',
              name: m.name ?? null,
              contextWindow:
                typeof m.context_window === 'number' && Number.isFinite(m.context_window)
                  ? m.context_window
                  : null,
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

function catalogName(model: CatalogModel | undefined): string | null {
  return model?.name?.trim() || null;
}

/**
 * Resolve a human-readable model name (e.g. "Claude Sonnet 5") for a model id
 * or canonical id (e.g. "claude-sonnet-5"). Falls back to the id itself when the
 * catalog has no matching entry or no name, so callers always get something
 * printable. Returns null only when the id is empty.
 *
 * A `provider/model` routing slug needs a second look. The vendor prefix is the
 * upstream vendor the gateway routes to, not the `provider` the catalog records,
 * and the same model is spelled three ways across rows: `claude-sonnet-4.5`,
 * `anthropic/claude-sonnet-4.5` on OpenRouter, `anthropic.claude-sonnet-5` on
 * Bedrock. So an exact-match lookup misses any slug whose prefix happens to
 * disagree with the row that holds the name, and the footer prints the slug.
 * Retry on the model segment alone once the exact spellings are exhausted.
 */
export function modelDisplayName(
  models: CatalogModel[],
  id: string | null | undefined
): string | null {
  if (!id) return null;
  const exact = catalogName(models.find((m) => m.modelId === id || m.canonicalId === id));
  if (exact) return exact;

  const bare = id.includes('/') ? id.slice(id.lastIndexOf('/') + 1) : '';
  if (bare) {
    const routed = catalogName(
      models.find((m) => m.canonicalId === bare || m.modelId === bare)
    );
    if (routed) return routed;
  }
  return id;
}

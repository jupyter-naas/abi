export const LAYER_BASEMAP_PREFS_KEY = 'nexus-maps-layer-basemap-prefs';

type WorkspacePrefs = Record<string, string>;
type Store = Record<string, WorkspacePrefs>;

function readStore(): Store {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.localStorage.getItem(LAYER_BASEMAP_PREFS_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Store;
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

function writeStore(store: Store): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(LAYER_BASEMAP_PREFS_KEY, JSON.stringify(store));
}

/** Per-layer default basemap id (browser-local, per workspace). */
export function getLayerDefaultBasemapId(
  workspaceId: string,
  layerId: string,
): string | undefined {
  const value = readStore()[workspaceId]?.[layerId];
  return typeof value === 'string' && value.trim() ? value.trim() : undefined;
}

export function setLayerDefaultBasemapId(
  workspaceId: string,
  layerId: string,
  basemapId: string | undefined,
): void {
  const store = readStore();
  const workspace = { ...(store[workspaceId] ?? {}) };
  if (!basemapId?.trim()) {
    delete workspace[layerId];
  } else {
    workspace[layerId] = basemapId.trim();
  }
  store[workspaceId] = workspace;
  writeStore(store);
}

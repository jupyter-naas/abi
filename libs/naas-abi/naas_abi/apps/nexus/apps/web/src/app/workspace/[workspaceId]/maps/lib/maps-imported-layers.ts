import { legacyGroupLabel } from './maps-layer-groups';
import {
  buildMapsFeedPayload,
  isMapsFeatureCollection,
  pinRecordsToFeatures,
  type MapsLayerFeatureCollection,
} from './maps-pin-geojson';

export const IMPORTED_LAYERS_STORAGE_KEY = 'nexus-maps-imported-layers';
export const IMPORTED_LAYERS_UPDATED_EVENT = 'nexus-maps-imported-layers-updated';

const LAYER_ID = /^[a-z0-9][a-z0-9-]{0,47}$/;

export type ImportedMapLayer = {
  id: string;
  title: string;
  description: string;
  icon: string;
  color: string;
  order: number;
  /** Sidebar group label (older imports stored a `groupId` slug instead). */
  group?: string;
  featureCollection: MapsLayerFeatureCollection & Record<string, unknown>;
  /** Default Nexus basemap when this layer is shown alone. */
  defaultBasemapId?: string;
  createdAt: string;
};

type WorkspaceStore = Record<string, ImportedMapLayer[]>;

function readStore(): WorkspaceStore {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.localStorage.getItem(IMPORTED_LAYERS_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as WorkspaceStore;
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

function writeStore(store: WorkspaceStore): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(IMPORTED_LAYERS_STORAGE_KEY, JSON.stringify(store));
  window.dispatchEvent(new CustomEvent(IMPORTED_LAYERS_UPDATED_EVENT));
}

export function loadImportedMapLayers(workspaceId: string): ImportedMapLayer[] {
  return (readStore()[workspaceId] ?? []).map((layer) => {
    const legacy = (layer as { groupId?: string }).groupId;
    return layer.group || !legacy ? layer : { ...layer, group: legacyGroupLabel(legacy) };
  });
}

export function getImportedMapLayer(
  workspaceId: string,
  layerId: string,
): ImportedMapLayer | undefined {
  return loadImportedMapLayers(workspaceId).find((layer) => layer.id === layerId);
}

/** URL-safe layer slug from display title (lowercase, dashes). */
export function slugifyLayerSlug(title: string): string {
  const slug = title
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 48);
  if (!slug) return 'layer';
  return LAYER_ID.test(slug) ? slug : `layer-${slug}`.slice(0, 48);
}

export function layerTemplateGeoJson(): MapsLayerFeatureCollection {
  return {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        id: 'example-point',
        geometry: { type: 'Point', coordinates: [2.3522, 48.8566] },
        properties: {
          label: 'Example point',
          detail: 'Optional subtitle · shown on the pin popup',
          color: '#2563eb',
          size: 10,
        },
      },
    ],
  };
}

export function downloadLayerTemplate(): void {
  const blob = new Blob([`${JSON.stringify(layerTemplateGeoJson(), null, 2)}\n`], {
    type: 'application/geo+json',
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = 'nexus-maps-layer-template.geojson';
  anchor.click();
  URL.revokeObjectURL(url);
}

export type ParseGeoJsonResult =
  | { ok: true; collection: MapsLayerFeatureCollection & Record<string, unknown>; featureCount: number }
  | { ok: false; error: string };

/** Accept FeatureCollection, a single Feature, or legacy `{ pins: [...] }`. */
export function parseGeoJsonLayerInput(raw: string): ParseGeoJsonResult {
  const trimmed = raw.trim();
  if (!trimmed) {
    return { ok: false, error: 'Paste GeoJSON or choose a .geojson / .json file.' };
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmed);
  } catch {
    return { ok: false, error: 'Invalid JSON. Check commas, quotes, and brackets.' };
  }
  return normalizeImportedGeoJson(parsed);
}

export function normalizeImportedGeoJson(parsed: unknown): ParseGeoJsonResult {
  if (!parsed || typeof parsed !== 'object') {
    return { ok: false, error: 'Expected a GeoJSON object.' };
  }
  const record = parsed as Record<string, unknown>;

  if (record.type === 'Feature' && record.geometry) {
    const collection = {
      type: 'FeatureCollection' as const,
      features: [record],
      count: 1,
    };
    return { ok: true, collection, featureCount: 1 };
  }

  if (isMapsFeatureCollection(parsed)) {
    const features = parsed.features.filter(
      (feature) => feature?.geometry?.type === 'Point',
    );
    if (features.length === 0 && parsed.features.length > 0) {
      return {
        ok: false,
        error: 'No Point features found. Nexus map layers need Point geometry ([lng, lat]).',
      };
    }
    const collection = {
      ...record,
      type: 'FeatureCollection' as const,
      features,
      count: features.length,
    };
    return { ok: true, collection, featureCount: features.length };
  }

  if (Array.isArray(record.pins)) {
    const pins = record.pins as Array<Record<string, unknown>>;
    const features = pinRecordsToFeatures(pins);
    const collection = buildMapsFeedPayload(pins, {
      source: typeof record.source === 'string' ? record.source : 'imported',
    });
    return { ok: true, collection, featureCount: features.length };
  }

  return {
    ok: false,
    error: 'Use a FeatureCollection, a single Feature, or legacy `{ "pins": [ ... ] }`.',
  };
}

export function validateLayerSlug(slug: string, takenIds: ReadonlySet<string>): string | null {
  if (!slug.trim()) return 'Layer slug is required.';
  if (!LAYER_ID.test(slug)) {
    return 'Lowercase letters, digits and dashes only (max 48, must start with a letter or digit).';
  }
  if (takenIds.has(slug)) return 'This slug is already used by another layer.';
  return null;
}

/** @deprecated use slugifyLayerSlug */
export const slugifyLayerId = slugifyLayerSlug;

/** @deprecated use validateLayerSlug */
export const validateLayerId = validateLayerSlug;

export function saveImportedMapLayer(
  workspaceId: string,
  layer: Omit<ImportedMapLayer, 'createdAt'>,
): ImportedMapLayer {
  const store = readStore();
  const list = store[workspaceId] ?? [];
  const saved: ImportedMapLayer = { ...layer, createdAt: new Date().toISOString() };
  const index = list.findIndex((item) => item.id === layer.id);
  if (index >= 0) list[index] = saved;
  else list.push(saved);
  store[workspaceId] = list.sort((a, b) => a.order - b.order || a.title.localeCompare(b.title));
  writeStore(store);
  return saved;
}

/** Store each imported layer's legacy `groupId` as a `group` label (one-time upgrade). */
export function relabelImportedLayerGroups(
  workspaceId: string,
  labels: Readonly<Record<string, string>>,
): void {
  const store = readStore();
  const list = store[workspaceId];
  if (!list?.some((layer) => 'groupId' in layer)) return;
  store[workspaceId] = list.map((layer) => {
    const { groupId, ...rest } = layer as ImportedMapLayer & { groupId?: string };
    if (rest.group || !groupId) return rest;
    return { ...rest, group: labels[groupId] ?? legacyGroupLabel(groupId) };
  });
  writeStore(store);
}

/** Client hook: imported layers for the active workspace (localStorage). */
export function subscribeImportedLayers(onChange: () => void): () => void {
  if (typeof window === 'undefined') return () => {};
  const handler = () => onChange();
  window.addEventListener(IMPORTED_LAYERS_UPDATED_EVENT, handler);
  return () => window.removeEventListener(IMPORTED_LAYERS_UPDATED_EVENT, handler);
}

export function removeImportedMapLayer(workspaceId: string, layerId: string): void {
  const store = readStore();
  const list = store[workspaceId] ?? [];
  store[workspaceId] = list.filter((layer) => layer.id !== layerId);
  writeStore(store);
}

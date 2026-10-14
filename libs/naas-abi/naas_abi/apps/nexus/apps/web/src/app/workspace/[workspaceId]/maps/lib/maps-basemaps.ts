import type { GeoJSON as GeoJSONLayer, Map as LeafletMap, TileLayer } from 'leaflet';

import type { BasemapCategory, BasemapPalette, BasemapRenderer, WorkspaceBasemap } from './basemaps-api';
import { isMapsDarkMode } from './leaflet-tiles';
import {
  addVectorCountriesBasemapLayer,
  fetchNaturalEarthCountries,
  type NaturalEarthFeatureCollection,
} from './maps-natural-earth-basemap';

/**
 * Basemaps are data: the workspace catalog from `/api/maps/catalog` (seeded by
 * Nexus and the deployment, managed in Settings → Maps). This module only knows
 * how to draw a renderer config; it holds no basemap ids, labels or previews.
 */

/** Used until the catalog names its own default (the API sends `default_basemap_id`). */
export const FALLBACK_BASEMAP_ID = 'openstreetmap';

export interface MapsBasemapDef {
  id: string;
  /** Short label for the toolbar picker. */
  label: string;
  category: BasemapCategory;
  order: number;
  renderer: BasemapRenderer;
  system: boolean;
  /** 0 when the basemap has no preview image. */
  previewVersion: number;
}

export function basemapDefFromApi(basemap: WorkspaceBasemap): MapsBasemapDef {
  return {
    id: basemap.id,
    label: basemap.title,
    category: basemap.category,
    order: basemap.order,
    renderer: basemap.renderer,
    system: basemap.system,
    previewVersion: basemap.preview_content_type ? basemap.preview_version : 0,
  };
}

export type BasemapPickerColumns = Record<BasemapCategory, MapsBasemapDef[]>;

const CATEGORY_ORDER: readonly BasemapCategory[] = ['standard', 'organization', 'custom'];

function byOrder(a: MapsBasemapDef, b: MapsBasemapDef): number {
  return a.order - b.order || a.label.localeCompare(b.label);
}

/** Map type picker columns: standard | organization | custom. */
export function splitBasemapPickerDefs(defs: readonly MapsBasemapDef[]): BasemapPickerColumns {
  const columns: BasemapPickerColumns = { standard: [], organization: [], custom: [] };
  for (const def of defs) (columns[def.category] ?? columns.custom).push(def);
  for (const category of CATEGORY_ORDER) columns[category].sort(byOrder);
  return columns;
}

/**
 * A known id stays; an unknown one falls back to the catalog default, then the
 * first basemap. While the catalog is still loading (no defs) the id is kept,
 * so a stored choice is not lost before the catalog arrives.
 */
export function normalizeBasemapId(
  id: string | null | undefined,
  defs: readonly MapsBasemapDef[] = [],
  defaultId: string = FALLBACK_BASEMAP_ID,
): string {
  if (defs.length === 0) return id || defaultId;
  if (id && defs.some((def) => def.id === id)) return id;
  if (defs.some((def) => def.id === defaultId)) return defaultId;
  return defs[0]!.id;
}

export function basemapLabel(id: string, defs: readonly MapsBasemapDef[] = []): string {
  return defs.find((def) => def.id === id)?.label ?? 'Basemap';
}

export interface MapsBasemapHandle {
  /** Swap the basemap; pass the latest catalog when it changed since install. */
  setBasemap: (id: string, defs?: readonly MapsBasemapDef[]) => void;
  cleanup: () => void;
}

export interface InstallMapsBasemapOptions {
  defs?: readonly MapsBasemapDef[];
}

function tileTemplate(renderer: Extract<BasemapRenderer, { kind: 'tile' }>): string {
  return isMapsDarkMode() && renderer.dark_url ? renderer.dark_url : renderer.url;
}

export function createBasemapTileLayer(
  L: typeof import('leaflet'),
  renderer: Extract<BasemapRenderer, { kind: 'tile' }>,
): TileLayer {
  return L.tileLayer(tileTemplate(renderer), {
    className: 'maps-basemap',
    attribution: renderer.attribution ?? '',
    maxZoom: renderer.max_zoom ?? 19,
    ...(renderer.subdomains?.length ? { subdomains: renderer.subdomains } : {}),
  });
}

/** Fixed palettes apply in light mode; dark mode keeps the theme-aware look. */
function lightPalette(palette: BasemapPalette | undefined): BasemapPalette | undefined {
  return palette && !isMapsDarkMode() ? palette : undefined;
}

function setVectorBasemapBackground(map: LeafletMap, vector: boolean, background?: string): void {
  const container = map.getContainer();
  container.classList.toggle('maps-leaflet--countries-basemap', vector);
  container.style.background = vector && background ? background : '';
}

/** Installs the initial basemap; use setBasemap to swap without remounting the map. */
export function installMapsBasemap(
  L: typeof import('leaflet'),
  map: LeafletMap,
  initialBasemapId: string,
  onBasemapChange?: (id: string) => void,
  options: InstallMapsBasemapOptions = {},
): MapsBasemapHandle {
  let defs = options.defs ?? [];
  let currentId = normalizeBasemapId(initialBasemapId, defs);
  // What is drawn now; a catalog update re-draws the same id when its renderer changed.
  let drawn: string | null = null;
  let currentTile: TileLayer | null = null;
  let currentVector: GeoJSONLayer | null = null;
  let generation = 0;

  const removeLayers = () => {
    currentTile?.remove();
    currentTile = null;
    currentVector?.remove();
    currentVector = null;
    setVectorBasemapBackground(map, false);
  };

  const applyBasemap = () => {
    const def = defs.find((item) => item.id === currentId);
    const signature = def ? `${def.id}:${JSON.stringify(def.renderer)}` : null;
    if (signature === drawn) return;
    removeLayers();
    drawn = signature;
    const run = ++generation;
    if (!def) return; // catalog not loaded yet: plain map background
    const renderer = def.renderer;

    if (renderer.kind === 'tile') {
      currentTile = createBasemapTileLayer(L, renderer);
      currentTile.addTo(map);
      return;
    }

    const palette = lightPalette(renderer.palette);
    setVectorBasemapBackground(map, true, palette?.background);
    const strokeWidth = renderer.kind === 'countries' ? renderer.stroke_width : undefined;
    const draw = (geojson: NaturalEarthFeatureCollection) => {
      if (run !== generation) return;
      currentVector = addVectorCountriesBasemapLayer(L, map, geojson, { palette, strokeWidth });
    };
    if (renderer.kind === 'geojson') {
      draw(renderer.feature_collection as NaturalEarthFeatureCollection);
      return;
    }
    void fetchNaturalEarthCountries()
      .then(draw)
      .catch(() => {
        /* muted background */
      });
  };

  applyBasemap();

  return {
    setBasemap: (id: string, nextDefs?: readonly MapsBasemapDef[]) => {
      if (nextDefs) defs = nextDefs;
      const nextId = normalizeBasemapId(id, defs);
      const changed = nextId !== currentId;
      currentId = nextId;
      applyBasemap();
      if (changed) onBasemapChange?.(nextId);
    },
    cleanup: () => {
      generation += 1;
      drawn = null;
      removeLayers();
    },
  };
}

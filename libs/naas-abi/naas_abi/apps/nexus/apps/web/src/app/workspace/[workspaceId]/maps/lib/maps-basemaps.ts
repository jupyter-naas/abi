import type { Map as LeafletMap, TileLayer } from 'leaflet';

import { isMapsDarkMode, MAPS_TILE_ATTR, MAPS_TILE_DARK, MAPS_TILE_LIGHT } from './leaflet-tiles';

/** Default background under data layers. */
export const DEFAULT_BASEMAP_ID = 'openstreetmap';

export interface MapsBasemapDef {
  id: string;
  /** Short label for the toolbar picker. */
  label: string;
}

/** Tile basemaps. One is active at a time. */
export const MAPS_BASEMAPS: readonly MapsBasemapDef[] = [
  { id: 'openstreetmap', label: 'Street' },
  { id: 'esri-imagery', label: 'Satellite' },
  { id: 'opentopomap', label: 'Topo' },
] as const;

export function normalizeBasemapId(id: string | null | undefined): string {
  if (!id) return DEFAULT_BASEMAP_ID;
  return MAPS_BASEMAPS.some((b) => b.id === id) ? id : DEFAULT_BASEMAP_ID;
}

export function basemapLabel(id: string): string {
  return MAPS_BASEMAPS.find((b) => b.id === normalizeBasemapId(id))?.label ?? 'Basemap';
}

export function createBasemapTileLayer(
  L: typeof import('leaflet'),
  basemapId: string,
): TileLayer {
  const id = normalizeBasemapId(basemapId);
  if (id === 'openstreetmap') {
    return L.tileLayer(isMapsDarkMode() ? MAPS_TILE_DARK : MAPS_TILE_LIGHT, {
      className: 'maps-basemap',
      attribution: MAPS_TILE_ATTR,
      maxZoom: 19,
    });
  }
  if (id === 'esri-imagery') {
    return L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      {
        className: 'maps-basemap',
        attribution:
          'Tiles &copy; Esri — Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community',
        maxZoom: 19,
      },
    );
  }
  return L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
    className: 'maps-basemap',
    subdomains: ['a', 'b', 'c'],
    attribution:
      'Map data: &copy; OpenStreetMap contributors, SRTM | Map style: &copy; OpenTopoMap (CC-BY-SA)',
    maxZoom: 17,
  });
}

export interface MapsBasemapHandle {
  setBasemap: (id: string) => void;
  cleanup: () => void;
}

/** Installs the initial tile layer; use setBasemap to swap without remounting the map. */
export function installMapsBasemap(
  L: typeof import('leaflet'),
  map: LeafletMap,
  initialBasemapId: string,
  onBasemapChange?: (id: string) => void,
): MapsBasemapHandle {
  let currentId = normalizeBasemapId(initialBasemapId);
  let currentLayer = createBasemapTileLayer(L, currentId);
  currentLayer.addTo(map);

  return {
    setBasemap: (id: string) => {
      const nextId = normalizeBasemapId(id);
      if (nextId === currentId) return;
      currentLayer.remove();
      currentId = nextId;
      currentLayer = createBasemapTileLayer(L, nextId);
      currentLayer.addTo(map);
      onBasemapChange?.(nextId);
    },
    cleanup: () => {
      currentLayer.remove();
    },
  };
}

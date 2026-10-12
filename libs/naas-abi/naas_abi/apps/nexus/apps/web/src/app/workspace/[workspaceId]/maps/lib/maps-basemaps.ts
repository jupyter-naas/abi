import type { GeoJSON as GeoJSONLayer, Map as LeafletMap, TileLayer } from 'leaflet';

import { isMapsDarkMode, MAPS_TILE_ATTR, MAPS_TILE_DARK, MAPS_TILE_LIGHT } from './leaflet-tiles';
import {
  addNaturalEarthBasemapLayer,
  fetchNaturalEarthCountries,
} from './maps-natural-earth-basemap';

/** Default background under data layers. */
export const DEFAULT_BASEMAP_ID = 'openstreetmap';

/** Vector country polygons only (Natural Earth, no OSM tiles). */
export const NATURAL_EARTH_BASEMAP_ID = 'natural-earth';

export interface MapsBasemapDef {
  id: string;
  /** Short label for the toolbar picker. */
  label: string;
}

/** Basemaps. One is active at a time. */
export const MAPS_BASEMAPS: readonly MapsBasemapDef[] = [
  { id: 'openstreetmap', label: 'Street' },
  { id: NATURAL_EARTH_BASEMAP_ID, label: 'Countries' },
  { id: 'esri-imagery', label: 'Satellite' },
  { id: 'opentopomap', label: 'Topo' },
] as const;

export function isTileBasemap(basemapId: string): boolean {
  return normalizeBasemapId(basemapId) !== NATURAL_EARTH_BASEMAP_ID;
}

export function normalizeBasemapId(id: string | null | undefined): string {
  if (!id) return DEFAULT_BASEMAP_ID;
  return MAPS_BASEMAPS.some((b) => b.id === id) ? id : DEFAULT_BASEMAP_ID;
}

export function basemapLabel(id: string): string {
  return MAPS_BASEMAPS.find((b) => b.id === normalizeBasemapId(id))?.label ?? 'Basemap';
}

/** Static preview for the map-type popover (`public/maps/basemaps/`). */
export function basemapPreviewSrc(id: string): string {
  const normalized = normalizeBasemapId(id);
  if (normalized === NATURAL_EARTH_BASEMAP_ID) {
    return '/maps/basemaps/natural-earth.svg';
  }
  return `/maps/basemaps/${normalized}.png`;
}

export function createBasemapTileLayer(
  L: typeof import('leaflet'),
  basemapId: string,
): TileLayer {
  const id = normalizeBasemapId(basemapId);
  if (!isTileBasemap(id)) {
    throw new Error(`Basemap ${id} is not a tile layer`);
  }
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

function setCountriesBasemapClass(map: LeafletMap, enabled: boolean): void {
  map.getContainer().classList.toggle('maps-leaflet--countries-basemap', enabled);
}

/** Installs the initial basemap; use setBasemap to swap without remounting the map. */
export function installMapsBasemap(
  L: typeof import('leaflet'),
  map: LeafletMap,
  initialBasemapId: string,
  onBasemapChange?: (id: string) => void,
): MapsBasemapHandle {
  let currentId = normalizeBasemapId(initialBasemapId);
  let currentTile: TileLayer | null = null;
  let currentCountries: GeoJSONLayer | null = null;
  let countriesGeneration = 0;

  const removeLayers = () => {
    currentTile?.remove();
    currentTile = null;
    currentCountries?.remove();
    currentCountries = null;
    setCountriesBasemapClass(map, false);
  };

  const applyBasemap = (nextId: string) => {
    removeLayers();
    currentId = nextId;
    if (nextId === NATURAL_EARTH_BASEMAP_ID) {
      setCountriesBasemapClass(map, true);
      const generation = ++countriesGeneration;
      void fetchNaturalEarthCountries()
        .then((geojson) => {
          if (generation !== countriesGeneration || currentId !== NATURAL_EARTH_BASEMAP_ID) {
            return;
          }
          currentCountries = addNaturalEarthBasemapLayer(L, map, geojson);
        })
        .catch(() => {
          /* keep muted background; pins remain usable */
        });
      return;
    }
    currentTile = createBasemapTileLayer(L, nextId);
    currentTile.addTo(map);
  };

  applyBasemap(currentId);

  return {
    setBasemap: (id: string) => {
      const nextId = normalizeBasemapId(id);
      if (nextId === currentId) return;
      applyBasemap(nextId);
      onBasemapChange?.(nextId);
    },
    cleanup: () => {
      countriesGeneration += 1;
      removeLayers();
    },
  };
}

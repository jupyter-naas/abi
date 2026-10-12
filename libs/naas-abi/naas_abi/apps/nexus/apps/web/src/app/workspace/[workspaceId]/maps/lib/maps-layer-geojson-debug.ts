'use client';

import type { MapsLayerFeatureCollection } from './maps-pin-geojson';

const STORAGE_KEY = 'nexus-maps-layer-geojson-debug';
const UI_ENABLED_KEY = 'nexus-maps-geojson-debug-ui';

export type StoredLayerGeoJson = {
  collection: MapsLayerFeatureCollection;
  savedAt: string;
};

export type LayerGeoJsonDebugStore = Record<string, StoredLayerGeoJson>;

function readStore(): LayerGeoJsonDebugStore {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as LayerGeoJsonDebugStore;
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

function writeStore(store: LayerGeoJsonDebugStore): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
}

export function saveLayerGeoJsonDebug(layerId: string, collection: MapsLayerFeatureCollection): void {
  const store = readStore();
  store[layerId] = { collection, savedAt: new Date().toISOString() };
  writeStore(store);
  window.dispatchEvent(new CustomEvent('nexus-maps-geojson-debug-updated'));
}

export function loadLayerGeoJsonDebugStore(): LayerGeoJsonDebugStore {
  return readStore();
}

export function clearLayerGeoJsonDebug(): void {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(STORAGE_KEY);
  window.dispatchEvent(new CustomEvent('nexus-maps-geojson-debug-updated'));
}

export function downloadJson(filename: string, data: unknown): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/geo+json' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

/** Open the GeoJSON layers modal when `?mapsDebug=geojson` is on the Maps URL. */
export function isMapsGeoJsonDebugEnabled(searchParams: URLSearchParams | null | undefined): boolean {
  return searchParams?.get('mapsDebug') === 'geojson';
}

export function loadGeoJsonDebugUiEnabled(): boolean {
  if (typeof window === 'undefined') return false;
  return window.localStorage.getItem(UI_ENABLED_KEY) === '1';
}

export function setGeoJsonDebugUiEnabled(enabled: boolean): void {
  if (typeof window === 'undefined') return;
  if (enabled) window.localStorage.setItem(UI_ENABLED_KEY, '1');
  else window.localStorage.removeItem(UI_ENABLED_KEY);
}

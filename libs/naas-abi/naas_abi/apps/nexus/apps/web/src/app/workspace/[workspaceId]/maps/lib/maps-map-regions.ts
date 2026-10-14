import type { MapsPinMarker } from './leaflet-map';
import type { BasemapRenderer } from './basemaps-api';
import { findCountryCenter, type CountryCenterIndex } from './maps-country-centers';

export interface MapRegionDefinition {
  id: string;
  name: string;
  labelX: number;
  labelY: number;
  color: string;
  latitude?: number;
  longitude?: number;
  zoom?: number;
}

/** Hide feed region name/count labels from this zoom upward (Leaflet; world ≈ 2–3). */
export const MAPS_REGION_LABELS_MAX_ZOOM = 3;

export function showMapRegionLabelsAtZoom(zoom: number): boolean {
  return zoom < MAPS_REGION_LABELS_MAX_ZOOM;
}

/** Region labels drawn over a basemap that declares regions (`renderer.regions`). */
export interface MapRegionOverlay {
  regions: MapRegionDefinition[];
  countryToRegion: Record<string, string>;
}

export function basemapRegionOverlay(renderer: BasemapRenderer | undefined): MapRegionOverlay | undefined {
  if (!renderer || renderer.kind === 'tile' || !renderer.regions?.length) return undefined;
  const countryToRegion: Record<string, string> = {};
  const regions = renderer.regions.map((region) => {
    for (const country of region.countries) countryToRegion[country] = region.id;
    return {
      id: region.id,
      name: region.name,
      labelX: region.label_x,
      labelY: region.label_y,
      color: region.color,
      latitude: region.latitude,
      longitude: region.longitude,
      zoom: region.zoom,
    };
  });
  return { regions, countryToRegion };
}

export function regionForCountry(
  country: string | undefined,
  countryToRegion: Record<string, string>,
  centers?: CountryCenterIndex | null,
): string | undefined {
  const key = (country ?? '').trim();
  if (!key) return undefined;
  if (countryToRegion[key]) return countryToRegion[key];
  const canonical = findCountryCenter(centers, key)?.name;
  if (canonical && countryToRegion[canonical]) return countryToRegion[canonical];
  const lower = key.toLowerCase();
  const match = Object.keys(countryToRegion).find((name) => name.toLowerCase() === lower);
  return match ? countryToRegion[match] : undefined;
}

export interface RegionFeedFacilityCount {
  feedId: string;
  /** Feed or layer title for the label line. */
  label: string;
  count: number;
}

function feedKey(pin: MapsPinMarker): string {
  return pin.feedId ?? pin.layerId ?? '';
}

function feedLabel(pin: MapsPinMarker): string {
  return (pin.feedTitle ?? pin.feedId ?? pin.layerId ?? 'Layer').trim() || 'Layer';
}

/** Facility counts per region, broken down by feed/layer. */
export function facilityCountsByRegionAndFeed(
  pins: readonly MapsPinMarker[],
  countryToRegion: Record<string, string>,
  centers?: CountryCenterIndex | null,
): Map<string, RegionFeedFacilityCount[]> {
  const byRegion = new Map<string, Map<string, RegionFeedFacilityCount>>();
  for (const pin of pins) {
    const regionId = regionForCountry(pin.country, countryToRegion, centers);
    if (!regionId) continue;
    const key = feedKey(pin);
    if (!key) continue;
    let feeds = byRegion.get(regionId);
    if (!feeds) {
      feeds = new Map();
      byRegion.set(regionId, feeds);
    }
    const existing = feeds.get(key);
    if (existing) {
      existing.count += 1;
    } else {
      feeds.set(key, { feedId: key, label: feedLabel(pin), count: 1 });
    }
  }
  const result = new Map<string, RegionFeedFacilityCount[]>();
  for (const [regionId, feeds] of byRegion) {
    result.set(
      regionId,
      [...feeds.values()].sort(
        (a, b) => b.count - a.count || a.label.localeCompare(b.label),
      ),
    );
  }
  return result;
}

export function distinctMapFeedIds(pins: readonly MapsPinMarker[]): number {
  const ids = new Set<string>();
  for (const pin of pins) {
    const key = feedKey(pin);
    if (key) ids.add(key);
  }
  return ids.size;
}

/** Pin `country` spellings that fall in a region (for country filter after label click). */
export function pinCountriesInMapRegion(
  regionId: string,
  pins: readonly MapsPinMarker[],
  countryToRegion: Record<string, string>,
  centers?: CountryCenterIndex | null,
): string[] {
  const out = new Set<string>();
  for (const pin of pins) {
    const country = pin.country?.trim();
    if (!country) continue;
    if (regionForCountry(country, countryToRegion, centers) === regionId) out.add(country);
  }
  return [...out].sort((a, b) => a.localeCompare(b));
}

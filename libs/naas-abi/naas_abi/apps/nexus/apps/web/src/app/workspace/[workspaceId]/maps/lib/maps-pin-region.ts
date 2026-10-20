import type { MapsPinMarker } from './leaflet-map';
import {
  continentForGrouping,
  findCountryCenter,
  type CountryCenterIndex,
} from './maps-country-centers';
import type { MapsRegionFilter } from '../components/maps-region-filter-control';

export function continentForPin(
  pin: MapsPinMarker,
  centers: CountryCenterIndex | null,
): string | undefined {
  const center = findCountryCenter(centers, pin.country);
  const continent = continentForGrouping(center);
  return continent ?? undefined;
}

export function continentsOnPins(
  pins: readonly MapsPinMarker[],
  centers: CountryCenterIndex | null,
): string[] {
  const set = new Set<string>();
  for (const pin of pins) {
    const continent = continentForPin(pin, centers);
    if (continent) set.add(continent);
  }
  return [...set].sort((a, b) => a.localeCompare(b));
}

export function pinMatchesRegionFilter(
  pin: MapsPinMarker,
  filter: MapsRegionFilter,
  centers: CountryCenterIndex | null,
): boolean {
  if (filter.mode === 'all') return true;
  const continent = continentForPin(pin, centers);
  if (filter.mode === 'none') return false;
  if (!continent) return false;
  return filter.regions.has(continent);
}

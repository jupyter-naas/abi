import type { GeoJSONOptions } from 'leaflet';
export type CountryFeature = Parameters<NonNullable<GeoJSONOptions<Record<string, unknown>>['filter']>>[0];
export interface CountryBorders { type: 'FeatureCollection'; features: CountryFeature[]; }
import type { MapsPinMarker } from './leaflet-map';

function countryKey(value: string): string {
  const key = value.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z]/g, '');
  return ({ unitedstatesofamerica: 'unitedstates', republicofkorea: 'southkorea', russianfederation: 'russia' } as Record<string, string>)[key] ?? key;
}

export function coverageCountries(pins: MapsPinMarker[]): Map<string, number> {
  const countries = new Map<string, Set<string>>();
  for (const pin of pins) {
    if (!pin.country) continue;
    const cities = countries.get(pin.country) ?? new Set<string>();
    cities.add(pin.entityUri ?? pin.id);
    countries.set(pin.country, cities);
  }
  return new Map(Array.from(countries, ([country, cities]) => [country, cities.size]));
}

/** Match country names supplied by a module to Natural Earth's geographic labels. */
export function coverageCountry(feature: CountryFeature, countries: Map<string, number>): string | undefined {
  const properties = feature.properties ?? {};
  const names = [properties.NAME_EN, properties.ADMIN, properties.NAME, properties.NAME_LONG]
    .filter((name): name is string => typeof name === 'string').map(countryKey);
  return Array.from(countries.keys()).find(country => names.includes(countryKey(country)));
}

import type { NaturalEarthFeatureCollection } from './maps-natural-earth-basemap';

/**
 * Country "centers" for group-by-country: Natural Earth's label point
 * (LABEL_X / LABEL_Y — inside the country, where its name is drawn), matched by
 * any of its names (English, local, ~25 languages, ISO code) plus aliases seen in
 * facility feeds. Countries missing from the 110m data (small islands, city
 * states) have no center: callers fall back to the mean of the pins.
 */

export interface CountryCenter {
  /** Natural Earth NAME (English): the marker label and grouping key. */
  name: string;
  lat: number;
  lng: number;
}

export type CountryCenterIndex = ReadonlyMap<string, CountryCenter>;

export function normalizeCountryName(value: string): string {
  return value
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .trim();
}

/** Spellings feeds use that Natural Earth does not (normalized → Natural Earth NAME). */
const ALIASES: Record<string, string> = {
  chine: 'China',
  '中国': 'China',
  'republique tcheque': 'Czechia',
  'czech republic': 'Czechia',
  korea: 'South Korea',
  'republic of korea': 'South Korea',
  'coree du sud': 'South Korea',
  'ελλας': 'Greece',
  usa: 'United States of America',
  'united states': 'United States of America',
  'etats unis': 'United States of America',
  uk: 'United Kingdom',
  'royaume uni': 'United Kingdom',
  russie: 'Russia',
  'emirats arabes unis': 'United Arab Emirates',
};

const NAME_KEYS = /^(NAME(_[A-Z]{2,3})?|NAME_LONG|NAME_ALT|NAME_SORT|NAME_CIAWF|ADMIN|GEOUNIT|SOVEREIGNT|FORMAL_EN|ISO_A2)$/;

export function buildCountryCenterIndex(collection: NaturalEarthFeatureCollection): CountryCenterIndex {
  const index = new Map<string, CountryCenter>();
  const byName = new Map<string, CountryCenter>();
  for (const feature of collection.features) {
    const props = (feature.properties ?? {}) as Record<string, unknown>;
    const name = typeof props.NAME === 'string' ? props.NAME : null;
    const lng = Number(props.LABEL_X);
    const lat = Number(props.LABEL_Y);
    if (!name || !Number.isFinite(lat) || !Number.isFinite(lng)) continue;
    const center = { name, lat, lng };
    byName.set(name, center);
    for (const [key, value] of Object.entries(props)) {
      if (!NAME_KEYS.test(key) || typeof value !== 'string' || !value.trim() || value === '-99') continue;
      const normalized = normalizeCountryName(value);
      if (normalized && !index.has(normalized)) index.set(normalized, center);
    }
  }
  for (const [alias, name] of Object.entries(ALIASES)) {
    const center = byName.get(name);
    const key = normalizeCountryName(alias);
    if (center && !index.has(key)) index.set(key, center);
  }
  return index;
}

export function findCountryCenter(
  index: CountryCenterIndex | null | undefined,
  country: string | undefined,
): CountryCenter | undefined {
  if (!index || !country?.trim()) return undefined;
  return index.get(normalizeCountryName(country));
}

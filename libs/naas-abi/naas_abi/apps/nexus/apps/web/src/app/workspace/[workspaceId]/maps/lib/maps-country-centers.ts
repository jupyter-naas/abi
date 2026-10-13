import type { CountryCenterRow } from '@/app/api/maps/country-centers/centers';

/**
 * Country "centers" for map grouping: Natural Earth 50m label points (inside
 * the country, where its name is drawn), matched by any of the country's names
 * (own names win over translations, codes last) plus aliases seen in facility
 * feeds, with each country's continent. Unknown countries have no center:
 * callers fall back to the mean of the pins.
 */

export interface CountryCenter {
  /** Natural Earth NAME (English): the marker label and grouping key. */
  name: string;
  lat: number;
  lng: number;
  continent?: string | null;
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
  // French country labels common in EU facility feeds (→ Natural Earth NAME).
  allemagne: 'Germany',
  belgique: 'Belgium',
  bresil: 'Brazil',
  egypte: 'Egypt',
  espagne: 'Spain',
  hongrie: 'Hungary',
  inde: 'India',
  indonesie: 'Indonesia',
  irlande: 'Ireland',
  italie: 'Italy',
  japon: 'Japan',
  malaisie: 'Malaysia',
  maroc: 'Morocco',
  mexique: 'Mexico',
  'pays bas': 'Netherlands',
  pologne: 'Poland',
  roumanie: 'Romania',
  slovaquie: 'Slovakia',
  thailande: 'Thailand',
  tunisie: 'Tunisia',
  turquie: 'Turkey',
  brasil: 'Brazil',
};

/** Natural Earth leaves continent empty for some territories; use for group-by-continent. */
export const CONTINENT_BY_COUNTRY_NAME: Readonly<Record<string, string>> = {
  Mauritius: 'Africa',
  Madagascar: 'Africa',
  Réunion: 'Africa',
  Reunion: 'Africa',
  Mayotte: 'Africa',
  Seychelles: 'Africa',
  Maldives: 'Asia',
  Bermuda: 'North America',
  Greenland: 'North America',
};

/** Where a continent marker sits (visual centers, not centroids). */
export const CONTINENT_CENTERS: Readonly<Record<string, { lat: number; lng: number }>> = {
  Africa: { lat: 4, lng: 20 },
  Europe: { lat: 52, lng: 15 },
  Asia: { lat: 38, lng: 95 },
  'North America': { lat: 45, lng: -100 },
  'South America': { lat: -15, lng: -60 },
  Oceania: { lat: -25, lng: 135 },
  Antarctica: { lat: -80, lng: 0 },
};

export function buildCountryCenterIndex(rows: readonly CountryCenterRow[]): CountryCenterIndex {
  const index = new Map<string, CountryCenter>();
  const rank = new Map<string, number>();
  const byName = new Map<string, CountryCenter>();
  for (const row of rows) {
    const center: CountryCenter = { name: row.name, lat: row.lat, lng: row.lng, continent: row.continent };
    byName.set(row.name, center);
    row.names.forEach((value, position) => {
      const key = normalizeCountryName(value);
      // A country's own name beats another country's translation or code.
      if (key && (rank.get(key) ?? Infinity) > position) {
        index.set(key, center);
        rank.set(key, position);
      }
    });
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

/** Continent bucket for cluster markers (null → country-level fallback). */
export function continentForGrouping(center: CountryCenter | undefined): string | null {
  if (!center) return null;
  if (center.continent) return center.continent;
  return CONTINENT_BY_COUNTRY_NAME[center.name] ?? null;
}

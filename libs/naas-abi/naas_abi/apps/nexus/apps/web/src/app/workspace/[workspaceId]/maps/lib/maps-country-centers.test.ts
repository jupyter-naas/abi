import { describe, expect, it } from 'vitest';
import type { CountryCenterRow } from '@/app/api/maps/country-centers/centers';
import {
  buildCountryCenterIndex,
  continentForGrouping,
  findCountryCenter,
} from './maps-country-centers';

const row = (name: string, names: string[], lat: number, lng: number, continent: string | null = 'Europe'): CountryCenterRow => ({
  name,
  names: [name, ...names],
  lat,
  lng,
  continent,
});

const ROWS = [
  // Listed first and named "France" in another language: must not take France.
  row('Fr. S. Antarctic Lands', ['Terres australes françaises', 'France'], -49, 69, null),
  row('France', ['Frankreich', 'FRA'], 46.7, 2.55),
  row('South Africa', ['Afrique du Sud'], -29.7, 23.6, 'Africa'),
  row('China', ['République populaire de Chine'], 32.9, 106.3, 'Asia'),
  row('Germany', ['Deutschland'], 51.1, 10.4, 'Europe'),
  row('Mauritius', ['Maurice'], -20.2, 57.5, null),
];

describe('country centers', () => {
  const index = buildCountryCenterIndex(ROWS);

  it('prefers a country own name over another country translation', () => {
    expect(findCountryCenter(index, 'France')).toEqual({ name: 'France', lat: 46.7, lng: 2.55, continent: 'Europe' });
  });

  it('matches any name, case and accents aside, and knows aliases', () => {
    expect(findCountryCenter(index, 'afrique du sud')?.name).toBe('South Africa');
    expect(findCountryCenter(index, 'FRA')?.name).toBe('France');
    expect(findCountryCenter(index, 'Chine')?.name).toBe('China');
    expect(findCountryCenter(index, 'Allemagne')?.name).toBe('Germany');
    expect(findCountryCenter(index, 'Atlantis')).toBeUndefined();
  });

  it('infers continent for territories Natural Earth leaves blank', () => {
    const mauritius = findCountryCenter(index, 'Mauritius');
    expect(continentForGrouping(mauritius)).toBe('Africa');
  });
});

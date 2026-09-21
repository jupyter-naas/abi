import { expect, it } from 'vitest';
import { coverageCountries, coverageCountry, type CountryFeature } from './maps-coverage';

it('counts cities by identity and matches country labels without inferring extra territory', () => {
  const countryCounts = coverageCountries([
    { id: 'paris', entityUri: 'urn:paris', label: 'Paris', lat: 48, lng: 2, country: 'France' },
    { id: 'paris-copy', entityUri: 'urn:paris', label: 'Paris', lat: 48, lng: 2, country: 'France' },
    { id: 'new-york', label: 'New York', lat: 40, lng: -74, country: 'United States' },
    { id: 'seoul', label: 'Seoul', lat: 37, lng: 127, country: 'South Korea' },
  ]);
  const feature = (properties: Record<string, string>): CountryFeature => ({ type: 'Feature', properties, geometry: { type: 'Polygon', coordinates: [] } });
  expect(countryCounts.get('France')).toBe(1);
  expect(coverageCountry(feature({ ADMIN: 'United States of America' }), countryCounts)).toBe('United States');
  expect(coverageCountry(feature({ NAME_EN: 'Republic of Korea' }), countryCounts)).toBe('South Korea');
  expect(coverageCountry(feature({ NAME_EN: 'Germany' }), countryCounts)).toBeUndefined();
  expect(coverageCountry(feature({ NAME_EN: 'French Polynesia', SOVEREIGNT: 'France' }), countryCounts)).toBeUndefined();
});
